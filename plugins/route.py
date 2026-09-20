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
from lib.util.render_template import render_page, render_home_page
from plugins.error_detection import detect_error


routes = web.RouteTableDef()
class_cache = {}


@routes.get("/", allow_head=True)
async def root_route_handler(request: web.Request):
    uptime_str = get_readable_time(int(time.time() - StartTime))
    total_clients = len(multi_clients)
    is_multi_client = total_clients > 1
    total_active_streams = sum(work_loads.values())

    clients = [
        {"client_id": cid, "active_streams": load}
        for cid, load in sorted(work_loads.items())
    ]

    if request.query.get("json") == "true":
        return web.json_response({
            "status": "online",
            "uptime": uptime_str,
            "multi_client": is_multi_client,
            "total_clients": total_clients,
            "active_streams": total_active_streams,
            "clients": clients,
        })

    html = await render_home_page(
        uptime_str=uptime_str,
        total_clients=total_clients,
        is_multi_client=is_multi_client,
        total_active_streams=total_active_streams,
        clients=clients,
    )
    return web.Response(text=html, content_type="text/html")


@routes.get(r"/watch/{path:.+}", allow_head=True)
@routes.get(r"/stream/{path:.+}", allow_head=True)
async def stream_handler(request: web.Request):
    return await _render_page_route(request, page="watch")


@routes.get(r"/download/{path:.+}", allow_head=True)
@routes.get(r"/view/{path:.+}", allow_head=True)
async def download_page_handler(request: web.Request):
    return await _render_page_route(request, page="dl")


@routes.get(r"/dl/{path:.+}", allow_head=True)
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
            match = re.search(r"(\d+)(?:/.*)?", path)
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
    except (AttributeError, BadStatusLine, ConnectionError, asyncio.CancelledError):
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


@routes.get(r"/{path:.+}", allow_head=True)
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
            match = re.search(r"(\d+)(?:/.*)?", path)
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
    except (AttributeError, BadStatusLine, ConnectionError, asyncio.CancelledError):
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

        clean_name = file_name.replace('"', '_')
        try:
            clean_name.encode("ascii")
            disposition = f'attachment; filename="{clean_name}"'
        except UnicodeEncodeError:
            encoded = urllib.parse.quote(clean_name, safe="")
            disposition = f"attachment; filename*=UTF-8''{encoded}"

        status = 206 if range_header else 200

        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(req_length),
            "Content-Disposition": disposition,
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-store",
        }
        if range_header:
            headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"

        response = web.StreamResponse(
            status=status,
            headers=headers,
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
        except (ConnectionError, asyncio.CancelledError):
            logging.debug(
                "HTTP client disconnected from client %s",
                index,
            )
        finally:
            await body.aclose()

        try:
            await response.write_eof()
        except (ConnectionError, asyncio.CancelledError):
            pass

        return response

    finally:
        # Handles failures occurring before yield_file() takes ownership.
        if reserved and index in work_loads and work_loads[index] > 0:
            work_loads[index] -= 1
