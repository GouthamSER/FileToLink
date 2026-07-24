<div align="center">

# 🔗 FileToLink

**Send a file → get an instant streaming + download link.**

![Python](https://img.shields.io/badge/python-3.11-blue)
![Pyrogram](https://img.shields.io/badge/pyrogram-pyrotgfork-2CA5E0)
![aiohttp](https://img.shields.io/badge/server-aiohttp-orange)
![MongoDB](https://img.shields.io/badge/db-MongoDB-4DB33D)
![Docker](https://img.shields.io/badge/deploy-Docker%2FKoyeb-0db7ed)

</div>
<hr>
<div align="center">
<h3>Deploy To Various Platforms :)</h3>
<br>
      
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/GouthamSER/FileToLink)
[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/GouthamSER/FileToLink&branch=main&builder=dockerfile)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/GouthamSER/FileToLink)

</div>

---

<h2 align="center">✨ Features</h2>

- ⚡ Instant direct-download links for any file
- 🎬 In-browser video/audio streaming page — full HTTP Range support, resumable
- 🔒 Force-subscribe gate (optional)
- 🔗 Shortlink support — is.gd or Shortzy-based (gplinks, mdisk, etc.)
- 🚀 Multi-client mode for higher throughput with extra bot tokens
- 🛠️ Admin tools — `/stats`, `/broadcast`, `/restart`
- ♻️ Auto-restart every 3h, plus auto-restart on network errors
- 💓 Self-ping keepalive for free-tier hosts (Heroku/Koyeb)

<h2 align="center">🧱 Stack</h2>

| | |
|---|---|
| Runtime | Python 3.11 |
| Telegram | Pyrogram (pyrotgfork) + TgCrypto |
| Server | aiohttp (web server + chunked streaming) |
| Database | MongoDB (motor) |
| Deploy | Docker → Koyeb |

<h2 align="center">🚀 Setup</h2>

**1. Install deps**
```bash
pip install -r requirements.txt
```

**2. Set environment variables**

Required vars hard-fail with a clear error message if missing — no more cryptic tracebacks.

| Var | Required | Description |
|---|:---:|---|
| `API_ID` | ✅ | from my.telegram.org |
| `API_HASH` | ✅ | from my.telegram.org |
| `BOT_TOKEN` | ✅ | from @BotFather |
| `LOG_CHANNEL` | ✅ | private channel id used as file storage backend |
| `DATABASE_URI` | ✅ | MongoDB connection string |
| `DATABASE_NAME` | ✅ | MongoDB db name |
| `URL` | ✅ | public base URL of this deployment, e.g. `https://yourapp.koyeb.app/` |
| `ADMINS` | – | space-separated admin user IDs |
| `FSUB_CHANNEL` | – | force-subscribe channel id (`0` = disabled) |
| `PORT` | – | default `8080` |
| `SLEEP_THRESHOLD` | – | default `60` |
| `PING_INTERVAL` | – | self-ping interval in seconds, default `1200` |
| `SHORTLINK` | – | `True`/`False`, use Shortzy-based shortener |
| `SHORTLINK_URL` / `SHORTLINK_API` | – | required if `SHORTLINK=True` |
| `ISGD` | – | `True`/`False`, use is.gd shortener (no key needed) |
| `MULTI_TOKEN1`, `MULTI_TOKEN2`, ... | – | extra bot tokens for multi-client load balancing |

**3. Run**
```bash
python bot.py
```

Or with Docker:
```bash
docker build -t filetolink .
docker run -p 8080:8080 --env-file .env filetolink
```

<h2 align="center">⚙️ How it works</h2>

```
User sends file
      │
      ▼
Bot forwards file → LOG_CHANNEL
      │
      ▼
Bot replies with:
  • Stream link  → /watch/<id>/<name>?hash=...
  • Download link → /<id>/<name>?hash=...
      │
      ▼
aiohttp pulls file from Telegram on-demand,
1MB chunks, per-DC locked sessions,
prefetch-pipelined, Range-aware → resumable
```

<h2 align="center">📁 Project layout</h2>

```
bot.py                       entrypoint, plugin loader, auto-restart
info.py                      env var config
Script.py                    bot text templates
utils.py                     shortlink helper, temp state
database/                    MongoDB user store
lib/bot/                     Pyrogram client + multi-client manager
lib/util/custom_dl.py        chunked file streaming from Telegram
lib/util/render_template.py  renders download/stream HTML pages
lib/template/                dl.html (download page), req.html (player page)
lib/server/exceptions.py     InvalidHash / FIleNotFound
plugins/                     command handlers (start, route, broadcast, stats, etc.)
```

<h2 align="center">📝 Notes</h2>

- `LOG_CHANNEL` must be a channel/group the bot is admin in — it's permanent file storage, not just a log.
- Links are hash-protected (first 6 chars of the file's `unique_id`) so IDs can't be brute-forced sequentially.

<h2 align="center">🩹 Fixes in this build</h2>

| Bug | Fix |
|---|---|
| `dl.html` used Python `%s` placeholders but was rendered via jinja2 → page showed literal `%s` instead of filename/link/size | Switched to `{{var}}` jinja2 syntax |
| Download page render made a full self-HTTP `GET` just to read a `Content-Length` header — streamed the whole file for nothing | Removed; reuses the already-known file size |
| `MULTI_CLIENT` flag was set on a local var and never reached the route handler — multi-client logging never fired | Route now checks live client count directly |
| `detect_error()` (auto-restart on network errors) was defined but never called anywhere | Hooked into the route handlers' exception path |
| `info.py` crashed with a bare `ValueError` traceback if `API_ID`/`LOG_CHANNEL` were missing | Now exits with a clear error message |
| Every plugin handler ran **twice** — Client was set to auto-load `plugins/` (pyrogram's `plugins={"root":"plugins"}`) *and* `bot.py` manually re-imported every file in `plugins/*.py` | Removed the auto-load, kept only the manual loader → `/start`, stream links, `/stats`, `/broadcast` etc. now fire once |
| `info.py`'s `id_pattern` regex (`^.\d+$`) failed to match single-digit admin IDs | Fixed to `^\d+$` |

<h2 align="center">👤 Maintainer</h2>

<p align="center"><b>Goutham</b> — <a href="https://github.com/GouthamSER">@GouthamSER</a></p>
