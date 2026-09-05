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
            [InlineKeyboardButton("✅ I've Joined", callback_data="check_fsub")],
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
        fileName = quote_plus(edited_name)

        print(f"Original filename: {filename}")
        print(f"Edited name: {edited_name}")
        print(f"Encoded fileName: {fileName}")

        # Rolled back to the old long URL model: full filename in the path
        # (quote(), not quote_plus() — quote_plus's '+' for spaces is
        # query-string syntax, not valid on a URL path, and corrupts the
        # saved filename in some Android download managers).
        # Clean filename for the URL: spaces -> underscore, strip anything
        # that isn't alnum/dot/dash/underscore (so @ and other symbols are
        # dropped, not percent-encoded). Only whatever's genuinely left
        # over (rare non-ASCII chars) gets %-escaped as a safety net —
        # normal filenames end up with zero %XX in the link.
        url_safe_name = re.sub(r'\s+', '_', filename or edited_name)
        url_safe_name = re.sub(r'[^\w\.-]', '', url_safe_name)
        encoded_name = urllib.parse.quote(url_safe_name, safe='_.-')
        file_hash = get_hash(log_msg)

        if SHORTLINK == False:
            stream   = f"{URL}watch/{log_msg.id}/{encoded_name}?hash={file_hash}"
            download = f"{URL}{log_msg.id}/{encoded_name}?hash={file_hash}"
        else:
            stream   = await get_shortlink(f"{URL}watch/{log_msg.id}/{encoded_name}?hash={file_hash}")
            download = await get_shortlink(f"{URL}{log_msg.id}/{encoded_name}?hash={file_hash}")

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
                    InlineKeyboardButton("🚀 Fast Download 🚀", url=download),
                    InlineKeyboardButton("🖥️ Watch online 🖥️", url=stream),
                ]
            ]),
        )

        rm = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Sᴛʀᴇᴀᴍ 🖥", url=stream),
                InlineKeyboardButton("Dᴏᴡɴʟᴏᴀᴅ 📥", url=download),
            ],
            [
                InlineKeyboardButton("🗑 Revoke Link", callback_data=f"rv_{log_msg.id}_{user_id}"),
            ],
        ])

        msg_text = (
            f"<i><u>𝗬𝗼𝘂𝗿 𝗟𝗶𝗻𝗸 𝗚𝗲𝗻𝗲ʀ𝗮𝘁𝗲𝗱 !</u></i>\n\n"
            f"<b>📂 Fɪʟᴇ ɴᴀᴍᴇ :</b> <i>{filename}</i>\n\n"
            f"<b>📦 Fɪʟᴇ ꜱɪᴢᴇ :</b> <i>{humanbytes(get_media_file_size(message))}</i>\n\n"
            f"<b>📥 Download Link: </b><code>{download}</code>\n\n"
            f"<b><u>⏳ Lɪɴᴋ Exᴘɪʀᴇꜱ Iɴ 𝟤𝟦ʜʀꜱ </u></b>\n\n"
            f"📌 Note :- Use FDM (For PC) or FDM (For Mobile) To Download With Maximum Speed"
        )

        await message.reply_text(
            text=msg_text,
            quote=True,
            disable_web_page_preview=True,
            reply_markup=rm,
        )

    except Exception as e:
        await message.reply_text(f"Sorry, an error occurred while generating the link: {str(e)}")
        print(f"Error in stream_start: {e}")


# ─────────────────────────────────────────────
#  Revoke: delete the file from LOG_CHANNEL — kills every stream/download
#  link pointing at it immediately (route.py's get_messages returns
#  nothing once deleted -> clean 404 for anyone who still has the link).
#  Two-step confirm so a stray tap can't nuke a file by accident.
# ─────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^rv_(\d+)_(\d+)$"))
async def revoke_ask(client, callback_query: CallbackQuery):
    log_msg_id, owner_id = map(int, callback_query.matches[0].groups())
    if callback_query.from_user.id != owner_id and callback_query.from_user.id not in ADMINS:
        await callback_query.answer("❌ This isn't your file.", show_alert=True)
        return
    await callback_query.answer()
    await callback_query.message.edit_reply_markup(
        InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Confirm Revoke", callback_data=f"rvy_{log_msg_id}_{owner_id}"),
                InlineKeyboardButton("Cancel", callback_data=f"rvn_{log_msg_id}_{owner_id}"),
            ]
        ])
    )


@Client.on_callback_query(filters.regex(r"^rvy_(\d+)_(\d+)$"))
async def revoke_confirm(client, callback_query: CallbackQuery):
    log_msg_id, owner_id = map(int, callback_query.matches[0].groups())
    if callback_query.from_user.id != owner_id and callback_query.from_user.id not in ADMINS:
        await callback_query.answer("❌ This isn't your file.", show_alert=True)
        return
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


@Client.on_callback_query(filters.regex(r"^rvn_(\d+)_(\d+)$"))
async def revoke_cancel(client, callback_query: CallbackQuery):
    log_msg_id, owner_id = map(int, callback_query.matches[0].groups())
    if callback_query.from_user.id != owner_id and callback_query.from_user.id not in ADMINS:
        await callback_query.answer("❌ This isn't your file.", show_alert=True)
        return
    await callback_query.answer("Cancelled.")
    # Buttons only carried the ids — links themselves aren't recoverable
    # from here, so just drop back to a plain "revoke again?" button
    # rather than trying to reconstruct the original Stream/Download URLs.
    await callback_query.message.edit_reply_markup(
        InlineKeyboardMarkup([[
            InlineKeyboardButton("🗑 Revoke Link", callback_data=f"rv_{log_msg_id}_{owner_id}"),
        ]])
    )
