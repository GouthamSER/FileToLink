import re
import urllib.parse
from os import environ

id_pattern = re.compile(r'^\d+$')

# Bot information
SESSION = environ.get('SESSION', '')
API_ID = int(environ.get('API_ID') or 0)
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit(
        "Missing required env vars: API_ID, API_HASH, BOT_TOKEN must all be set."
    )

# Bot settings
PORT = int(environ.get("PORT", "8080"))

# Returns True if set to "True", "true", "1", or "yes". Otherwise False.
AUTO_RESTART = environ.get("AUTO_RESTART", "True").lower() in ["true", "1", "yes"]

# Online Stream and Download
MULTI_CLIENT = True
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '14'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  #2min in seconds
if 'DYNO' in environ:
    ON_HEROKU = True
else:
    ON_HEROKU = False
URL = environ.get("URL", "")
if URL:
    # Auto-fix a common misconfiguration: someone pastes a health-check or
    # other sub-path URL (e.g. "https://app.koyeb.app/health/") into this
    # var instead of the bare app root. Every generated download/stream
    # link is built as f"{URL}{id}?hash=...", so any extra path segment
    # here makes EVERY single link 404 with no obvious cause. Strip down
    # to scheme+host and force exactly one trailing slash so that class of
    # mistake can't silently break every link again.
    _parsed = urllib.parse.urlparse(URL if "://" in URL else f"https://{URL}")
    URL = f"{_parsed.scheme}://{_parsed.netloc}/"

# Admins, Channels & Users
LOG_CHANNEL = int(environ.get('LOG_CHANNEL') or 0)
if not LOG_CHANNEL:
    raise SystemExit("Missing required env var: LOG_CHANNEL must be set.")
ADMINS = [int(admin) if id_pattern.search(admin) else admin for  admin in environ.get('ADMINS', '').split()]
FSUB_CHANNEL = int(environ.get('FSUB_CHANNEL', '0')) #public channel id -232859845

# MongoDB information
DATABASE_URI = environ.get('DATABASE_URI', "")
DATABASE_NAME = environ.get('DATABASE_NAME', "")

#FREE SHORTNER
ISGD = environ.get('ISGD', 'False').strip().lower() in ('true', '1', 'yes')

# Shortlink Info
SHORTLINK = environ.get('SHORTLINK', 'False').strip().lower() in ('true', '1', 'yes')
SHORTLINK_URL = environ.get('SHORTLINK_URL', '')
SHORTLINK_API = environ.get('SHORTLINK_API', '')
