import random, re, urllib.parse
import humanize
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery
from pyrogram.errors import UserNotParticipant
from info import URL, LOG_CHANNEL, SHORTLINK, FSUB_CHANNEL, ADMINS
from urllib.parse import quote_plus
from lib.util.file_properties import get_name, get_hash, get_media_file_size
from lib.util.human_readable import humanbytes
from database.users_chats_db import db
from utils import temp, get_shortlink
import time

# ButtonStyle is a real Telegram Bot API 9.5 (Feb 2026) feature — a
# `style` field on InlineKeyboardButton giving it an actual colored
# appearance in-client (not a modded-client trick). Not every Pyrogram
# fork has caught up to it yet, so this import is wrapped: if the
# installed fork doesn't have it, buttons silently fall back to default
# style instead of crashing the whole bot on import.
try:
    from pyrogram.enums import ButtonStyle
    HAS_BUTTON_STYLE = True
except ImportError:
    HAS_BUTTON_STYLE = False


def styled_button(text, style=None, **kwargs):
    """InlineKeyboardButton with an optional color style, safe on forks
    that don't support ButtonStyle yet — falls back to a plain button."""
    if HAS_BUTTON_STYLE and style is not None:
        return InlineKeyboardButton(text, style=style, **kwargs)
    return InlineKeyboardButton(text, **kwargs)


# ─────────────────────────────────────────────
#  Helper: Check if user is subscribed
# ─────────────────────────────────────────────
async def is_subscribed(client, user_id: int) -> bool:
    """Returns True if the user is a member of FSUB_CHANNEL, False otherwise."""
    try:
        member = await client.get_chat_member(FSUB_CHANNEL, user_id)
        return member.status not in (
            enums.ChatMemberStatus.BANNED,
            enums.ChatMemberStatus.LEFT,
        )
    except UserNotParticipant:
        return False
    except Exception:
        # If we can't check (e.g. bot not admin), allow the user through
        return True


async def send_fsub_message(client, message):
    """Sends the force-subscribe prompt to the user."""
    try:
        invite_link = await client.export_chat_invite_link(FSUB_CHANNEL)
    except Exception:
        invite_link = f"https://t.me/{str(FSUB_CHANNEL).lstrip('@')}"

    rm = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔔 Join Channel", url=invite_link)],
            [styled_button("✅ I've Joined", style=ButtonStyle.SUCCESS if HAS_BUTTON_STYLE else None, callback_data="check_fsub")],
        ]
    )
    await message.reply_text(
        text=(
            "⚠️ <b>You must join our channel to use this bot!</b>\n\n"
            "1️⃣ Click <b>Join Channel</b> below.\n"
            "2️⃣ Then click <b>I've Joined</b> to continue."
        ),
        reply_markup=rm,
        parse_mode=enums.ParseMode.HTML,
    )


# ─────────────────────────────────────────────
#  /start handler
# ─────────────────────────────────────────────
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    user_id = message.from_user.id

    # FSub check
    if not await is_subscribed(client, user_id):
        await send_fsub_message(client, message)
        return

    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)
        await client.send_message(
            LOG_CHANNEL,
            script.LOG_TEXT_P.format(user_id, message.from_user.mention),
        )

    rm = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✨ Update Channel", url="https://t.me/wudixh15")]]
    )
    await client.send_message(
        chat_id=user_id,
        text=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
        reply_markup=rm,
        parse_mode=enums.ParseMode.HTML,
    )


# ─────────────────────────────────────────────
#  Callback: "I've Joined" button
# ─────────────────────────────────────────────
@Client.on_callback_query(filters.regex("^check_fsub$"))
async def check_fsub_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if await is_subscribed(client, user_id):
        await callback_query.message.delete()
        await callback_query.answer("✅ Thanks for joining! You can now use the bot.", show_alert=True)

        # Re-trigger the welcome message after successful join
        if not await db.is_user_exist(user_id):
            await db.add_user(user_id, callback_query.from_user.first_name)
            await client.send_message(
                LOG_CHANNEL,
                script.LOG_TEXT_P.format(user_id, callback_query.from_user.mention),
            )
        rm = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✨ Update Channel", url="https://t.me/wudixh12")]]
        )
        await client.send_message(
            chat_id=user_id,
            text=script.START_TXT.format(
                callback_query.from_user.mention, temp.U_NAME, temp.B_NAME
            ),
            reply_markup=rm,
            parse_mode=enums.ParseMode.HTML,
        )
    else:
        await callback_query.answer(
            "❌ You haven't joined yet! Please join and try again.", show_alert=True
        )


# ─────────────────────────────────────────────
#  File / Stream handler
# ─────────────────────────────────────────────
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def stream_start(client, message):
    user_id = message.from_user.id

    # FSub check
    if not await is_subscribed(client, user_id):
        await send_fsub_message(client, message)
        return

    try:
        file = getattr(message, message.media.value)
        filename = file.file_name
        fileid = file.file_id
        username = message.from_user.mention

        log_msg = await client.send_cached_media(chat_id=LOG_CHANNEL, file_id=fileid)

        edited_name = get_name(log_msg)
        edited_name = re.sub(r'[^\w\.-]', '', edited_name)
        edited_name = edited_name.replace(" ", ".")

        file_hash = get_hash(log_msg)

        # No filename in the URL at all — just server + message id + hash.
        # The real filename is never lost: Content-Disposition (and the
        # download= attribute on the button) already force it onto the
        # saved file at actual download time regardless of what the URL
        # itself looks like — this only cleans up what's visible in the
        # link people share.
        if SHORTLINK == False:
            stream   = f"{URL}watch/{log_msg.id}?hash={file_hash}"
            download = f"{URL}{log_msg.id}?hash={file_hash}"
        else:
            stream   = await get_shortlink(f"{URL}watch/{log_msg.id}?hash={file_hash}")
            download = await get_shortlink(f"{URL}{log_msg.id}?hash={file_hash}")

        # Send log message to log channel
        await log_msg.reply_text(
            text=(
                f"•• Lɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \n"
                f"•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \n\n"
                f"•• File Name : {filename}"
            ),
            quote=True,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [
                    styled_button("🚀 Fast Download 🚀", style=ButtonStyle.PRIMARY if HAS_BUTTON_STYLE else None, url=download),
                    styled_button("🖥️ Watch online 🖥️", style=ButtonStyle.SUCCESS if HAS_BUTTON_STYLE else None, url=stream),
                ]
            ]),
        )

        # Updated Message Text Formatting with Blockquotes
        bot_me = await client.get_me()
        bot_username = f"@{bot_me.username}" if bot_me.username else temp.U_NAME

        msg_text = (
            f"<blockquote>▶ <b>File Name :</b> <i>{filename}</i>\n\n"
            f"▶ <b>File Size :</b> {humanbytes(get_media_file_size(message))}</blockquote>\n\n"
            f"<blockquote>➞ <b>Download :</b> <a href='{download}'>{download}</a>\n\n"
            f"➞ <b>Watch Online :</b> <a href='{stream}'>{stream}</a></blockquote>\n\n"
            f"💡 <i>Tip :- Use IDM (For PC) or 1DM (For Mobile) To Download With Maximum Speed</i>\n\n"
            f"<blockquote>CC : {bot_username}</blockquote>"
        )

        # Colored buttons (ButtonStyle — Bot API 9.5): blue Download,
        # green Watch, red Delete. No Rename button — never had one.
        rm = InlineKeyboardMarkup([
            [
                styled_button("⬇ Download", style=ButtonStyle.PRIMARY if HAS_BUTTON_STYLE else None, url=download),
                styled_button("▶ Watch", style=ButtonStyle.SUCCESS if HAS_BUTTON_STYLE else None, url=stream),
            ],
            [
                styled_button("⌫ Delete", style=ButtonStyle.DANGER if HAS_BUTTON_STYLE else None, callback_data=f"rv_{log_msg.id}_{user_id}"),
            ]
        ])

        # Send to user
        await message.reply_text(
            text=msg_text,
            quote=True,
            disable_web_page_preview=True,
            reply_markup=rm,
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(f"Sorry, an error occurred while generating the link: {str(e)}")
        print(f"Error in stream_start: {e}")


# ─────────────────────────────────────────────
#  Revoke: delete the file from LOG_CHANNEL.
#
#  Tap-twice confirm instead of swapping buttons. The old approach
#  replaced the message's ENTIRE reply_markup with a Confirm/Cancel
#  pair, and Cancel had no way to reconstruct the original Download/
#  Watch buttons (their URLs aren't stored anywhere retrievable at that
#  point) — so Cancel permanently lost them, leaving only a bare Delete
#  button behind. Never touching reply_markup at all avoids that
#  entirely: same Delete button both taps, state lives in a small
#  in-memory dict instead.
# ─────────────────────────────────────────────
_PENDING_REVOKES = {}   # {(log_msg_id, owner_id): expires_at_timestamp}
_REVOKE_CONFIRM_WINDOW = 10  # seconds


@Client.on_callback_query(filters.regex(r"^rv_(\d+)_(\d+)$"))
async def revoke_tap(client, callback_query: CallbackQuery):
    log_msg_id, owner_id = map(int, callback_query.matches[0].groups())
    if callback_query.from_user.id != owner_id and callback_query.from_user.id not in ADMINS:
        await callback_query.answer("❌ This isn't your file.", show_alert=True)
        return

    key = (log_msg_id, owner_id)
    now = time.time()
    expires_at = _PENDING_REVOKES.get(key)

    if expires_at and now < expires_at:
        # Second tap within the window — actually delete.
        _PENDING_REVOKES.pop(key, None)
        try:
            await client.delete_messages(chat_id=LOG_CHANNEL, message_ids=log_msg_id)
        except Exception as e:
            await callback_query.answer(f"Failed to revoke: {e}", show_alert=True)
            return
        await callback_query.answer("🗑 Revoked — links are now dead.", show_alert=True)
        try:
            await callback_query.message.edit_text(
                "🗑 <b>This file has been revoked.</b>\nAll stream/download links for it no longer work.",
                reply_markup=None,
            )
        except Exception:
            pass
        return

    # First tap — arm it, don't touch any buttons.
    _PENDING_REVOKES[key] = now + _REVOKE_CONFIRM_WINDOW
    await callback_query.answer(
        f"⚠️ Tap Delete again within {_REVOKE_CONFIRM_WINDOW}s to permanently delete this file.",
        show_alert=True,
    )
