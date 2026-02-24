import re
import os

id_pattern = re.compile(r'^\d+$')

# ===============================
# Bot Information
# ===============================
SESSION = os.environ.get('SESSION', '')
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')

# ===============================
# Bot Settings
# ===============================
PORT = os.environ.get("PORT", "8080")
MULTI_CLIENT = False
SLEEP_THRESHOLD = int(os.environ.get('SLEEP_THRESHOLD', '60'))
PING_INTERVAL = int(os.environ.get("PING_INTERVAL", "1200"))  # in seconds
ON_HEROKU = 'DYNO' in os.environ
URL = os.environ.get("URL", "")

# ===============================
# Admins, Channels & Users
# ===============================
LOG_CHANNEL = int(os.environ.get('LOG_CHANNEL', '0'))
ADMINS = [
    int(admin) if id_pattern.match(admin) else admin
    for admin in os.environ.get('ADMINS', '').split()
]


# ===============================
# MongoDB
# ===============================
DATABASE_URI = os.environ.get('DATABASE_URI', "")
DATABASE_NAME = os.environ.get('DATABASE_NAME', "")

# ===============================
# Shortlink Info
# ===============================
SHORTLINK = os.environ.get('SHORTLINK', 'False').lower() == 'true'
SHORTLINK_URL = os.environ.get('SHORTLINK_URL', '')
SHORTLINK_API = os.environ.get('SHORTLINK_API', '')
