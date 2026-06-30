# FileToLink

Telegram bot that turns any file you send into a direct download / streaming link. Built on Pyrogram (pyrotgfork) + aiohttp, with MongoDB for user tracking.

## Features
- Instant direct-download links for any file
- In-browser video/audio streaming page (range-request support, resumable)
- Force-subscribe gate (optional)
- Shortlink support (is.gd or Shortzy-based: gplinks, mdisk, etc.)
- Multi-client mode for higher throughput (extra bot tokens)
- Admin `/stats` panel, `/broadcast`, `/restart`
- Auto-restart every 3h + auto-restart on network errors
- Self-ping keepalive for free-tier hosts (Heroku/Koyeb)

## Stack
- Python 3.11
- Pyrogram (pyrotgfork) + TgCrypto
- aiohttp (web server + streaming)
- MongoDB (motor)
- Docker (deploy target: Koyeb)

## Setup

1. Install deps:
   ```
   pip install -r requirements.txt
   ```

2. Set env vars (required ones will hard-fail with a clear error if missing):

   | Var | Required | Description |
   |---|---|---|
   | `API_ID` | yes | from my.telegram.org |
   | `API_HASH` | yes | from my.telegram.org |
   | `BOT_TOKEN` | yes | from @BotFather |
   | `LOG_CHANNEL` | yes | private channel id used as file storage backend |
   | `DATABASE_URI` | yes | MongoDB connection string |
   | `DATABASE_NAME` | yes | MongoDB db name |
   | `URL` | yes | public base URL of this deployment (e.g. `https://yourapp.koyeb.app/`) |
   | `ADMINS` | no | space-separated admin user IDs |
   | `FSUB_CHANNEL` | no | force-subscribe channel id (0 = disabled) |
   | `PORT` | no | default `8080` |
   | `SLEEP_THRESHOLD` | no | default `60` |
   | `PING_INTERVAL` | no | self-ping interval seconds, default `1200` |
   | `SHORTLINK` | no | `True`/`False`, use Shortzy-based shortener |
   | `SHORTLINK_URL` / `SHORTLINK_API` | no | required if `SHORTLINK=True` |
   | `ISGD` | no | `True`/`False`, use is.gd shortener (no key needed) |
   | `MULTI_TOKEN1`, `MULTI_TOKEN2`, ... | no | extra bot tokens for multi-client load balancing |

3. Run:
   ```
   python bot.py
   ```

   Or with Docker:
   ```
   docker build -t filetolink .
   docker run -p 8080:8080 --env-file .env filetolink
   ```

## How it works

User sends a file → bot forwards it to `LOG_CHANNEL` → bot replies with a stream link (`/watch/<id>/<name>?hash=...`) and a download link (`/<id>/<name>?hash=...`). The aiohttp server pulls the file from Telegram on-demand in 1MB chunks via a custom `ByteStreamer`, with per-DC media session locking and chunk-prefetch pipelining for speed, and supports HTTP Range requests so downloads/streams resume cleanly.

## Project layout

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

## Notes
- `LOG_CHANNEL` must be a channel/group the bot is admin in — it's used as permanent file storage, not just a log.
- Links are hash-protected (first 6 chars of the file's `unique_id`) so IDs can't be brute-forced sequentially.

## Fixes in this build
- Download page (`dl.html`) used Python `%s` placeholders but was rendered with jinja2 — page showed literal `%s` everywhere instead of filename/link/size. Fixed.
- Download page render was making a full self-HTTP GET just to read a `Content-Length` header (streaming the whole file pointlessly). Removed; uses the already-known file size.
- `MULTI_CLIENT` flag was set on a local variable and never actually reached the route handler — multi-client logging never triggered. Route now checks live client count instead.
- `error_detection.py`'s `detect_error()` (auto-restart on network errors) was defined but never called anywhere. Hooked into the route handlers' exception path.
- `info.py` crashed with a bare `ValueError` traceback if `API_ID`/`LOG_CHANNEL` env vars were missing. Now exits with a clear message.
