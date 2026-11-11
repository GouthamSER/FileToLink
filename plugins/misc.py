import os
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from info import is_admin
from database.users_chats_db import db
from utils import temp
from lib import StartTime

LOG_FILE = "TELEGRAM BOT.LOG"


@Client.on_message(filters.command("ping") & filters.private)
async def ping_cmd(client: Client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    ms = (time.time() - start) * 1000
    up = int(time.time() - StartTime)
    d, r = divmod(up, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    await msg.edit_text(
        f"🏓 <b>Pong!</b>\n\n⚡ Response: <code>{ms:.0f} ms</code>\n"
        f"⏱ Uptime: <code>{d}d {h}h {m}m {s}s</code>"
    )


@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        "<b>🛸 Help</b>\n\n"
        "Send me any file (document, video, audio, photo) and I'll give you "
        "an instant <b>Stream</b> + <b>Download</b> link.\n\n"
        "/start - Start the bot\n"
        "/how - How to use\n"
        "/about - About the bot\n"
        "/ping - Bot status and response time",
        disable_web_page_preview=True,
    )


@Client.on_message(filters.command("about") & filters.private)
async def about_cmd(client: Client, message: Message):
    await message.reply_text(
        f"<b>🤖 About</b>\n\n"
        f"Name: <b>{temp.B_NAME}</b>\n"
        f"Username: @{temp.U_NAME}\n"
        "Function: File → direct stream/download link",
        disable_web_page_preview=True,
    )


@Client.on_message(filters.command("users") & filters.private)
async def users_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id, message.from_user.username):
        return await message.reply_text("❌ You are not authorized.")
    total = await db.total_users_count()
    await message.reply_text(f"👥 Total users: <code>{total}</code>")


@Client.on_message(filters.command("log") & filters.private)
async def log_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id, message.from_user.username):
        return await message.reply_text("❌ You are not authorized.")
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        return await message.reply_text("📄 Log empty (no errors logged).")
    await message.reply_document(LOG_FILE, caption="📄 Bot error log")
