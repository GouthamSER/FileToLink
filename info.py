import re
from os import environ

id_pattern = re.compile(r'^.\d+$')

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
AUTO_RESTART = os.environ.get("AUTO_RESTART", "True").lower() in ["true", "1", "yes"]

# Online Stream and Download
MULTI_CLIENT = False
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  #2min in seconds
if 'DYNO' in environ:
    ON_HEROKU = True
else:
    ON_HEROKU = False
URL = environ.get("URL", "")

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
