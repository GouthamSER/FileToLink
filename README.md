<div align="center">

<img src="https://i.ibb.co/KzqHfL05/photo-2026-02-07-13-38-13.jpg" width="96" height="96" alt="File Stream Bot logo">

# 📡 File Stream Bot™

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
- 🎬 In-browser video/audio streaming page — full HTTP Range support, resumable, cinema-style UI
- 🎧 Audio track switching (multi-track AAC/AC3/Opus files) via native browser `audioTracks` API
- 💬 Subtitle support — load external `.srt`/`.vtt` client-side, toggle on/off
- 🔗 Short links — `/watch/<hash+id>` and `/dl/<hash+id>`, no filename or query string exposed in the shareable URL
- 🔒 Force-subscribe gate (optional)
- 🔗 Shortlink support — is.gd or Shortzy-based (gplinks, mdisk, etc.)
- 🚀 Multi-client mode for higher throughput with extra bot tokens (`MULTI_TOKEN1..N`)
- ⏩ Per-stream parallel chunk prefetch (`CONCURRENT_FETCHES`) — faster single-stream speed, not just more concurrent viewers
- ♻️ Auto-retry on transient Telegram RPC errors (`-503 Timeout` etc.) and FloodWait, instead of killing the stream
- 🧹 Graceful shutdown on SIGTERM — stops all clients + in-flight streams cleanly within the platform's grace window (fixes Heroku R12 / forced SIGKILL)
- 🛠️ Admin tools — `/stats`, `/broadcast`, `/restart`
- ♻️ Auto-restart every 12h, plus auto-restart on network errors
- 💓 Self-ping keepalive for free-tier hosts (Heroku/Koyeb/Render)

<h2 align="center">🧱 Stack</h2>

| | |
|---|---|
| Runtime | Python 3.11 |
| Telegram | Pyrogram (pyrotgfork) + TgCrypto |
| Server | aiohttp (web server + chunked streaming) |
| Database | MongoDB (motor) |
| Deploy | Docker → Koyeb / Heroku / Render |

<h2 align="center">🚀 Setup</h2>

**1. Install deps**
```bash
pip install -r requirements.txt
```

**2. Set environment variables**

Required vars hard-fail with a clear error message if missing — no more cryptic tracebacks.

| Var | Required | Description |
|---|:---:|---|
| `API_ID` | ✅ | from my.telegram.org — shared across ALL bot tokens, including `MULTI_TOKEN*` |
| `API_HASH` | ✅ | from my.telegram.org — same, shared |
| `BOT_TOKEN` | ✅ | main bot, from @BotFather |
| `LOG_CHANNEL` | ✅ | private channel used as file storage backend — every bot token (main + multi) must be admin here |
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
| `MULTI_TOKEN1`, `MULTI_TOKEN2`, ... | – | extra bot tokens for multi-client load balancing — tokens can come from separate Telegram accounts (BotFather caps 20 bots/account), just add each new bot as admin in `LOG_CHANNEL` |

**3. Run**
```bash
python bot.py
```

Or with Docker:
```bash
docker build -t filestreambot .
docker run -p 8080:8080 --env-file .env filestreambot
```

<h2 align="center">⚙️ How it works</h2>

```
User sends file
      │
      ▼
Bot forwards file → LOG_CHANNEL
      │
      ▼
Bot replies with short links:
  • Stream link   → /watch/<hash+id>
  • Download link → /dl/<hash+id>
      │
      ▼
Page resolves hash+id → serves req.html (player) or dl.html (download),
video/download button points at the raw byte-stream endpoint
      │
      ▼
aiohttp pulls file from Telegram on-demand,
1MB chunks, 2 fetched in parallel per stream,
per-DC locked sessions, Range-aware → resumable,
auto-retries on FloodWait / transient Telegram errors
```

<h2 align="center">📊 Sizing multi-client</h2>

- Each `MULTI_TOKEN` client ≈ comfortably serves 3-5 concurrent full-speed streams before Telegram FloodWaits it.
- Rule of thumb: `tokens_needed ≈ peak_concurrent_viewers / 4`
- Each live client ≈ 25-40MB RAM — on a 512MB dyno, **7-8 clients is the realistic ceiling**; going higher risks Heroku R14 (memory) and R12 (SIGKILL on shutdown) errors. Upgrade dyno RAM before adding more tokens past that.

<h2 align="center">📁 Project layout</h2>

```
bot.py                       entrypoint, plugin loader, auto-restart, graceful shutdown
info.py                      env var config
Script.py                    bot text templates
utils.py                     shortlink helper, temp state
database/                    MongoDB user store
lib/bot/clients.py           multi-client manager — start + graceful stop_clients()
lib/util/custom_dl.py        chunked file streaming from Telegram, retry logic, parallel prefetch
lib/util/render_template.py  renders download/stream HTML pages
lib/template/                req.html (player page), dl.html (download page)
lib/server/exceptions.py     InvalidHash / FIleNotFound
plugins/route.py             /watch, /dl, and raw byte-stream routes
plugins/                     command handlers (start, route, broadcast, stats, etc.)
```

<h2 align="center">📝 Notes</h2>

- `LOG_CHANNEL` must be a channel/group every bot token (main + all `MULTI_TOKEN*`) is admin in — it's permanent file storage, not just a log.
- Short links are hash-protected (first 6 chars of the file's `unique_id`) so IDs can't be brute-forced sequentially — no database lookup needed for link resolution.
- DTS/DTS-HD/TrueHD audio tracks won't play in-browser regardless of what's in the file — no browser ships a decoder for them, that's a licensing wall, not a bug.

<h2 align="center">🩹 Changelog</h2>

| Fix | Detail |
|---|---|
| Heroku R12 (Exit timeout / SIGKILL) | Added graceful shutdown: on SIGTERM, stops aiohttp server, cancels in-flight stream tasks, stops every Pyrogram client within a bounded 20s window |
| `dict(clients)` crash on any failed multi-client token | `initialize_clients()` now skips failed tokens instead of crashing the whole multi-client pool |
| `GeneratorExit` / "coroutine ignored" spam on client disconnect | Prefetch producer now stops cooperatively instead of being hard-cancelled mid-fetch; strong-ref set prevents early GC of pending tasks |
| Stream died instantly on `[-503 Timeout]` / transient Telegram RPC errors | Now retried with backoff, same as FloodWait |
| Slow single-stream speed | Chunks fetched 2-at-a-time per stream (`CONCURRENT_FETCHES`) instead of strictly sequential |
| Downloaded filename sometimes corrupted (`+` vs space) | URL path now uses `quote()` not `quote_plus()`; `download=` attribute also forces the exact real filename client-side |
| `dl.html` used Python `%s` placeholders but was rendered via jinja2 | Switched to `{{var}}` jinja2 syntax |
| Download page render made a full self-HTTP `GET` just to read `Content-Length` | Removed; reuses the already-known file size |
| `MULTI_CLIENT` flag never reached the route handler | Route now checks live client count directly |
| `detect_error()` defined but never called | Hooked into route handlers' exception path |
| `info.py` crashed with a bare `ValueError` if required vars missing | Now exits with a clear error message |
| Every plugin handler ran **twice** (double plugin load) | Removed auto-load, kept only the manual loader |
| `info.py`'s `id_pattern` failed on single-digit admin IDs | Fixed regex |

<h2 align="center">👤 Maintainer</h2>

<p align="center"><b>Goutham</b> — <a href="https://github.com/GouthamSER">@GouthamSER</a></p>
