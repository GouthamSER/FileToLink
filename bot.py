import sys, glob, importlib, logging, logging.config, pytz, asyncio, os, signal
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
from lib.bot.clients import initialize_clients, stop_clients
from lib.util.custom_dl import cancel_all_producers

# ================= CONFIG =================
ppath = "plugins/*.py"
files = glob.glob(ppath)

RESTART_INTERVAL = 6 * 60 * 60  # 12 Hours

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
        hours = RESTART_INTERVAL // 3600

        await File2Link.send_message(
            chat_id=LOG_CHANNEL,
            text=(
                "♻️ <b>Auto Restart Triggered</b>\n\n"
                f"⏰ Time: <code>{now}</code>\n"
                f"🕕 Interval: <code>{hours} Hours</code>"
            )
        )
    except Exception as e:
        logging.error(f"Restart message failed: {e}")
    logging.info(f"Restarting bot after {RESTART_INTERVAL // 3600} hours")

    # Previously this called os.execv(), which replaces the process image
    # in place and completely SKIPS our SIGTERM shutdown handling below —
    # every multi-client MTProto connection got killed uncleanly instead
    # of properly logged out, every 12h. Send our own SIGTERM instead: it
    # runs through the exact same graceful shutdown path a platform
    # restart uses (stop_clients, cancel in-flight streams, close the
    # aiohttp server), then exits 0 — Heroku/Koyeb/Render's process
    # supervisor (the `web: python bot.py` Procfile entry) restarts it
    # automatically, same as it does on any clean exit.
    os.kill(os.getpid(), signal.SIGTERM)

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

    app_runner = web.AppRunner(await web_server())
    await app_runner.setup()
    await web.TCPSite(app_runner, "0.0.0.0", PORT).start()

    # ================= AUTO RESTART CHECK =================
    if AUTO_RESTART:
        hours = RESTART_INTERVAL // 3600
        msg = f"Auto Restart: ON | Interval: {hours} Hours"
        print(f"🔄 {msg}")
        logging.info(msg)
        asyncio.create_task(auto_restart())
    else:
        msg = "Auto Restart: OFF"
        print(f"⏸️ {msg}")
        logging.info(msg)
    # ======================================================

    # selfping
    asyncio.create_task(self_ping_task())

    await idle()

    # ================= GRACEFUL SHUTDOWN =================
    # idle() returns once SIGINT/SIGTERM is received. Platforms like
    # Heroku (R12), Koyeb, and Render only give ~30s (some less) between
    # SIGTERM and a hard SIGKILL. Without explicit cleanup, open MTProto
    # sockets (multi-client), in-flight stream tasks, and the aiohttp
    # server can keep the process alive past that window -> force-killed
    # instead of exiting clean. Bound the whole thing so we never eat the
    # full grace period ourselves.
    logging.info("Shutdown signal received, cleaning up...")
    try:
        await asyncio.wait_for(_shutdown(app_runner), timeout=20)
    except asyncio.TimeoutError:
        logging.warning("Graceful shutdown exceeded 20s, exiting anyway.")
    logging.info("Shutdown complete. Bye 👋")


async def _shutdown(app_runner: web.AppRunner):
    # Stop accepting/serving first so no new stream requests start mid-cleanup.
    try:
        await app_runner.cleanup()
    except Exception:
        logging.error("Error during aiohttp cleanup", exc_info=True)

    try:
        await cancel_all_producers()
    except Exception:
        logging.error("Error cancelling stream producers", exc_info=True)

    try:
        await stop_clients()
    except Exception:
        logging.error("Error stopping Pyrogram clients", exc_info=True)

# ================= RUN =================
if __name__ == "__main__":
    try:
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logging.info("Service Stopped Bye 👋")
    finally:
        # Let any cancelled tasks unwind before the loop itself closes,
        # otherwise their cleanup can be cut off mid-way (same class of
        # issue as the shutdown handling above).
        try:
            pending = asyncio.all_tasks(loop=loop)
            for t in pending:
                t.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()
