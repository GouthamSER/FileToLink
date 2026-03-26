import re, math, logging, secrets, mimetypes, urllib.parse
from info import *
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from lib.bot import File2Link, multi_clients, work_loads
from lib.server.exceptions import FIleNotFound, InvalidHash
from lib import StartTime, __version__
from lib.util.custom_dl import ByteStreamer
from lib.util.time_format import get_readable_time
from lib.util.render_template import render_page

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("I AM ALive BABy")


@routes.get(r"/watch/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
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
            text=await render_page(id, secure_hash), content_type="text/html"
        )
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical(e.with_traceback(None))
        raise web.HTTPInternalServerError(text=str(e))


@routes.get(r"/{path:\S+}", allow_head=True)
async def download_handler(request: web.Request):
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
        raise web.HTTPInternalServerError(text=str(e))


class_cache = {}


async def media_streamer(request: web.Request, id: int, secure_hash: str):
    range_header = request.headers.get("Range", "")

    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]

    if MULTI_CLIENT:
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

    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )

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
