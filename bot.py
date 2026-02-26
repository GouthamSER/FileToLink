import sys, glob, importlib, logging, logging.config, pytz, asyncio, os
from pathlib import Path
from datetime import date, datetime
from plugins.selfping import self_ping_task # selfping from plugin

# ================= LOGGING =================
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)

# ================= IMPORTS =================
from pyrogram import idle
from aiohttp import web

from database.users_chats_db import db
from info import *
from utils import temp
from Script import script
from plugins import web_server

from lib.bot import File2Link
from lib.util.keepalive import ping_server
from lib.bot.clients import initialize_clients

# ================= CONFIG =================
ppath = "plugins/*.py"
files = glob.glob(ppath)

RESTART_INTERVAL = 3 * 60 * 60  # 3 Hours

loop = asyncio.get_event_loop()

# ================= BANNER =================
def print_banner():
    banner = """
████ █ ████ File 2 Link ™ ████ █ ████ 
    """
    print(banner)

# ================= AUTO RESTART =================
async def auto_restart():
    await asyncio.sleep(RESTART_INTERVAL)

    try:
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz).strftime("%d-%m-%Y | %I:%M:%S %p")

        await File2Link.send_message(
            chat_id=LOG_CHANNEL,
            text=(
                "♻️ <b>Auto Restart Triggered</b>\n\n"
                f"⏰ Time: <code>{now}</code>\n"
                "🕕 Interval: <code>3 Hours</code>"
            )
        )
    except Exception as e:
        logging.error(f"Restart message failed: {e}")
    logging.info("Restarting bot after 3 hours")

    # Restart bot using python3 bot.py
    os.execv(sys.executable, ["python3", "bot.py"])

# ================= MAIN =================
async def start():
    print("\n")
    print_banner()
    print("\nInitializing Your Bot...\n")

    # FIX: Started the client properly inside the async function
    await File2Link.start()

    bot_info = await File2Link.get_me()
    await initialize_clients()

    # Load Plugins
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = f"plugins.{plugin_name}"

            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules[import_path] = load

            print(f"File2Link Imported => {plugin_name}")

    if ON_HEROKU:
        asyncio.create_task(ping_server())

    # Save bot details
    me = await File2Link.get_me()
    temp.BOT = File2Link
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name

    # Restart Message
    tz = pytz.timezone("Asia/Kolkata")
    today = date.today()
    now = datetime.now(tz).strftime("%I:%M:%S %p")

    await File2Link.send_message(
        chat_id=LOG_CHANNEL,
        text=script.RESTART_TXT.format(today, now)
    )

    app = web.AppRunner(await web_server())
    await app.setup()
    await web.TCPSite(app, "0.0.0.0", PORT).start()

    # Start Auto Restart Task
    asyncio.create_task(auto_restart())

    # selfping
    asyncio.create_task(self_ping_task())
    
    await idle()

# ================= RUN =================
if __name__ == "__main__":
    try:
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logging.info("Service Stopped Bye 👋")

