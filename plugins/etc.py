import psutil
import sys
import os
import shutil
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from info import ADMINS
from database.users_chats_db import db

# Assuming you have a start time variable somewhere in your bot
# If not, add this at the top of your main bot file or here
try:
    from bot import StartTime
except:
    StartTime = time.time()

def get_readable_time(seconds: int) -> str:
    """Convert seconds to readable time format"""
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result.append(f'{int(period_value)}{period_name}')
    return ' '.join(result) if result else '0s'

def humanbytes(size):
    """Convert bytes to human readable format"""
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    while size > power and n < len(units) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {units[n]}"

@Client.on_message(filters.command("stats") & filters.private)
async def stats(client: Client, message: Message):
    # Allow only admins
    if message.from_user.id not in ADMINS:
        return await message.reply_text("❌ You are not authorized to use this command.")
    
    try:
        # Send "Processing..." message
        status_msg = await message.reply_text("📊 Fetching statistics...")
        
        # Get system uptime - FIXED: boot_time() is not async, doesn't need await
        sys_uptime = psutil.boot_time()
        sys_uptime_str = get_readable_time(int(time.time() - sys_uptime))
        
        # Get bot uptime
        bot_uptime_str = get_readable_time(int(time.time() - StartTime))
        
        # Get network I/O counters
        net_io_counters = await asyncio.to_thread(psutil.net_io_counters)
        
        # Get CPU information
        cpu_percent = await asyncio.to_thread(psutil.cpu_percent, interval=0.5)
        cpu_cores = await asyncio.to_thread(psutil.cpu_count, logical=False)
        cpu_freq = await asyncio.to_thread(psutil.cpu_freq)
        cpu_freq_ghz = f"{cpu_freq.current / 1000:.2f} GHz" if cpu_freq else "N/A"
        
        # Get RAM information
        ram_info = await asyncio.to_thread(psutil.virtual_memory)
        ram_total = humanbytes(ram_info.total)
        ram_used = humanbytes(ram_info.used)
        ram_free = humanbytes(ram_info.available)
        ram_percent = ram_info.percent
        
        # Get disk usage
        disk_usage = await asyncio.to_thread(psutil.disk_usage, '/')
        total_disk = humanbytes(disk_usage.total)
        used_disk = humanbytes(disk_usage.used)
        free_disk = humanbytes(disk_usage.free)
        disk_percent = disk_usage.percent
        
        # Get total users from database
        total_users = await db.total_users_count()
        
        # Format the stats message
        stats_text = (
            "<blockquote>📊 <b>Bot System Statistics</b>\n\n"
            f"👥 <b>Total Users:</b> <code>{total_users}</code>\n\n"
            f"⏰ <b>System Uptime:</b> <code>{sys_uptime_str}</code>\n"
            f"🤖 <b>Bot Uptime:</b> <code>{bot_uptime_str}</code>\n\n"
            f"⚙️ <b>CPU Usage:</b> <code>{cpu_percent}%</code>\n"
            f"🔢 <b>CPU Cores:</b> <code>{cpu_cores if cpu_cores else 'N/A'}</code>\n"
            f"⚡ <b>CPU Frequency:</b> <code>{cpu_freq_ghz}</code>\n\n"
            f"🧠 <b>RAM Usage:</b> <code>{ram_used} / {ram_total}</code> (<code>{ram_percent}%</code>)\n"
            f"💚 <b>RAM Free:</b> <code>{ram_free}</code>\n\n"
            f"💾 <b>Disk Usage:</b> <code>{used_disk} / {total_disk}</code> (<code>{disk_percent}%</code>)\n"
            f"📁 <b>Disk Free:</b> <code>{free_disk}</code>\n\n"
            f"📤 <b>Upload:</b> <code>{humanbytes(net_io_counters.bytes_sent)}</code>\n"
            f"📥 <b>Download:</b> <code>{humanbytes(net_io_counters.bytes_recv)}</code>\n\n"
            "🚀 <b>Status:</b> Bot running smoothly!</blockquote>"
        )
        
        # Update the message with stats
        await status_msg.edit_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
                [InlineKeyboardButton("❌ Close", callback_data="close_stats")]
            ])
        )
        
    except Exception as e:
        logging.error(f"Stats command error: {e}", exc_info=True)
        await message.reply_text(f"❌ <b>Error:</b> <code>{str(e)}</code>")

# Callback query handler for refresh and close buttons
@Client.on_callback_query(filters.regex("^(refresh_stats|close_stats)$"))
async def stats_callback(client: Client, callback_query):
    if callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("❌ You are not authorized!", show_alert=True)
    
    if callback_query.data == "close_stats":
        await callback_query.message.delete()
        return
    
    if callback_query.data == "refresh_stats":
        await callback_query.answer("🔄 Refreshing stats...")
        
        try:
            # Get all stats again (same as above)
            sys_uptime = psutil.boot_time()
            sys_uptime_str = get_readable_time(int(time.time() - sys_uptime))
            bot_uptime_str = get_readable_time(int(time.time() - StartTime))
            net_io_counters = await asyncio.to_thread(psutil.net_io_counters)
            cpu_percent = await asyncio.to_thread(psutil.cpu_percent, interval=0.5)
            cpu_cores = await asyncio.to_thread(psutil.cpu_count, logical=False)
            cpu_freq = await asyncio.to_thread(psutil.cpu_freq)
            cpu_freq_ghz = f"{cpu_freq.current / 1000:.2f} GHz" if cpu_freq else "N/A"
            ram_info = await asyncio.to_thread(psutil.virtual_memory)
            ram_total = humanbytes(ram_info.total)
            ram_used = humanbytes(ram_info.used)
            ram_free = humanbytes(ram_info.available)
            ram_percent = ram_info.percent
            disk_usage = await asyncio.to_thread(psutil.disk_usage, '/')
            total_disk = humanbytes(disk_usage.total)
            used_disk = humanbytes(disk_usage.used)
            free_disk = humanbytes(disk_usage.free)
            disk_percent = disk_usage.percent
            total_users = await db.total_users_count()
            
            stats_text = (
                "<blockquote>📊 <b>Bot System Statistics</b>\n\n"
                f"👥 <b>Total Users:</b> <code>{total_users}</code>\n\n"
                f"⏰ <b>System Uptime:</b> <code>{sys_uptime_str}</code>\n"
                f"🤖 <b>Bot Uptime:</b> <code>{bot_uptime_str}</code>\n\n"
                f"⚙️ <b>CPU Usage:</b> <code>{cpu_percent}%</code>\n"
                f"🔢 <b>CPU Cores:</b> <code>{cpu_cores if cpu_cores else 'N/A'}</code>\n"
                f"⚡ <b>CPU Frequency:</b> <code>{cpu_freq_ghz}</code>\n\n"
                f"🧠 <b>RAM Usage:</b> <code>{ram_used} / {ram_total}</code> (<code>{ram_percent}%</code>)\n"
                f"💚 <b>RAM Free:</b> <code>{ram_free}</code>\n\n"
                f"💾 <b>Disk Usage:</b> <code>{used_disk} / {total_disk}</code> (<code>{disk_percent}%</code>)\n"
                f"📁 <b>Disk Free:</b> <code>{free_disk}</code>\n\n"
                f"📤 <b>Upload:</b> <code>{humanbytes(net_io_counters.bytes_sent)}</code>\n"
                f"📥 <b>Download:</b> <code>{humanbytes(net_io_counters.bytes_recv)}</code>\n\n"
                "🚀 <b>Status:</b> Bot running smoothly!</blockquote>"
            )
            
            await callback_query.message.edit_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")],
                    [InlineKeyboardButton("❌ Close", callback_data="close_stats")]
                ])
            )
            
        except Exception as e:
            import logging
            logging.error(f"Stats refresh error: {e}", exc_info=True)
            await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)

# VIDEO SENDING HOW IT WORKS
@Client.on_message(filters.private & filters.command("how"))
async def send_two_videos(client, message):
    # First video
    try:
        await client.send_video(
            chat_id=message.chat.id,
            video="plugins/testvideo/vid1.mp4",
            caption="Look this !!!"
        )
    except Exception as e:
        import logging
        logging.error(f"Error sending video: {e}")
        await message.reply_text(f"❌ Error sending video: {str(e)}")

# RESTART BOT COMMAND
@Client.on_message(filters.command("restart") & filters.private)
async def restart_bot(client, message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("❌ You are not authorized.")
    
    await message.reply_text("♻️ <b>Bot is restarting...</b>")
    os.execv(sys.executable, ['python3'] + sys.argv)
