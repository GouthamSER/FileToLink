import random, re
import humanize
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery
from pyrogram.errors import UserNotParticipant
from info import URL, LOG_CHANNEL, SHORTLINK, FSUB_CHANNEL 
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
        [[InlineKeyboardButton("✨ Update Channel", url="https://t.me/wudixh12")]]
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

        if SHORTLINK == False:
            stream   = f"{URL}watch/{str(log_msg.id)}/{fileName}?hash={get_hash(log_msg)}"
            download = f"{URL}{str(log_msg.id)}/{fileName}?hash={get_hash(log_msg)}"
        else:
            stream   = await get_shortlink(f"{URL}watch/{str(log_msg.id)}/{fileName}?hash={get_hash(log_msg)}")
            download = await get_shortlink(f"{URL}{str(log_msg.id)}/{fileName}?hash={get_hash(log_msg)}")

        await log_msg.reply_text(
            text=(
                f"•• Lɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \n"
                f"•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \n\n"
                f"•• File Name : {edited_name}"
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
            ]
        ])

        msg_text = (
            f"<i><u>𝗬𝗼𝘂𝗿 𝗟𝗶𝗻𝗸 𝗚𝗲𝗻𝗲ʀ𝗮𝘁𝗲𝗱 !</u></i>\n\n"
            f"<b>📂 Fɪʟᴇ ɴᴀᴍᴇ :</b> <i>{edited_name}</i>\n\n"
            f"<b>📦 Fɪʟᴇ ꜱɪᴢᴇ :</b> <i>{humanbytes(get_media_file_size(message))}</i>\n\n"
            f"<b>📥 Download Link: </b><code>{download}</code>\n\n"
            f"<b><u>🚸 Nᴏᴛᴇ : Lɪɴᴋ Exᴘɪʀᴇꜱ Iɴ 𝟤𝟦ʜʀꜱ </u></b>"
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
