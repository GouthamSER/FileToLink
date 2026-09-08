import re, math, time, logging, secrets, mimetypes, urllib.parse, asyncio
from info import *
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from lib.bot import File2Link, multi_clients, work_loads
from lib.server.exceptions import FIleNotFound, InvalidHash
from lib import StartTime, __version__
from lib.util.custom_dl import ByteStreamer
from lib.util.time_format import get_readable_time
from lib.util.render_template import render_page
from plugins.error_detection import detect_error

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    # Fetch existing metrics
    uptime_str = get_readable_time(int(time.time() - StartTime))
    total_clients = len(multi_clients)
    is_multi_client = total_clients > 1
    
    # Optional: Keep old JSON functionality if ?json=true is passed
    # Useful for Heroku/Koyeb/Render bots that strictly expect JSON
    if request.query.get("json") == "true":
        clients = [
            {"client_id": cid, "active_streams": load}
            for cid, load in sorted(work_loads.items())
        ]
        return web.json_response({
            "status": "alive",
            "uptime": uptime_str,
            "multi_client": is_multi_client,
            "total_clients": total_clients,
            "clients": clients,
        })

    # Generate HTML for the client workloads dynamically
    clients_html = ""
    for cid, load in sorted(work_loads.items()):
        clients_html += f"""
        <div class="client-item">
            <span>Client ID: <b>{cid}</b></span>
            <span class="badge">{load} Active Streams</span>
        </div>
        """
        
    if not clients_html:
        clients_html = '<div class="client-item" style="justify-content: center; color: var(--text-muted);">No active clients found.</div>'

    # Build responsive, interactive HTML string
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Status Dashboard</title>
    <style>
        :root {{
            --bg: #0f172a; --card-bg: #1e293b; --item-bg: #334155;
            --text-main: #f8fafc; --text-muted: #94a3b8;
            --accent: #38bdf8; --success: #10b981; --error: #ef4444;
        }}
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: system-ui, -apple-system, sans-serif; 
            background: var(--bg); color: var(--text-main); 
            margin: 0; padding: 1.5rem; 
            display: flex; justify-content: center; align-items: center; 
            min-height: 100vh; 
        }}
        .container {{ 
            background: var(--card-bg); padding: 2rem; 
            border-radius: 1rem; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); 
            width: 100%; max-width: 650px; border: 1px solid #334155; 
        }}
        h1 {{ 
            text-align: center; color: var(--accent); 
            margin-top: 0; display: flex; align-items: center; 
            justify-content: center; gap: 12px; font-size: 1.8rem;
        }}
        .stat-grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); 
            gap: 1rem; margin-bottom: 2rem; 
        }}
        .stat-card {{ 
            background: var(--item-bg); padding: 1.5rem 1rem; 
            border-radius: 0.75rem; text-align: center; 
            transition: transform 0.2s, box-shadow 0.2s; 
        }}
        .stat-card:hover {{ 
            transform: translateY(-5px); 
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }}
        .stat-value {{ 
            font-size: 1.25rem; font-weight: bold; margin: 0.5rem 0; 
            color: var(--success); 
        }}
        .stat-label {{ 
            font-size: 0.75rem; color: var(--text-muted); 
            text-transform: uppercase; letter-spacing: 0.1em; 
        }}
        .client-list {{ 
            background: var(--item-bg); border-radius: 0.75rem; overflow: hidden; 
        }}
        .client-item {{ 
            display: flex; justify-content: space-between; align-items: center; 
            padding: 1rem 1.5rem; border-bottom: 1px solid #475569; 
            transition: background 0.2s;
        }}
        .client-item:hover {{ background: #3f4e66; }}
        .client-item:last-child {{ border-bottom: none; }}
        .status-indicator {{ 
            display: inline-block; width: 14px; height: 14px; 
            background: var(--success); border-radius: 50%; 
            box-shadow: 0 0 10px var(--success); animation: pulse 2s infinite; 
        }}
        .badge {{ 
            background: var(--accent); color: var(--bg); 
            padding: 0.35rem 0.75rem; border-radius: 999px; 
            font-size: 0.8rem; font-weight: bold; 
        }}
        @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1><span class="status-indicator"></span> System Status</h1>
        
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-label">Uptime</div>
                <div class="stat-value">{uptime_str}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Clients</div>
                <div class="stat-value">{total_clients}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Multi-Client</div>
                <div class="stat-value" style="color: {'var(--success)' if is_multi_client else 'var(--error)'}">
                    {is_multi_client}
                </div>
            </div>
        </div>

        <h2 style="font-size: 1rem; margin-bottom: 1rem; color: var(--text-muted); letter-spacing: 0.05em;">ACTIVE WORKLOADS</h2>
        <div class="client-list">
            {clients_html}
        </div>
    </div>
</body>
</html>
"""
    return web.Response(text=html_content, content_type="text/html")


@routes.get(r"/watch/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
    return await _render_page_route(request, page="watch")


@routes.get(r"/dl/{path:\S+}", allow_head=True)
async def download_direct_handler(request: web.Request):
    # /dl/<hash+id> = direct download, same as the old bare /{id}/{filename}
    # route — straight to raw bytes with Content-Disposition: attachment,
    # no HTML page in between. Just reuses the new short hash+id URL shape.
    return await _download_route(request)


async def _render_page_route(request: web.Request, page: str):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            id = int(match.group(2))
        else:
            id = int(re.search(r"(\d+)(?:\/\S+)?", path).group(1))
            secure_hash = request.rel_url.query.get("hash")
        return web.Response(
            text=await render_page(id, secure_hash, page=page), content_type="text/html"
        )
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical(e.with_traceback(None))
        asyncio.create_task(detect_error(e, context="route_handler"))
        raise web.HTTPInternalServerError(text=str(e))


@routes.get(r"/{path:\S+}", allow_head=True)
async def download_handler(request: web.Request):
    return await _download_route(request)


async def _download_route(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            id = int(match.group(2))
        else:
            id = int(re.search(r"(\d+)(?:\/\S+)?", path).group(1))
            secure_hash = request.rel_url.query.get("hash")
        return await media_streamer(request, id, secure_hash)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical(e.with_traceback(None))
        asyncio.create_task(detect_error(e, context="route_handler"))
        raise web.HTTPInternalServerError(text=str(e))


class_cache = {}


async def media_streamer(request: web.Request, id: int, secure_hash: str):
    range_header = request.headers.get("Range", "")

    # Reserve the client's slot RIGHT HERE, synchronously, with the pick —
    # no await between them. Previously the reservation (work_loads
    # increment) only happened deep inside yield_file(), well after
    # `await tg_connect.get_file_properties(id)` below. That await hands
    # control back to the event loop, so a burst of near-simultaneous
    # requests (exactly what download accelerators like FDM do — they open
    # many parallel Range connections to the same URL at once) could all
    # read the same stale work_loads snapshot and all pick the SAME
    # "least loaded" client before any of them registered. Net effect:
    # streaming (one connection at a time) balanced fine, but download
    # managers' parallel connections all piled onto one or two clients.
    # Doing pick+reserve as one atomic (no-await) step closes that window.
    index = min(work_loads, key=work_loads.get)
    work_loads[index] += 1
    reserved = True
    faster_client = multi_clients[index]

    try:
        if len(multi_clients) > 1:
            logging.info(f"Client {index} is now serving {request.remote}")

        if faster_client in class_cache:
            tg_connect = class_cache[faster_client]
            logging.debug(f"Using cached ByteStreamer object for client {index}")
        else:
            logging.debug(f"Creating new ByteStreamer object for client {index}")
            tg_connect = ByteStreamer(faster_client)
            class_cache[faster_client] = tg_connect

        logging.debug("before calling get_file_properties")
        file_id = await tg_connect.get_file_properties(id)
        logging.debug("after calling get_file_properties")

        if file_id.unique_id[:6] != secure_hash:
            logging.debug(f"Invalid hash for message with ID {id}")
            raise InvalidHash

        file_size = file_id.file_size

        # --- Range parsing ---------------------------------------------------------
        # Always use 1 MB chunks (Telegram's GetFile hard limit).
        chunk_size = 1024 * 1024

        if range_header:
            # Parse "bytes=START-END" (END is optional)
            try:
                range_val = range_header.replace("bytes=", "")
                start_str, end_str = range_val.split("-")
                from_bytes = int(start_str) if start_str else 0
                until_bytes = int(end_str) if end_str else file_size - 1
            except (ValueError, AttributeError):
                return web.Response(
                    status=416,
                    body="416: Range not satisfiable",
                    headers={"Content-Range": f"bytes */{file_size}"},
                )
        else:
            from_bytes = 0
            until_bytes = file_size - 1

        # Clamp and validate
        until_bytes = min(until_bytes, file_size - 1)

        if until_bytes < from_bytes or from_bytes < 0:
            return web.Response(
                status=416,
                body="416: Range not satisfiable",
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        # --- Chunk maths -----------------------------------------------------------
        offset = from_bytes - (from_bytes % chunk_size)
        first_part_cut = from_bytes - offset
        last_part_cut = until_bytes % chunk_size + 1
        req_length = until_bytes - from_bytes + 1
        part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)

        # yield_file() owns the reservation from here on — it releases it
        # (work_loads[index] -= 1) in its own finally once the actual byte
        # stream finishes, however long that takes. Mark reserved=False so
        # OUR except block below doesn't also release it once we return.
        body = tg_connect.yield_file(
            file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
        )
        reserved = False

        # --- MIME / filename -------------------------------------------------------
        mime_type = file_id.mime_type
        file_name = file_id.file_name

        if mime_type:
            if not file_name:
                try:
                    ext = mime_type.split("/")[1]
                except (IndexError, AttributeError):
                    ext = "unknown"
                file_name = f"{secrets.token_hex(2)}.{ext}"
        else:
            if file_name:
                mime_type = (
                    mimetypes.guess_type(file_name)[0] or "application/octet-stream"
                )
            else:
                mime_type = "application/octet-stream"
                file_name = f"{secrets.token_hex(2)}.unknown"

        # RFC 5987 — encode non-ASCII filenames so Chrome doesn't mangle them.
        # Plain ASCII names use the simple form; everything else gets utf-8 encoding.
        try:
            file_name.encode("ascii")
            disposition_value = f'attachment; filename="{file_name}"'
        except UnicodeEncodeError:
            encoded = urllib.parse.quote(file_name, safe="")
            disposition_value = (
                f"attachment; filename*=utf-8''{encoded}"
            )

        # --- Response --------------------------------------------------------------
        # Always respond 206 when a Range header was supplied (even bytes=0-).
        # Chrome treats a 200 for a Range request as "no range support" and
        # will restart the download from 0 if the connection drops.
        status = 206 if range_header else 200

        return web.Response(
            status=status,
            body=body,
            headers={
                "Content-Type": mime_type,
                "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
                "Content-Length": str(req_length),
                "Content-Disposition": disposition_value,
                # Tell clients (and Chrome's download manager) we support resuming.
                "Accept-Ranges": "bytes",
                # Prevent Chrome from caching a partial response and then
                # refusing to request the remaining bytes.
                "Cache-Control": "no-store, no-cache",
                # Keep the TCP connection alive between chunk requests.
                "Connection": "keep-alive",
            },
        )
    finally:
        # Only fires if we exit WITHOUT ever reaching yield_file() (early
        # 416 return, InvalidHash, get_file_properties failure) — in that
        # case the reservation made at the top was never handed off, so
        # release it here. Once yield_file() is called, reserved=False and
        # this is a no-op; yield_file's own finally owns the release then.
        if reserved:
            work_loads[index] -= 1
