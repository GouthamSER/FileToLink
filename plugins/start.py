import random,re
import humanize
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery
from pyrogram.errors import UserNotParticipant
from info import URL, LOG_CHANNEL, SHORTLINK, FORCE_SUB_CHANNELS, INVITE_LINKS, AUTO_DELETE_TIME
from urllib.parse import quote_plus
from lib.util.file_properties import get_name, get_hash, get_media_file_size
from lib.util.human_readable import humanbytes
from database.users_chats_db import db
from utils import temp, get_shortlink, check_force_sub

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    user_id = message.from_user.id
    # =========================
    # Force Subscribe Check
    # =========================
    not_joined = await check_force_sub(client, user_id)
    if not_joined:
        buttons = []
        for channel in not_joined:
            if isinstance(channel, str):  # Public
                link = f"https://t.me/{channel}"
            else:  # Private
                link = INVITE_LINKS.get(channel)
            if link:
                buttons.append(
                    [InlineKeyboardButton("🔔 Join Channel", url=link)]
                )
        buttons.append(
            [InlineKeyboardButton("✅ Try Again", callback_data="check_sub")]
        )
        msg = await message.reply(
            "⚠️ You must join all required channels to use this bot.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await asyncio.sleep(AUTO_DELETE_TIME)
        await msg.delete()
        return
    # =========================
    # User Passed Force Sub
    # =========================
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)
        await client.send_message(
            LOG_CHANNEL,
            script.LOG_TEXT_P.format(user_id, message.from_user.mention)
        )
    rm = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✨ Update Channel", url="https://t.me/wudixh15")]]
    )
    await client.send_message(
        chat_id=user_id,
        text=script.START_TXT.format(
            message.from_user.mention,
            temp.U_NAME,
            temp.B_NAME
        ),
        reply_markup=rm,
        parse_mode=enums.ParseMode.HTML
    )

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def stream_start(client, message):
    if not await db.is_user_exist(user_id):  # added here if bot not started
        await db.add_user(user_id, message.from_user.first_name)
        await client.send_message(
            LOG_CHANNEL,
            script.LOG_TEXT_P.format(user_id, message.from_user.mention)
        )
    try:
        file = getattr(message, message.media.value)
        filename = file.file_name
        filesize = humanize.naturalsize(file.file_size) 
        fileid = file.file_id
        user_id = message.from_user.id
        username =  message.from_user.mention 

        log_msg = await client.send_cached_media(
            chat_id=LOG_CHANNEL,
            file_id=fileid,
        )
        # Get and sanitize the filename: remove special characters, replace spaces with dots
        edited_name = get_name(log_msg)
        edited_name = re.sub(r'[^\w\.-]', '', edited_name)  # Remove non-alphanumeric, dot, hyphen (strips @, :, spaces, etc.)
        edited_name = edited_name.replace(" ", ".")  # Replace any remaining spaces with dots
        fileName = quote_plus(edited_name)
        
        # Debug: Print for troubleshooting (remove in production)
        print(f"Original filename: {filename}")
        print(f"Edited name: {edited_name}")
        print(f"Encoded fileName: {fileName}")
        
        if SHORTLINK == False:
            stream = f"{URL}watch/{str(log_msg.id)}/{fileName}?hash={get_hash(log_msg)}"
            download = f"{URL}{str(log_msg.id)}/{fileName}?hash={get_hash(log_msg)}"
        else:
            stream = await get_shortlink(f"{URL}watch/{str(log_msg.id)}/{fileName}?hash={get_hash(log_msg)}")
            download = await get_shortlink(f"{URL}{str(log_msg.id)}/{fileName}?hash={get_hash(log_msg)}")
            
        await log_msg.reply_text(
            text=f"•• Lɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \n•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \n\n•• File Name : {edited_name}",
            quote=True,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Fast Download 🚀", url=download),  # we download Link
                                                InlineKeyboardButton('🖥️ Watch online 🖥️', url=stream)]])  # web stream Link
        )
        rm=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("𝖲𝗍𝗋𝖾𝖺𝗆 🖥", url=stream),
                    InlineKeyboardButton("𝖣𝗈𝗐𝗇𝗅𝗈𝖺𝖽 📥", url=download)
                ]
            ] 
        )
        msg_text = f"""<u>𝘓𝘪𝘯𝘬 𝘎𝘦𝘯𝘦𝘳𝘢𝘵𝘦𝘥 !</u>\n
<b>📂 𝖥𝗂𝗅𝖾 𝖭𝖺𝗆𝖾 :</b> <i>{edited_name}</i>\n
<b>📦 𝖥𝗂𝗅𝖾 𝖲𝗂𝗓𝖾 :</b> <i>{humanbytes(get_media_file_size(message))}</i>\n
<b>📥 𝖣𝗈𝗐𝗇𝗅𝗈𝖺𝖽 𝖫𝗂𝗇𝗄 : </b><code>{download}</code>\n
<b>🚸 𝖭𝗈𝗍𝖾 : 𝖫𝗂𝗇𝗄 𝖶𝗂𝗅𝗅 𝖤𝗑𝗉𝗂𝗋𝖾𝗌 𝗂𝗇 𝟤𝟦𝗁𝗋𝗌</b>"""

        await message.reply_text(
        text=msg_text,
        quote=True,
        disable_web_page_preview=True,
        reply_markup=rm
        )
    except Exception as e:
        # Error handling: Reply to user and log
        await message.reply_text(f"Sorry, an error occurred while generating the link: {str(e)}")
        print(f"Error in stream_start: {e}")  # Replace with logging in production

# ===============================
# Callback: Recheck Subscription start cmnd 
# ===============================

@Client.on_callback_query(filters.regex("check_sub"))
async def check_sub_callback(client, callback_query):

    user_id = callback_query.from_user.id
    not_joined = await check_force_sub(client, user_id)

    if not_joined:
        await callback_query.answer(
            "❌ You have not joined all required channels!",
            show_alert=True
        )
    else:
        await callback_query.message.edit(
            "✅ Subscription verified! You can now use the bot."
        )
