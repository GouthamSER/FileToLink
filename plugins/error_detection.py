# plugins/error_detection.py

import os
import sys
import asyncio
import logging
from datetime import datetime
import pytz

from lib.bot import File2Link
from info import LOG_CHANNEL

# Errors commonly seen on Koyeb / upstream proxies
RESTART_ERRORS = (
    "upstream connect error",
    "connection reset",
    "connection aborted",
    "server disconnected",
    "server closed the connection",
    "network is unreachable",
    "socket error",
    "read timeout",
    "write timeout",
    "timeout error",
    "aiohttp.client_exceptions",
)

RESTART_COOLDOWN = 300  # 5 minutes
_last_restart = 0


async def restart_bot(reason: str):
    global _last_restart
    now_ts = asyncio.get_event_loop().time()

    # Prevent restart loop
    if now_ts - _last_restart < RESTART_COOLDOWN:
        logging.warning("Restart skipped (cooldown active)")
        return

    _last_restart = now_ts

    try:
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz).strftime("%d-%m-%Y | %I:%M:%S %p")

        await File2Link.send_message(
            chat_id=LOG_CHANNEL,
            text=(
                "🚨 <b>Critical Network Error</b>\n\n"
                f"🧩 Reason: <code>{reason}</code>\n"
                f"⏰ Time: <code>{now}</code>\n"
                "🔄 Action: <code>Auto Restart</code>"
            )
        )
    except Exception as e:
        logging.error(f"Failed to send restart log: {e}")

    await asyncio.sleep(2)
    os.execv(sys.executable, [sys.executable, "bot.py"])


async def detect_error(error: Exception, context: str = "Unknown"):
    error_text = str(error).lower()

    if any(err in error_text for err in RESTART_ERRORS):
        logging.error(f"[AUTO-RESTART] {context}: {error}")
        await restart_bot(context)
