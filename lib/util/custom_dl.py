import os
import math
import asyncio
import logging
from collections import deque
from typing import Dict, Union

from info import *
from lib.bot import work_loads, multi_clients
from pyrogram import Client, utils, raw
from lib.util.file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid, FloodWait, RPCError, BadRequest
from lib.server.exceptions import FIleNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource


# Tuned for 22–23 Telegram clients.
# Telegram GetFile uses 1 MiB chunks.
CHUNK_SIZE = 1024 * 1024

def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


# Number of chunks fetched in parallel by ONE HTTP stream.
# One Telegram connection is latency bound: more requests in flight = more
# speed. Env tunable: STREAM_CONCURRENCY.
CONCURRENT_FETCHES = _env_int("STREAM_CONCURRENCY", 6)

# Number of chunks kept ready in the HTTP pipeline (memory = N MiB/stream).
PREFETCH_SIZE = _env_int("STREAM_PREFETCH", 10)

# Maximum simultaneous Telegram GetFile requests handled by ONE
# Telegram client across ALL users/streams using that client.
MAX_CLIENT_FETCHES = _env_int("CLIENT_MAX_FETCHES", 12)

# Per-request timeout. Session.send default is 15s -> false timeouts on slow
# links. Pyrogram's own downloader uses MEDIA_WAIT_TIMEOUT (60s).
FETCH_TIMEOUT = getattr(Session, "MEDIA_WAIT_TIMEOUT", 60)

# How long file properties remain cached.
CACHE_CLEAN_INTERVAL = 30 * 60

# Strong references to active producer tasks.
_BG_PRODUCER_TASKS: set = set()

# One semaphore per Pyrogram client.
_CLIENT_SEMAPHORES: Dict[object, asyncio.Semaphore] = {}

# Protect media-session creation when many FDM Range requests arrive together.
_CLIENT_SESSION_LOCKS: Dict[object, asyncio.Lock] = {}

# Protect first-time metadata generation for the same message.
_FILE_LOCKS: Dict[tuple, asyncio.Lock] = {}


def _get_client_semaphore(client: Client) -> asyncio.Semaphore:
    semaphore = _CLIENT_SEMAPHORES.get(client)
    if semaphore is None:
        semaphore = asyncio.Semaphore(MAX_CLIENT_FETCHES)
        _CLIENT_SEMAPHORES[client] = semaphore
    return semaphore


def _get_session_lock(client: Client) -> asyncio.Lock:
    lock = _CLIENT_SESSION_LOCKS.get(client)
    if lock is None:
        lock = asyncio.Lock()
        _CLIENT_SESSION_LOCKS[client] = lock
    return lock


def _get_file_lock(client: Client, message_id: int) -> asyncio.Lock:
    key = (client, message_id)
    lock = _FILE_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _FILE_LOCKS[key] = lock
    return lock


class ByteStreamer:
    def __init__(self, client: Client):
        self.clean_timer = CACHE_CLEAN_INTERVAL
        self.client: Client = client
        self.cached_file_ids: Dict[int, FileId] = {}
        asyncio.create_task(self.clean_cache())

    async def get_file_properties(self, id: int) -> FileId:
        file_id = self.cached_file_ids.get(id)
        if file_id is not None:
            return file_id

        lock = _get_file_lock(self.client, id)
        async with lock:
            file_id = self.cached_file_ids.get(id)
            if file_id is not None:
                return file_id
            try:
                return await self.generate_file_properties(id)
            finally:
                _FILE_LOCKS.pop((self.client, id), None)

    async def generate_file_properties(self, id: int) -> FileId:
        file_id = await get_file_ids(self.client, LOG_CHANNEL, id)

        # Some multi-clients may not have access to LOG_CHANNEL.
        # Fall back to the main client before declaring the file missing.
        if not file_id and self.client is not multi_clients.get(0):
            main_client = multi_clients.get(0)
            if main_client:
                logging.warning(
                    "Client could not read message %s from LOG_CHANNEL; "
                    "retrying with main client.",
                    id,
                )
                file_id = await get_file_ids(main_client, LOG_CHANNEL, id)

        if not file_id:
            raise FIleNotFound

        self.cached_file_ids[id] = file_id
        return file_id

    async def generate_media_session(self, client: Client, file_id: FileId) -> Session:
        media_session = client.media_sessions.get(file_id.dc_id)
        if media_session is not None:
            return media_session

        lock = _get_session_lock(client)
        async with lock:
            media_session = client.media_sessions.get(file_id.dc_id)
            if media_session is not None:
                return media_session

            if file_id.dc_id != await client.storage.dc_id():
                media_session = Session(
                    client,
                    file_id.dc_id,
                    await Auth(
                        client,
                        file_id.dc_id,
                        await client.storage.test_mode(),
                    ).create(),
                    await client.storage.test_mode(),
                    is_media=True,
                )
                await media_session.start()

                for _ in range(6):
                    exported_auth = await client.invoke(
                        raw.functions.auth.ExportAuthorization(dc_id=file_id.dc_id)
                    )
                    try:
                        await media_session.send(
                            raw.functions.auth.ImportAuthorization(
                                id=exported_auth.id,
                                bytes=exported_auth.bytes,
                            )
                        )
                        break
                    except AuthBytesInvalid:
                        logging.debug(
                            "Invalid authorization bytes for DC %s",
                            file_id.dc_id,
                        )
                else:
                    await media_session.stop()
                    raise AuthBytesInvalid
            else:
                media_session = Session(
                    client,
                    file_id.dc_id,
                    await client.storage.auth_key(),
                    await client.storage.test_mode(),
                    is_media=True,
                )
                await media_session.start()

            client.media_sessions[file_id.dc_id] = media_session
            return media_session

    @staticmethod
    async def get_location(file_id: FileId) -> Union[
        raw.types.InputPhotoFileLocation,
        raw.types.InputDocumentFileLocation,
        raw.types.InputPeerPhotoFileLocation,
    ]:
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id,
                    access_hash=file_id.chat_access_hash,
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(
                        chat_id=-file_id.chat_id
                    )
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=utils.get_channel_id(file_id.chat_id),
                        access_hash=file_id.chat_access_hash,
                    )

            return raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )

        if file_type == FileType.PHOTO:
            return raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )

        return raw.types.InputDocumentFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size,
        )

    async def refresh_location(self, message_id: int):
        """Re-read message -> fresh file_reference. Fixes FILE_REFERENCE_EXPIRED
        mid-download instead of killing the stream."""
        self.cached_file_ids.pop(message_id, None)
        file_id = await self.generate_file_properties(message_id)
        return file_id, await self.get_location(file_id)

    async def _fetch_chunk(
        self,
        media_session: Session,
        state: dict,
        offset: int,
        chunk_size: int,
        client_index,
        file_size: int,
        message_id: int = None,
        retries: int = 8,
    ) -> bytes:
        """Fetch ONE full chunk. Never returns a short/empty chunk unless EOF.

        Telegram may answer a GetFile with fewer bytes than asked; old code
        passed that on as-is -> silent truncation / corrupt file. Here we
        top up until the chunk is complete, and retry on any transient error.
        """
        semaphore = _get_client_semaphore(self.client)
        expected = min(chunk_size, file_size - offset) if file_size else chunk_size
        delay = 1
        last_exc = None
        refreshed = False

        for attempt in range(1, retries + 1):
            try:
                buf = bytearray()
                while len(buf) < expected:
                    # Semaphore is PER TELEGRAM CLIENT, not per user.
                    async with semaphore:
                        result = await media_session.invoke(
                            raw.functions.upload.GetFile(
                                location=state["location"],
                                offset=offset + len(buf),
                                limit=chunk_size,
                            ),
                            timeout=FETCH_TIMEOUT,
                        )
                    data = result.bytes if isinstance(result, raw.types.upload.File) else b""
                    if not data:
                        raise ConnectionError(
                            f"empty GetFile reply at offset {offset + len(buf)} "
                            f"(have {len(buf)}/{expected})"
                        )
                    buf += data
                # Telegram can over-return when offset isn't chunk-aligned; trim.
                return bytes(buf[:expected]) if len(buf) > expected else bytes(buf)

            except FloodWait as exc:
                last_exc = exc
                wait = int(exc.value) + 1
                logging.warning(
                    "Client %s FloodWait %ss at offset %s (attempt %s/%s)",
                    client_index, wait, offset, attempt, retries,
                )
                await asyncio.sleep(wait)

            except BadRequest as exc:
                # FILE_REFERENCE_EXPIRED: refresh once and retry. Other
                # BadRequests (LOCATION_INVALID, OFFSET_INVALID) can never
                # succeed -> fail fast.
                if (
                    not refreshed
                    and message_id is not None
                    and "FILE_REFERENCE" in str(exc).upper()
                ):
                    refreshed = True
                    last_exc = exc
                    logging.warning("File reference expired, refreshing msg %s", message_id)
                    _, state["location"] = await self.refresh_location(message_id)
                    continue
                raise

            except (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError, RPCError) as exc:
                last_exc = exc
                logging.warning(
                    "Client %s error at offset %s (attempt %s/%s), retry in %ss: %r",
                    client_index, offset, attempt, retries, delay, exc,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)

        raise last_exc

    async def yield_file(
        self,
        file_id: FileId,
        index: int,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
        message_id: int = None,
    ):
        """
        Ordered async generator for Telegram -> HTTP streaming.

        Client selection/load reservation is performed by routes.py before
        this generator starts. This generator releases that reservation once
        streaming ends or the browser/FDM connection closes.
        """
        producer_task = None
        stop_event = asyncio.Event()

        try:
            media_session = await self.generate_media_session(self.client, file_id)
            state = {"location": await self.get_location(file_id)}
            file_size = getattr(file_id, "file_size", 0) or 0

            offsets = [
                offset + i * chunk_size
                for i in range(part_count)
            ]

            queue = asyncio.Queue(maxsize=PREFETCH_SIZE)
            sentinel = object()

            async def producer():
                # Sliding window: always keep CONCURRENT_FETCHES requests in
                # flight, deliver strictly in order.
                pending = deque()
                offs = iter(offsets)

                def launch():
                    off = next(offs, None)
                    if off is None:
                        return
                    pending.append(
                        asyncio.ensure_future(
                            self._fetch_chunk(
                                media_session, state, off, chunk_size,
                                index, file_size, message_id,
                            )
                        )
                    )

                try:
                    for _ in range(CONCURRENT_FETCHES):
                        launch()

                    while pending and not stop_event.is_set():
                        chunk = await pending.popleft()
                        launch()
                        await queue.put(chunk)

                except asyncio.CancelledError:
                    stop_event.set()
                    raise
                except Exception as exc:
                    if isinstance(exc, BadRequest) and message_id is not None:
                        # stale file_reference -> force fresh metadata next req
                        self.cached_file_ids.pop(message_id, None)
                    logging.error(
                        "Prefetch producer error on client %s: %s",
                        index,
                        exc,
                    )
                    if not stop_event.is_set():
                        await queue.put(exc)
                finally:
                    for t in pending:
                        t.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    # Consumer alive -> must deliver sentinel (await, queue
                    # may be full). Cancelled/stopped -> NEVER await put():
                    # blocked forever on full queue, stale streams piled up.
                    if stop_event.is_set():
                        try:
                            queue.put_nowait(sentinel)
                        except asyncio.QueueFull:
                            pass
                    else:
                        await queue.put(sentinel)

            producer_task = asyncio.create_task(producer())
            _BG_PRODUCER_TASKS.add(producer_task)
            producer_task.add_done_callback(_BG_PRODUCER_TASKS.discard)

            current_part = 1

            while True:
                item = await queue.get()

                if item is sentinel:
                    break

                if isinstance(item, Exception):
                    raise item

                if part_count == 1:
                    out = item[first_part_cut:last_part_cut]
                elif current_part == 1:
                    out = item[first_part_cut:]
                elif current_part == part_count:
                    out = item[:last_part_cut]
                else:
                    out = item

                yield out
                current_part += 1

            # Producer ended early (no exception) = missing parts. Raise so
            # route closes socket -> client sees short body and re-requests,
            # instead of a silently truncated "finished" file.
            if current_part <= part_count:
                raise IOError(
                    f"stream ended early: got {current_part - 1}/{part_count} parts"
                )

        except (GeneratorExit, asyncio.CancelledError):
            stop_event.set()
            raise
        finally:
            stop_event.set()

            # Release the HTTP/client load reservation exactly once, FIRST,
            # so a slow producer teardown can't leak the counter.
            if index in work_loads and work_loads[index] > 0:
                work_loads[index] -= 1

            if producer_task is not None and not producer_task.done():
                producer_task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(producer_task), timeout=5)
                except BaseException:
                    pass

    async def clean_cache(self) -> None:
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()


async def cancel_all_producers() -> None:
    tasks = list(_BG_PRODUCER_TASKS)

    for task in tasks:
        if not task.done():
            task.cancel()

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
        logging.info(
            "Cancelled %s active stream producer task(s)",
            len(tasks),
    )
