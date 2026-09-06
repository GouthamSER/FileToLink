<div align="center">

<img src="https://i.ibb.co/KzqHfL05/photo-2026-02-07-13-38-13.jpg" width="96" height="96" alt="File 2 Link logo">

# 📡 File 2 Link ™

**Send a file → get an instant streaming + download link.**

![Python](https://img.shields.io/badge/python-3.11-blue)
![Pyrogram](https://img.shields.io/badge/pyrogram-pyrofork-2CA5E0)
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
- 🎬 In-browser video/audio streaming page — full HTTP Range support, resumable, cinema-style UI, native `<video controls>` (no bundled player library)
- 🎧 Audio track switching (multi-track AAC/AC3/Opus files) via native browser `audioTracks` API — honest limits noted in-app (Firefox/Safari can't expose it at all; DTS/TrueHD can't decode in any browser)
- 💬 Subtitles — load external `.srt`/`.vtt` client-side, toggle on/off
- ℹ️ VLC-style media info panel — resolution, duration, track count, playback rate
- 🗑️ **Revoke button** on every generated link — uploader (or admin) can delete the file from `LOG_CHANNEL` on demand, instantly killing both the stream and download link. Two-step confirm so a stray tap can't nuke a file.
- 🔒 Force-subscribe gate (optional)
- 🔗 Shortlink support — is.gd or Shortzy-based (gplinks, mdisk, etc.)
- 🚀 Multi-client mode for higher throughput with extra bot tokens (`MULTI_TOKEN1..N`)
- ⏩ Per-stream parallel chunk prefetch (`CONCURRENT_FETCHES`) — faster single-stream speed, not just more concurrent viewers
- ⚖️ Atomic load-balancer reservation — client pick + slot reservation happen with no `await` gap between them, so a burst of parallel connections (download accelerators like FDM open several at once) can't all pile onto the same client
- 🩹 Auto-fallback if the load-balanced client can't read `LOG_CHANNEL` (e.g. missing admin rights) — retries with the main client instead of a random "file not found"
- ♻️ Auto-retry on transient Telegram RPC errors (`-503 Timeout` etc.) and FloodWait, instead of killing the stream
- 🧹 Graceful shutdown on SIGTERM — stops all clients + in-flight streams cleanly within the platform's grace window (fixes Heroku R12 / forced SIGKILL); the 12h auto-restart routes through this same path instead of a dirty `execv`
- 🗄️ Compiled-template caching — HTML pages are parsed once per process, not re-read/recompiled on every page view
- 🛠️ Admin tools — `/stats`, `/broadcast`, `/restart`
- 💓 Self-ping keepalive for free-tier hosts (Heroku/Koyeb/Render)

<h2 align="center">🧱 Stack</h2>

| | |
|---|---|
| Runtime | Python 3.11 |
| Telegram | Pyrogram fork: `pyrofork` + `TgCrypto-pyrofork` |
| Server | aiohttp (web server + chunked streaming) |
| Database | MongoDB (motor) |
| Deploy | Docker → Koyeb / Heroku / Render |

<h2 align="center">🚀 Setup</h2>

**1. Install deps**
```bash
pip install -r requirements.txt
```

**2. Set environment variables**

Required vars hard-fail with a clear error message if missing.

| Var | Required | Description |
|---|:---:|---|
| `API_ID` | ✅ | from my.telegram.org — shared across ALL bot tokens, including `MULTI_TOKEN*` |
| `API_HASH` | ✅ | from my.telegram.org — same, shared |
| `BOT_TOKEN` | ✅ | main bot, from @BotFather |
| `LOG_CHANNEL` | ✅ | private channel used as file storage backend — every bot token (main + multi) must be admin here |
| `DATABASE_URI` | ✅ | MongoDB connection string |
| `DATABASE_NAME` | ✅ | MongoDB db name |
| `URL` | ✅ | public base URL of this deployment. Any extra path accidentally pasted in (e.g. a health-check URL) is auto-stripped down to scheme+host — but set it clean anyway: `https://yourapp.koyeb.app/` |
| `ADMINS` | – | space-separated admin user IDs — also who can `/broadcast`, `/restart`, and revoke *anyone's* file link |
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
docker build -t file2link .
docker run -p 8080:8080 --env-file .env file2link
```

<h2 align="center">💬 Bot usage</h2>

| Who | Action |
|---|---|
| Anyone | Send any file in DM → get Stream + Download + Revoke buttons back |
| Anyone | `/start`, `/how` |
| Admins (`ADMINS`) | `/stats`, `/broadcast` (reply to a message), `/restart` |
| Uploader or admin | Tap **🗑 Revoke Link** on a generated message → confirm → file deleted from `LOG_CHANNEL`, links dead instantly |

<h2 align="center">⚙️ How it works</h2>

```
User sends file
      │
      ▼
Bot forwards file → LOG_CHANNEL
      │
      ▼
Bot replies with:
  • Stream link   → /watch/{id}/{filename}?hash=X
  • Download link → /{id}/{filename}?hash=X
  • 🗑 Revoke Link button
      │
      ▼
Page resolves id+hash → serves req.html (player) or dl.html (download),
templates compiled once and cached — not re-parsed per request
      │
      ▼
aiohttp pulls file from Telegram on-demand,
1MB chunks, several fetched in parallel per stream (CONCURRENT_FETCHES),
client pick + load-balancer reservation done atomically (no await gap),
per-DC locked sessions, Range-aware → resumable,
auto-retries on FloodWait / transient Telegram errors
```

<h2 align="center">📊 Real-world sizing (not theoretical)</h2>

- Each `MULTI_TOKEN` client ≈ comfortably serves 3-5 concurrent full-speed streams before Telegram FloodWaits it. Rule of thumb: `tokens_needed ≈ peak_concurrent_viewers / 4`.
- Each live client ≈ 25-40MB RAM. **On a 512MB dyno, 7-8 clients is the realistic ceiling** — confirmed in production: 13 clients hit Heroku R14 (memory quota exceeded) before a single viewer connected, 21 clients would be worse. Going past 7-8 needs more RAM (1GB+), not more tuning.
- `CONCURRENT_FETCHES` (per-stream parallel chunk fetch) trades speed for FloodWait risk — bumping this too high compounds fast under real concurrent load. Test any change against real traffic before trusting it; don't just guess upward.
- Bump `MULTI_TOKEN` count if you're seeing FloodWait storms in logs; bump dyno RAM if you're seeing R14 — they're different problems with different fixes.
- Live per-client load is visible anytime at the root URL — `GET /` returns `{"status":"alive","total_clients":N,"clients":[{"client_id":0,"active_streams":2},...]}`. Same endpoint your self-ping already hits, zero extra cost to check.

<h2 align="center">📁 Project layout</h2>

```
bot.py                       entrypoint, plugin loader, auto-restart (routes through graceful SIGTERM path), shutdown
info.py                      env var config, auto-sanitizes a misconfigured URL
Script.py                    bot text templates
utils.py                     shortlink helper, temp state
database/                    MongoDB user store
lib/bot/__init__.py          main bot client (workers=16)
lib/bot/clients.py           multi-client manager — start + graceful stop_clients()
lib/util/custom_dl.py        chunked file streaming from Telegram, retry logic, parallel prefetch, load-balancer fallback
lib/util/render_template.py  renders download/stream HTML pages, caches compiled templates
lib/template/                req.html (player page), dl.html (download page)
lib/server/exceptions.py     InvalidHash / FIleNotFound
plugins/route.py             /watch and raw byte-stream routes, atomic client reservation, live status JSON on /
plugins/start.py             file handling, link generation, revoke button + callbacks
plugins/                     other command handlers (broadcast, stats, etc.)
```

<h2 align="center">📝 Notes</h2>

- `LOG_CHANNEL` must be a channel/group every bot token (main + all `MULTI_TOKEN*`) is admin in — it's permanent file storage, not just a log. If one client loses access, `generate_file_properties()` now auto-retries with the main client instead of a random-looking "file not found" for whichever viewer got load-balanced to that client.
- Revoking a file is permanent and immediate — it deletes the message from `LOG_CHANNEL` itself, not just the link. There's no undo.
- DTS/DTS-HD/TrueHD audio tracks won't play in-browser regardless of what's in the file — no browser ships a decoder for them, that's a licensing wall, not a bug.
- `workers=16` on the main bot client sizes update-dispatch concurrency (commands/messages through handlers) — it has no effect on streaming speed, that path never touches it.

<h2 align="center">🩹 Changelog</h2>

| Fix | Detail |
|---|---|
| Heroku R12 (Exit timeout / SIGKILL) | Graceful shutdown on SIGTERM: stops aiohttp server, cancels in-flight stream tasks, stops every Pyrogram client within a bounded 20s window |
| Auto-restart bypassed shutdown entirely | `os.execv()` replaced the process image directly, skipping every cleanup step above on every 12h restart. Now sends itself SIGTERM and lets the same graceful path handle it |
| Load balancer pile-up under download accelerators | Client pick + reservation had an `await` gap between them — parallel connections (FDM, IDM) could all read stale load data and land on the same client. Now atomic, no gap |
| Silent permanent load-balancer drift | An exception during session setup (before the main try/finally) skipped the load counter's release, permanently inflating it. Fixed with an explicit release-on-failure path |
| Random "file not found" under multi-client | A client without real `LOG_CHANNEL` access returns nothing even though the file exists — now falls back to the main client before giving up |
| Stream died instantly on `[-503 Timeout]` / transient Telegram RPC errors | Now retried with backoff (7 attempts), same as FloodWait |
| `dict(clients)` crash on any failed multi-client token | Failed tokens are skipped instead of crashing the whole multi-client pool |
| `GeneratorExit` / "coroutine ignored" spam on client disconnect | Prefetch producer stops cooperatively instead of being hard-cancelled mid-fetch; strong-ref set prevents early GC of pending tasks |
| Slow single-stream speed | Chunks fetched several-at-a-time per stream (`CONCURRENT_FETCHES`) instead of strictly sequential |
| Downloaded filename sometimes corrupted (`+` vs space) | URL path now uses `quote()` not `quote_plus()`; `download=` attribute also forces the exact real filename client-side |
| `requirements.txt` had a typo'd package name | `wzgram[fast]` (doesn't exist on PyPI) → `pyrofork[fast]` |
| Page re-parsed/recompiled the Jinja template on every single view | Compiled once per process, cached |
| Bundled a full video-player library duplicating a toolbar already built manually | Removed; native `<video controls>` + manual keyboard shortcuts (Space/F/M/arrows) replace it |
| `workers=50` on the main client | Trimmed to 16 — that setting only sizes command-handler concurrency, unrelated to streaming, and was wasting RAM for no real benefit at this bot's scale |
| `MULTI_CLIENT` flag never reached the route handler | Route now checks live client count directly |
| `info.py` crashed with a bare `ValueError` if required vars missing | Now exits with a clear error message |
| Every plugin handler ran **twice** (double plugin load) | Removed auto-load, kept only the manual loader |

<h2 align="center">👤 Maintainer</h2>

<p align="center"><b>Goutham</b> — <a href="https://github.com/GouthamSER">@GouthamSER</a></p>
