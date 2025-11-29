import psutil
import shutil
from pyrogram import Client, filters
from info import ADMINS       # <-- your admin IDs list
from database.users_chats_db import db
import os
import sys


@Client.on_message(filters.command("stats") & filters.private)
async def stats(_, message):
    # Allow only admins
    if message.from_user.id not in ADMINS:
        return await message.reply_text("You are not authorized to use this command.")

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)

    # RAM
    ram = psutil.virtual_memory()
    ram_used = round(ram.used / (1024 ** 2), 2)
    ram_total = round(ram.total / (1024 ** 2), 2)
    ram_percent = ram.percent

    # DISK
    disk = shutil.disk_usage("/")
    disk_used = round(disk.used / (1024 ** 3), 2)
    disk_total = round(disk.total / (1024 ** 3), 2)
    disk_percent = round((disk.used / disk.total) * 100, 2)

    # DB Users Count
    total_users = await db.total_users_count()

    text = (
        "<blockquote>📊 <b>Bot Full Statistics</b>\n\n"
        f"👥 <b>Total Users:</b> <code>{total_users}</code>\n\n"
        f"⚙️ <b>CPU Usage:</b> <code>{cpu_percent}%</code>\n"
        f"🧠 <b>RAM Usage:</b> <code>{ram_used} MB / {ram_total} MB</code> (<code>{ram_percent}%</code>)\n"
        f"💾 <b>Disk Usage:</b> <code>{disk_used} GB / {disk_total} GB</code> (<code>{disk_percent}%</code>)\n"
        "\n🚀 <b>Status:</b> Bot running smoothly!</blockquote>"
    )

    await message.reply_text(text)

#VIDEO SENTING HOW IT WORKS /////////////

@Client.on_message(filters.private & filters.command("how"))
async def send_two_videos(client, message):

    # First video
    await client.send_video(
        chat_id=message.chat.id,
        video="plugins/testvideo/vid1.mp4",
        caption="Look this !!!"
    )

@Client.on_message(filters.command("restart") & filters.private)
async def restart_bot(client, message):

    if message.from_user.id not in ADMINS:
        return await message.reply_text("❌ You are not authorized.")

    await message.reply_text("♻️ <b>Bot restarted!</b>")

    os.execv(sys.executable, ['python'] + sys.argv)
