import re
from os import environ

id_pattern = re.compile(r'^.\d+$')

# Bot information
SESSION = environ.get('SESSION', '')
API_ID = int(environ.get('API_ID', ''))
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', "")

# Bot settings
PORT = environ.get("PORT", "8080")

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
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', ''))
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '').split()]

# ===============================
# Force Subscribe Configuration
# ===============================

# Multiple channels → separate by comma for usernames / IDs
FORCE_SUB_CHANNELS = [
    ch if not ch.isdigit() else int(ch) 
    for ch in os.environ.get("FORCE_SUB_CHANNELS", "").split(",") if ch
]

# Private channels invite links (channel ID: invite URL)
# Example format: -1001234567890=https://t.me/+abcdEFGH1234,-1009876543210=https://t.me/+xyz123
INVITE_LINKS = {}
for pair in os.environ.get("INVITE_LINKS", "").split(","):
    if "=" in pair:
        k, v = pair.split("=")
        INVITE_LINKS[int(k)] = v

# Auto delete time (seconds)
AUTO_DELETE_TIME = int(os.environ.get("AUTO_DELETE_TIME", 30))

# MongoDB information
DATABASE_URI = environ.get('DATABASE_URI', "")
DATABASE_NAME = environ.get('DATABASE_NAME', "")

# Shortlink Info
SHORTLINK = bool(environ.get('SHORTLINK', False)) # Set True Or False
SHORTLINK_URL = environ.get('SHORTLINK_URL', '')
SHORTLINK_API = environ.get('SHORTLINK_API', '')
