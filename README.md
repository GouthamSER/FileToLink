<div align="center">

<img src="https://i.ibb.co/KzqHfL05/photo-2026-02-07-13-38-13.jpg" width="100" height="100" style="border-radius:24px; box-shadow:0 8px 30px rgba(139,92,246,0.35);" alt="File 2 Link Logo">

# ⚡ File 2 Link ™

**High-Performance Telegram Cloud Streamer & Instant Direct Download Engine**

[![Version](https://img.shields.io/badge/Version-v1.5.2-8B5CF6?style=for-the-badge&logo=git&logoColor=white)](#-changelog)
[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Telegram Engine](https://img.shields.io/badge/Telegram-MTProto%20v2-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/wudixh15)
[![Telegram Library](https://img.shields.io/badge/Library-wzgram%20%5Bfast%5D-F59E0B?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/wzgram/)
[![Async Server](https://img.shields.io/badge/Server-aiohttp%20Speedups-FF6B6B?style=for-the-badge&logo=aiohttp&logoColor=white)](https://aiohttp.readthedocs.io)
[![Database](https://img.shields.io/badge/Database-MongoDB%20Async-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com)
[![Docker](https://img.shields.io/badge/Container-Docker%20Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)

<p align="center">
  <b>Send any Telegram file → Get instant high-speed streaming links & direct downloads with multi-client load balancing.</b>
</p>

[Deploy to Koyeb](https://app.koyeb.com/deploy?type=git&repository=github.com/GouthamSER/FileToLink&branch=main&builder=dockerfile) • [Deploy to Heroku](https://heroku.com/deploy?template=https://github.com/GouthamSER/FileToLink) • [Deploy to Render](https://render.com/deploy?repo=https://github.com/GouthamSER/FileToLink) • [Telegram Updates](https://t.me/wudixh15)

</div>

---

## 🌟 Highlights & Key Features

### 🎞️ Movi Player Web Page (`/watch/{id}`, `/stream/{id}`, `/movi/{id}`)
One liquid-glass player page for every video and audio file, powered by **Movi Player v0.4.1** (FFmpeg-WASM + WebCodecs).
- **Audio track switching**: pick any embedded language / track in multi-audio MKV and MP4.
- **Subtitle support**: embedded subtitle tracks, an *Off* option, and a **subtitle delay** slider (±10 s).
- **Plays more formats**: `.mkv`, `.mp4`, `.webm`, `.avi`, `.mov`, `.flv`, `.m4v`, `.ts`, `.3gp` including HEVC / AC3 that normal browser players reject.
- **Resume where you left off**: playback position is remembered per file.
- **Liquid-glass UI**: animated gradient blobs, frosted-glass cards, `Plus Jakarta Sans` + `JetBrains Mono`.
- **Audio mode**: music files (`.mp3`, `.flac`, `.wav`, `.ogg`, `.m4a`, `.aac`) get a spinning vinyl disc.
- **One-click external apps**: VLC, MX Player, nPlayer, KMPlayer, PotPlayer, raw stream URL copy (Kodi / Infuse / IINA) and native Share.
- **Safe by default**: pinned CDN version + SRI integrity hash (`MOVI_SRC` / `MOVI_SRI` to override; empty `MOVI_SRI` disables the check), RAM buffer auto-sized by device (32–128 MB), player disposed on page leave.
- **Graceful fallback**: no WebCodecs or CDN blocked → clear error + download link, external-app buttons still work.
- **Limits**: DTS / TrueHD audio is not decoded; HEVC / AV1 without hardware decode is CPU-heavy on weak phones. Use *Open in VLC* for 4K.

### 🚀 Direct Download Hub (`/{id}`)
- **Gigabit Chunked Streaming**: Full HTTP/1.1 Range header support (`206 Partial Content`) for multi-threaded download accelerators (IDM, 1DM, ADM, FDM, aria2).
- **Format-Aware Visual Badging**: Custom format icons and colored badges for video, audio, archives (`.zip`, `.rar`, `.7z`), software, and documents.
- **Native Web Share API**: One-click file sharing on mobile with clipboard copy fallback and custom toast feedback.
- **Dynamic Connection Animation**: Visual download handshake indicator.

### 🛡️ Core Reliability & Bot Architecture
- **Multi-Client Load Balancing**: Round-robin and active-workload client balancing across multiple bot tokens (`MULTI_TOKEN1..N`) for virtually unlimited concurrent throughput.
- **Atomic Reservation Lock**: Zero-gap client selection prevents race conditions when download accelerators open 16–32 connections in parallel.
- **Sliding-Window Chunk Prefetching**: Each stream keeps `CONCURRENT_FETCHES` Telegram requests always in flight, delivered strictly in order, so VLC/MX seeks and buffering stay smooth.
- **Seek-Safe Streams**: Abandoned seeks are torn down instantly (no leaked load counters), `HEAD` probes cost zero Telegram traffic, and a stale file reference fails fast and self-heals.
- **Stream Caps (anti-crash)**: `MAX_ACTIVE_STREAMS` (default 12) limits streams on the whole dyno and `MAX_STREAMS_PER_IP` (default 6) stops one download manager from taking every slot. Over the limit → `429` / `503` with `Retry-After`. `HEAD` probes are never counted.
- **Low-RAM Streaming**: zero-copy `memoryview` chunks, small per-stream buffers, `MALLOC_ARENA_MAX=2` and 4 Pyrogram workers keep a 512 MB Heroku dyno away from R14.
- **Resilient Retry Mechanism**: Automatic backoff retries for transient Telegram RPC errors (`-503 Timeout`, `FloodWait`, socket drops).
- **All Media Types Supported**: Documents, videos, audios, photos, voice notes, video notes, and stickers.
- **Permanent Link Revocation**: One-tap 🗑️ **Delete / Revoke** button with two-step confirmation window allows uploaders and admins to permanently remove files from storage.
- **User Ban System**: Admins ban abusers with `/ban <id|@username> [reason]`. Banned users get an NSFW-policy notice with the admin contact, are blocked from every command and button, and the ban list persists in MongoDB.
- **Zero-Crash MongoDB Integration**: Gracefully runs even if `DATABASE_URI` is unset or MongoDB is temporarily unreachable.
- **Clean SIGTERM Shutdown**: Graceful cleanup handles Heroku R12 / Koyeb termination cleanly without killing active connections or corrupting downloads.

---

## 🏗️ Architecture Flow

```mermaid
flowchart TD
    A[User sends File / Video / Photo] --> B[Bot uploads to LOG_CHANNEL]
    B --> C[Bot generates Unique Hash & URLs]
    C --> D[User receives Stream & Download Buttons]
    
    subgraph Client Streaming Requests
        E[Browser / Player requests /watch or /dl] --> F[aiohttp Web Server]
        F --> G[Atomic Multi-Client Load Balancer]
        G --> H{Select least-busy MTProto Client}
        H --> I[ByteStreamer: Parallel Telegram 1MB Chunks]
        I --> J[RFC 7233 HTTP 206 Byte-Range Response]
        J --> K[Smooth High-Speed Playback / Download]
    end
```

---

## 📦 Deployment & Setup

### 1. One-Click Cloud Deploy

| Platform | Deployment Button |
|---|---|
| **Koyeb** *(Recommended)* | [![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/GouthamSER/FileToLink&branch=main&builder=dockerfile) |
| **Heroku** | [![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/GouthamSER/FileToLink) |
| **Heroku (Colab, container stack)** | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1U_bWcaWD8pdRqFknp72yA1z_w28g5S5k?usp=sharing) — open it, *File → Save a copy in Drive*, enter your own Heroku email + API key + env vars. It builds & deploys via `heroku.yml`, then auto-wipes your secrets from the Colab session. Source: [`colab/Deploy_to_Heroku.ipynb`](colab/Deploy_to_Heroku.ipynb) |
| **Render** | [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/GouthamSER/FileToLink) |

---

### 2. Manual & VPS Setup

```bash
# Clone the repository
git clone https://github.com/GouthamSER/FileToLink.git
cd FileToLink

# Install dependencies
pip install -r requirements.txt

# Configure your environment variables (.env)
cp app.json .env # or configure manually

# Start the bot
python bot.py
```

### 3. Docker Deployment

```bash
# Build the optimized container
docker build -t file2link .

# Run with environment file
docker run -d -p 8080:8080 --env-file .env --name file2link_app file2link
```

---

## ⚙️ Configuration Variables

| Variable | Required | Description |
|---|:---:|---|
| `API_ID` | **Yes** | Telegram API ID from [my.telegram.org](https://my.telegram.org). |
| `API_HASH` | **Yes** | Telegram API Hash from [my.telegram.org](https://my.telegram.org). |
| `BOT_TOKEN` | **Yes** | Main Telegram Bot Token from [@BotFather](https://t.me/BotFather). |
| `LOG_CHANNEL` | **Yes** | Telegram Channel ID (e.g. `-1001234567890`) used as file storage. Bot must be Admin. |
| `URL` | **Yes** | Public root URL (e.g. `https://myapp.koyeb.app/`). Trailing slashes and health paths auto-sanitized. |
| `DATABASE_URI` | Optional | MongoDB connection string (`mongodb+srv://...`). Bot runs with DB disabled if omitted. |
| `DATABASE_NAME` | Optional | MongoDB database name (default: `FileToLink`). |
| `ADMINS` | Optional | Space-separated list of Admin IDs or usernames (e.g. `12345678 @username`). |
| `FSUB_CHANNEL` | Optional | Force-subscribe channel ID (e.g. `-1009876543210`). `0` = disabled. |
| `PORT` | Optional | Web server port (default: `8080`). |
| `MULTI_TOKEN1..N` | Optional | Additional Bot Tokens for multi-client load balancing. Add each bot as Admin in `LOG_CHANNEL`. |
| `SHORTLINK` | Optional | Enable Shortzy-based URL shorteners (`True` / `False`). |
| `SHORTLINK_URL` | Optional | Shortener base site URL (e.g. `api.shareus.io`, `gplinks.com`). |
| `SHORTLINK_API` | Optional | Shortener API key. |
| `ISGD` | Optional | Enable free `is.gd` shortener (`True` / `False`). |
| `MAX_ACTIVE_STREAMS` | Optional | Max simultaneous HTTP streams on the whole server (default `12`). Lower it if you see R14 memory errors. |
| `MAX_STREAMS_PER_IP` | Optional | Max simultaneous streams per user IP (default `6`). |
| `STREAM_CONCURRENCY` / `STREAM_PREFETCH` | Optional | Telegram chunks fetched in parallel / prefetched per stream (defaults `3` / `2`). |
| `CLIENT_MAX_FETCHES` | Optional | Max simultaneous Telegram fetches per bot client (default `8`). |
| `MOVI_SRC` / `MOVI_SRI` | Optional | Movi Player script URL and its SRI hash. Defaults to the pinned v0.4.1 build. |
| `AUTO_RESTART` | Optional | Periodic graceful restart trigger (default: `True`, 3-hour interval; set `False` to avoid cutting live streams). |

---

## 🎮 Telegram Bot Commands

| Command | Permission | Description |
|---|:---:|---|
| `/start` | Everyone | Start the bot, receive welcome guide & verify channel subscription. |
| `/how` | Everyone | Comprehensive user guide on how to stream, download, and revoke links. |
| `/stats` | Admins | Real-time system diagnostics (RAM, CPU, Uptime, Network I/O, User count). |
| `/broadcast` | Admins | Broadcast a replied message to all registered bot users in MongoDB. |
| `/ban` | Admins | `/ban <user_id \| @username> [reason]` (or reply to a user). Bans the user, notifies them (NSFW / contact admin) and saves to MongoDB. |
| `/unban` | Admins | `/unban <user_id \| @username>` lifts a ban and notifies the user. |
| `/banlist` | Admins | Show the latest banned users with reasons. |
| `/restart` | Admins | Trigger a graceful SIGTERM restart with in-flight stream and client safety. |

---

## 📈 Multi-Client Scaling & Performance Tips

> [!TIP]
> **Scaling Formula**: Each additional `MULTI_TOKEN` handles roughly 3–5 concurrent high-bitrate video streams before Telegram triggers rate limiting.
> `Tokens Needed ≈ Target Peak Concurrent Streams / 4`

- **Memory Consumption**: Each MTProto client consumes roughly 25–35 MB RAM. On a 512 MB dyno/container, 4–6 clients plus the stream caps run comfortably.
- **Maximum Download Speed**: For desktop downloads, recommend **IDM** with 16 connections. For mobile downloads, recommend **1DM** or **ADM**.
- **Live Health Status**: Visit `GET /` or `GET /?json=true` on your deployment URL anytime to view live uptime, active workload counts, and client distribution.

---

## 📁 Repository Structure

```
FileToLink/
├── bot.py                     # Main application entrypoint & graceful lifecycle manager
├── info.py                    # Environment parser, admin validator & URL sanitizer
├── Script.py                  # Localized Telegram text formatting & banners
├── utils.py                   # URL shortener service wrappers & temporary state
├── database/
│   └── users_chats_db.py      # Async MongoDB layer: users + banned_users (cached) with fail-safe guards
├── lib/
│   ├── bot/
│   │   ├── __init__.py        # Primary wzgram (Pyrogram API) client definition
│   │   └── clients.py         # Multi-client pool initialization & graceful stopper
│   ├── server/
│   │   └── exceptions.py      # Custom exceptions (InvalidHash, FIleNotFound)
│   ├── template/
│   │   ├── movi.html          # Movi Player video/audio page (audio+subtitle tracks)
│   │   ├── dl.html            # High-Speed Download Portal & acceleration guide
│   │   └── home.html          # Next-Gen Telegram Stream & Cloud Hub Dashboard
│   └── util/
│       ├── custom_dl.py       # Custom ByteStreamer for Telegram chunked byte-range fetches
│       ├── file_properties.py # Media type detector & universal filename synthesizer
│       ├── human_readable.py  # Safe byte formatter (handles 0 B to PiB without crashes)
│       ├── keepalive.py       # Pinger to prevent dyno idle sleep
│       └── render_template.py # Format-aware Jinja2 compiler & cached renderer
└── plugins/
    ├── route.py               # aiohttp streaming engine, RFC 206 byte-range handler
    ├── start.py               # Media receiver, HTML escaping, link generator & revoker
    ├── broadcast.py           # Admin broadcasting with FloodWait & error handlers
    ├── ban.py                 # /ban, /unban, /banlist + global banned-user gate
    ├── etc.py                 # Live hardware & process stats with refresh buttons
    └── selfping.py            # Self-ping keepalive loop
```

---

## 🧾 Changelog

Current version code: **`v1.5.2`** (also exposed as `__version__` in `lib/__init__.py`).

| Version | Changes |
|---|---|
| **v1.5.2** | ⏪ Back on **`wzgram[fast]`** (dzgram dropped) · no Cloudflare settings |
| **v1.4.0** | 🎞️ **Movi Player v0.4.1** page: audio-track + subtitle switching, subtitle delay, resume, external-app launchers · liquid-glass UI · pinned CDN + SRI · old Plyr watch page removed (`/watch`, `/stream`, `/movi` all use Movi) |
| **v1.3.1** | `HEAD` requests exempt from stream caps · per-IP default raised to 6 |
| **v1.3.0** | 🧯 Heroku R14 fix: global (`MAX_ACTIVE_STREAMS`) and per-IP (`MAX_STREAMS_PER_IP`) stream caps, smaller buffers, zero-copy chunks, `MALLOC_ARENA_MAX=2`, 4 workers · new `Script.py` messages · Colab Heroku deploy notebook with auto secret wipe |
| **v1.2.0** | 🚫 Ban system (`/ban`, `/unban`, `/banlist`, MongoDB `banned_users`, NSFW notice + admin contact) · 🎬 Seek/buffering fixes: leaked stream cleanup, sliding-window prefetch, HEAD handled without Telegram fetch, fail-fast on expired file references, no bot restart on a single bad chunk · Removed duplicate Telegram call per watch page · README refresh |
| **v1.1** | Multi-client load balancing, revoke button, graceful SIGTERM shutdown, URL sanitizer |

Bump the version in `lib/__init__.py` and add a row here on every release.

---

## 🤝 Support & Community

- **Developer**: [Goutham](https://github.com/GouthamSER)
- **Updates Channel**: [@wudixh15](https://t.me/wudixh15)
- **License**: [GNU General Public License v3.0](LICENSE)

<div align="center">
  <sub>Made with ❤️ for high-performance Telegram streaming.</sub>
</div>
