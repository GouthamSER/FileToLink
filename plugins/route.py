import re
import math
import time
import logging
import secrets
import mimetypes
import urllib.parse
import asyncio

from info import *
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from lib.bot import File2Link, multi_clients, work_loads
from lib.server.exceptions import FIleNotFound, InvalidHash
from lib import StartTime, __version__
from lib.util.custom_dl import ByteStreamer, CHUNK_SIZE
from lib.util.time_format import get_readable_time
from lib.util.render_template import render_page
from plugins.error_detection import detect_error


routes = web.RouteTableDef()
class_cache = {}


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    uptime_str = get_readable_time(int(time.time() - StartTime))
    total_clients = len(multi_clients)
    is_multi_client = total_clients > 1

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

    clients_html = ""
    for cid, load in sorted(work_loads.items()):
        clients_html += f"""
        <div class="client-item">
            <span>Client ID: <b>{cid}</b></span>
            <span class="badge">{load} Active</span>
        </div>
        """

    if not clients_html:
        clients_html = (
            '<div class="client-item" style="justify-content:center;'
            'color:var(--text-muted);">No active clients found.</div>'
        )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File ² Link</title>
    <style>
        :root {{
            --bg-main:#121212;
            --bg-secondary:#1e1e1e;
            --accent-purple:#9333ea;
            --text-main:#fff;
            --text-muted:#a3a3a3;
            --success:#22c55e;
            --error:#ef4444;
        }}
        html,body {{
            margin:0;
            padding:0;
            font-family:system-ui,-apple-system,sans-serif;
            background:var(--bg-main);
            color:var(--text-main);
            scroll-behavior:smooth;
        }}
        nav {{
            padding:1.5rem 2rem;
            display:flex;
            align-items:center;
            position:absolute;
            top:0;
            width:100%;
            box-sizing:border-box;
        }}
        .logo {{
            font-size:1.25rem;
            font-weight:800;
            letter-spacing:.05em;
            text-transform:uppercase;
        }}
        .logo span {{ color:var(--accent-purple); }}
        .hero {{
            min-height:100vh;
            display:flex;
            flex-direction:column;
            justify-content:center;
            align-items:center;
            text-align:center;
            padding:2rem;
            box-sizing:border-box;
        }}
        .hero h1 {{
            font-size:clamp(2rem,5vw,3.5rem);
            margin:0 0 1rem;
            font-weight:800;
            letter-spacing:-.02em;
        }}
        .hero p {{
            font-size:clamp(1rem,2.5vw,1.25rem);
            color:var(--text-muted);
            margin:0;
            max-width:600px;
        }}
        .scroll-prompt {{
            margin-top:4rem;
            color:var(--text-muted);
            animation:bounce 2s infinite;
            display:flex;
            flex-direction:column;
            align-items:center;
        }}
        @keyframes bounce {{
            0%,20%,50%,80%,100% {{ transform:translateY(0); }}
            40% {{ transform:translateY(-10px); }}
            60% {{ transform:translateY(-5px); }}
        }}
        .status-section {{
            padding:4rem 2rem;
            max-width:800px;
            margin:0 auto;
            min-height:80vh;
        }}
        .section-title {{
            text-align:center;
            font-size:1.8rem;
            margin-bottom:3rem;
            display:flex;
            justify-content:center;
            align-items:center;
            gap:12px;
        }}
        .status-indicator {{
            display:inline-block;
            width:14px;
            height:14px;
            background:var(--success);
            border-radius:50%;
            box-shadow:0 0 10px var(--success);
            animation:pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ box-shadow:0 0 0 0 rgba(34,197,94,.7); }}
            70% {{ box-shadow:0 0 0 10px rgba(34,197,94,0); }}
            100% {{ box-shadow:0 0 0 0 rgba(34,197,94,0); }}
        }}
        .stat-grid {{
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
            gap:1rem;
            margin-bottom:3rem;
        }}
        .stat-card {{
            background:var(--bg-secondary);
            padding:1.5rem;
            border-radius:1rem;
            text-align:center;
            border:1px solid #262626;
        }}
        .stat-value {{
            font-size:1.5rem;
            font-weight:bold;
            margin:.5rem 0;
            color:var(--success);
        }}
        .stat-label {{
            font-size:.8rem;
            color:var(--text-muted);
            text-transform:uppercase;
            letter-spacing:.1em;
        }}
        .client-list {{
            background:var(--bg-secondary);
            border-radius:1rem;
            overflow:hidden;
            border:1px solid #262626;
        }}
        .client-item {{
            display:flex;
            justify-content:space-between;
            align-items:center;
            padding:1.25rem 1.5rem;
            border-bottom:1px solid #262626;
        }}
        .client-item:last-child {{ border-bottom:none; }}
        .badge {{
            background:var(--accent-purple);
            color:#fff;
            padding:.35rem .75rem;
            border-radius:999px;
            font-size:.8rem;
            font-weight:bold;
        }}
        footer {{
            text-align:center;
            padding:2rem;
            color:var(--text-muted);
            font-size:.9rem;
            border-top:1px solid #262626;
            margin-top:2rem;
        }}
        footer a {{
            color:var(--accent-purple);
            text-decoration:none;
        }}
    </style>
</head>
<body>
    <nav>
        <div class="logo">FILE ² <span>LINK</span></div>
    </nav>

    <section class="hero">
        <h1>Welcome to File ² Link</h1>
        <p>Experience seamless streaming like never before.</p>

        <div class="scroll-prompt">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2" stroke-linecap="round"
                 stroke-linejoin="round">
                <path d="M12 5v14M19 12l-7 7-7-7"/>
            </svg>
            <div style="font-size:.75rem;margin-top:.75rem;text-transform:
                 uppercase;letter-spacing:2px;">Scroll for Status</div>
        </div>
    </section>

    <section class="status-section" id="status">
        <h2 class="section-title">
            <span class="status-indicator"></span> System Status
        </h2>

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
                <div class="stat-value"
                     style="color:{'var(--success)' if is_multi_client else 'var(--error)'}">
                    {is_multi_client}
                </div>
            </div>
        </div>

        <h3 style="font-size:1rem;margin-bottom:1rem;color:var(--text-muted);
                   letter-spacing:.05em;text-transform:uppercase;">
            Active Workloads
        </h3>
        <div class="client-list">{clients_html}</div>
    </section>

    <footer>
        Copyright &copy; 2026 <a href="#">File ² Link</a>. All Rights Reserved.
    </footer>
</body>
</html>
"""
    return web.Response(text=html_content, content_type="text/html")


@routes.get(r"/watch/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
    return await _render_page_route(request, page="watch")


@routes.get(r"/dl/{path:\S+}", allow_head=True)
async def download_direct_handler(request: web.Request):
    return await _download_route(request)


async def _render_page_route(request: web.Request, page: str):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)

        if match:
            secure_hash = match.group(1)
            message_id = int(match.group(2))
        else:
            match = re.search(r"(\d+)(?:/\S+)?", path)
            if not match:
                raise web.HTTPBadRequest(text="Invalid file path")
            message_id = int(match.group(1))
            secure_hash = request.rel_url.query.get("hash")

        return web.Response(
            text=await render_page(message_id, secure_hash, page=page),
            content_type="text/html",
        )

    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        return web.Response(status=499)
    except web.HTTPException:
        # HTTPBadRequest/HTTPForbidden/etc raised deliberately above (or by
        # aiohttp itself) ARE Exception subclasses, so without this they
        # fall straight into the catch-all below: logged as CRITICAL,
        # miscategorized as a 500 Internal Server Error instead of their
        # real status, and fire detect_error()'s auto-restart-on-error
        # trigger — all for a routine "bad path" hit. Let them through as
        # the intended response instead of hiding what they actually were.
        raise
    except Exception as e:
        logging.critical(f"Unhandled error on path {request.path!r}: {e}", exc_info=True)
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
            message_id = int(match.group(2))
        else:
            match = re.search(r"(\d+)(?:/\S+)?", path)
            if not match:
                raise web.HTTPBadRequest(text="Invalid file path")
            message_id = int(match.group(1))
            secure_hash = request.rel_url.query.get("hash")

        return await media_streamer(
            request,
            message_id,
            secure_hash,
        )

    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        return web.Response(status=499)
    except web.HTTPException:
        # Same fix as _render_page_route above — see that comment.
        raise
    except Exception as e:
        logging.critical(f"Unhandled error on path {request.path!r}: {e}", exc_info=True)
        asyncio.create_task(detect_error(e, context="route_handler"))
        raise web.HTTPInternalServerError(text=str(e))


def _parse_range(range_header: str, file_size: int):
    if not range_header:
        return 0, file_size - 1

    if not range_header.startswith("bytes="):
        raise ValueError("Invalid Range header")

    # Chrome/FDM normally sends one range. Multiple ranges are not useful
    # for this Telegram streaming backend.
    value = range_header[6:].split(",", 1)[0].strip()

    if "-" not in value:
        raise ValueError("Invalid Range header")

    start_str, end_str = value.split("-", 1)

    if not start_str:
        # Suffix range: bytes=-N
        suffix_length = int(end_str)
        if suffix_length <= 0:
            raise ValueError("Invalid suffix range")
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1

    if start < 0 or start >= file_size or end < start:
        raise ValueError("Range not satisfiable")

    return start, min(end, file_size - 1)


async def media_streamer(
    request: web.Request,
    message_id: int,
    secure_hash: str,
):
    if not multi_clients:
        raise web.HTTPServiceUnavailable(text="No Telegram clients available")

    # Atomic pick + reservation: no await between these operations.
    index = min(work_loads, key=work_loads.get)
    work_loads[index] += 1
    reserved = True

    faster_client = multi_clients[index]

    try:
        if faster_client in class_cache:
            tg_connect = class_cache[faster_client]
        else:
            tg_connect = ByteStreamer(faster_client)
            class_cache[faster_client] = tg_connect

        file_id = await tg_connect.get_file_properties(message_id)

        if secure_hash and file_id.unique_id[:6] != secure_hash:
            raise InvalidHash

        file_size = file_id.file_size

        if file_size <= 0:
            raise web.HTTPNotFound(text="Empty file")

        range_header = request.headers.get("Range", "")

        try:
            from_bytes, until_bytes = _parse_range(
                range_header,
                file_size,
            )
        except (ValueError, TypeError):
            return web.Response(
                status=416,
                text="416: Range not satisfiable",
                headers={
                    "Content-Range": f"bytes */{file_size}",
                    "Accept-Ranges": "bytes",
                },
            )

        offset = from_bytes - (from_bytes % CHUNK_SIZE)
        first_part_cut = from_bytes - offset
        last_part_cut = until_bytes % CHUNK_SIZE + 1

        req_length = until_bytes - from_bytes + 1

        # Number of Telegram 1 MiB chunks needed by this HTTP Range.
        part_count = (
            (until_bytes // CHUNK_SIZE)
            - (offset // CHUNK_SIZE)
            + 1
        )

        mime_type = file_id.mime_type
        file_name = file_id.file_name

        if mime_type:
            if not file_name:
                try:
                    ext = mime_type.split("/", 1)[1]
                except (IndexError, AttributeError):
                    ext = "unknown"
                file_name = f"{secrets.token_hex(2)}.{ext}"
        else:
            if file_name:
                mime_type = (
                    mimetypes.guess_type(file_name)[0]
                    or "application/octet-stream"
                )
            else:
                mime_type = "application/octet-stream"
                file_name = f"{secrets.token_hex(2)}.unknown"

        try:
            file_name.encode("ascii")
            disposition = f'attachment; filename="{file_name}"'
        except UnicodeEncodeError:
            encoded = urllib.parse.quote(file_name, safe="")
            disposition = f"attachment; filename*=UTF-8''{encoded}"

        status = 206 if range_header else 200

        response = web.StreamResponse(
            status=status,
            headers={
                "Content-Type": mime_type,
                "Content-Length": str(req_length),
                "Content-Disposition": disposition,
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-store",
                "Content-Range": (
                    f"bytes {from_bytes}-{until_bytes}/{file_size}"
                ),
            },
        )

        await response.prepare(request)

        body = tg_connect.yield_file(
            file_id=file_id,
            index=index,
            offset=offset,
            first_part_cut=first_part_cut,
            last_part_cut=last_part_cut,
            part_count=part_count,
            chunk_size=CHUNK_SIZE,
        )

        # The generator now owns the reservation and will release it in
        # its finally block, including browser/FDM disconnects.
        reserved = False

        try:
            async for chunk in body:
                await response.write(chunk)
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            logging.debug(
                "HTTP client disconnected from client %s",
                index,
            )
        finally:
            await body.aclose()

        try:
            await response.write_eof()
        except (ConnectionResetError, BrokenPipeError):
            pass

        return response

    finally:
        # Handles failures occurring before yield_file() takes ownership.
        if reserved and index in work_loads and work_loads[index] > 0:
            work_loads[index] -= 1
