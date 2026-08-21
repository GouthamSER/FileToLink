import math
import asyncio
import logging
from info import *
from typing import Dict, Union
from lib.bot import work_loads
from pyrogram import Client, utils, raw
from lib.util.file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid, FloodWait, RPCError
from lib.server.exceptions import FIleNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource


# Number of chunks to prefetch concurrently.
# Pipelining these requests hides the per-chunk Telegram MTProto round-trip
# and is the single biggest speed improvement without adding extra bot clients.
PREFETCH_SIZE = 3

# How many chunks a SINGLE stream fetches from Telegram in parallel.
# Chunks were previously fetched strictly one-at-a-time — speed per viewer
# was capped at chunk_size / round-trip-time regardless of how many
# MULTI_TOKEN clients exist (client count only affects how many DIFFERENT
# viewers can stream at once, not one viewer's own speed). Fetching a
# small window concurrently hides RTT and raises single-stream throughput.
# Keep this modest — Telegram will FloodWait a client that fires too many
# parallel upload.GetFile calls, and that hurts every viewer on it, not
# just this one.
CONCURRENT_FETCHES = 2

# Strong references to in-flight prefetch producer tasks. asyncio's event
# loop only keeps a WEAK reference to Tasks created with create_task(); a
# pending task with no other referrer can be garbage-collected mid-flight,
# which is what caused the "coroutine ignored GeneratorExit" spam under
# multi-client load. See yield_file() below.
_BG_PRODUCER_TASKS: set = set()


class ByteStreamer:
    def __init__(self, client: Client):
        """A custom class that holds the cache of a specific client and class functions.
        attributes:
            client: the client that the cache is for.
            cached_file_ids: a dict of cached file IDs.

        functions:
            generate_file_properties: returns the properties for a media of a specific message.
            generate_media_session: returns the media session for the DC that contains the media file.
            yield_file: yield a file from telegram servers for streaming.

        This is a modified version of the <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/telegram/utils/custom_download.py>
        Thanks to Eyaadh <https://github.com/eyaadh>
        """
        self.clean_timer = 30 * 60
        self.client: Client = client
        self.cached_file_ids: Dict[int, FileId] = {}
        asyncio.create_task(self.clean_cache())

    async def get_file_properties(self, id: int) -> FileId:
        """
        Returns the properties of a media of a specific message in a FileId class.
        If the properties are cached it returns them directly, otherwise it generates
        and caches them from the Message ID.
        """
        if id not in self.cached_file_ids:
            await self.generate_file_properties(id)
            logging.debug(f"Cached file properties for message with ID {id}")
        return self.cached_file_ids[id]

    async def generate_file_properties(self, id: int) -> FileId:
        """
        Generates the properties of a media file on a specific message.
        Returns the properties in a FileId class.
        """
        file_id = await get_file_ids(self.client, LOG_CHANNEL, id)
        logging.debug(f"Generated file ID and Unique ID for message with ID {id}")
        if not file_id:
            logging.debug(f"Message with ID {id} not found")
            raise FIleNotFound
        self.cached_file_ids[id] = file_id
        logging.debug(f"Cached media message with ID {id}")
        return self.cached_file_ids[id]

    async def generate_media_session(self, client: Client, file_id: FileId) -> Session:
        """
        Generates the media session for the DC that contains the media file.
        Required for getting bytes from Telegram servers.
        """
        media_session = client.media_sessions.get(file_id.dc_id, None)

        if media_session is None:
            if file_id.dc_id != await client.storage.dc_id():
                media_session = Session(
                    client,
                    file_id.dc_id,
                    await Auth(
                        client, file_id.dc_id, await client.storage.test_mode()
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
                                id=exported_auth.id, bytes=exported_auth.bytes
                            )
                        )
                        break
                    except AuthBytesInvalid:
                        logging.debug(
                            f"Invalid authorization bytes for DC {file_id.dc_id}"
                        )
                        continue
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
            logging.debug(f"Created media session for DC {file_id.dc_id}")
            client.media_sessions[file_id.dc_id] = media_session
        else:
            logging.debug(f"Using cached media session for DC {file_id.dc_id}")
        return media_session

    @staticmethod
    async def get_location(
        file_id: FileId,
    ) -> Union[
        raw.types.InputPhotoFileLocation,
        raw.types.InputDocumentFileLocation,
        raw.types.InputPeerPhotoFileLocation,
    ]:
        """
        Returns the file location for the media file.
        """
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id, access_hash=file_id.chat_access_hash
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=utils.get_channel_id(file_id.chat_id),
                        access_hash=file_id.chat_access_hash,
                    )
            location = raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )
        elif file_type == FileType.PHOTO:
            location = raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        else:
            location = raw.types.InputDocumentFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        return location

    async def _fetch_chunk(
        self,
        media_session: Session,
        location,
        offset: int,
        chunk_size: int,
        retries: int = 5,
    ) -> bytes:
        """
        Fetches a single chunk from Telegram with automatic retry and back-off.

        Retrying on transient errors (timeout, connection reset) is critical:
        without it a single Telegram hiccup aborts the entire download, which
        forces Chrome to restart from byte 0 instead of just resuming.
        """
        delay = 1
        last_exc = None
        for attempt in range(retries):
            try:
                r = await media_session.send(
                    raw.functions.upload.GetFile(
                        location=location,
                        offset=offset,
                        limit=chunk_size,
                    ),
                )
                if isinstance(r, raw.types.upload.File):
                    return r.bytes
                return b""
            except FloodWait as e:
                wait = e.value + 1
                logging.warning(f"FloodWait: sleeping {wait}s (attempt {attempt + 1})")
                await asyncio.sleep(wait)
                last_exc = e
            except (TimeoutError, asyncio.TimeoutError) as e:
                logging.warning(
                    f"Timeout at offset {offset} (attempt {attempt + 1}/{retries}), retrying in {delay}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
                last_exc = e
            except (ConnectionError, ConnectionResetError, OSError) as e:
                logging.warning(
                    f"Connection error at offset {offset} "
                    f"(attempt {attempt + 1}/{retries}): {e}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
                last_exc = e
            except RPCError as e:
                # Telegram-side hiccups ("[-503 Timeout] Telegram is having
                # internal problems...", occasional 5xx-style RPC errors)
                # are transient — Telegram's servers, not ours. Previously
                # these fell through to the bare Exception handler below
                # and instantly killed the whole stream for that viewer.
                # Retry with backoff same as a connection error.
                logging.warning(
                    f"Telegram RPC error at offset {offset} "
                    f"(attempt {attempt + 1}/{retries}): {e}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
                last_exc = e
            except Exception as e:
                logging.error(f"Unexpected error fetching chunk at offset {offset}: {e}")
                raise

        logging.error(f"All {retries} retries exhausted for chunk at offset {offset}")
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
    ) -> Union[str, None]:
        """
        Async generator that yields the bytes of a media file.

        Improvements over the original:
          1. Pipelined prefetch — PREFETCH_SIZE chunks are requested
             concurrently so Telegram RTT is hidden between yields.
          2. Retry with back-off — transient timeouts/connection errors are
             retried automatically instead of silently aborting the stream.
          3. Broad exception handling — unexpected errors are logged and
             re-raised so aiohttp closes the connection cleanly, letting
             Chrome resume via a Range request rather than restart from 0.

        Modded from <https://github.com/eyaadh/megadlbot_oss>
        Thanks to Eyaadh <https://github.com/eyaadh>
        """
        client = self.client
        # NOTE: work_loads[index] is reserved by the CALLER (route.py's
        # media_streamer, atomically with client selection) before this
        # generator is even created — see media_streamer for why. This
        # generator only owns the RELEASE, which happens exactly once in
        # the finally block below once actual streaming ends.
        logging.debug(f"Starting to yield file with client {index}.")
        try:
            media_session = await self.generate_media_session(client, file_id)
            location = await self.get_location(file_id)
        except Exception:
            work_loads[index] -= 1
            raise

        # Pre-build the ordered list of byte offsets for each chunk.
        offsets = [offset + i * chunk_size for i in range(part_count)]

        # Pipeline buffer: producer fetches ahead, consumer yields in order.
        queue: asyncio.Queue = asyncio.Queue(maxsize=PREFETCH_SIZE)
        _SENTINEL = object()
        # Cooperative stop flag — checked between chunk fetches only, never
        # while a fetch is in-flight. Hard-cancelling a task mid-fetch (i.e.
        # while it's suspended inside Pyrogram's network/executor bridge)
        # can leave that bridge's internal Future in a half-registered state;
        # the loop later force-closes the orphaned coroutine with
        # GeneratorExit, which is exactly the "Exception ignored in ...
        # producer / RuntimeError: coroutine ignored GeneratorExit" spam.
        stop_event = asyncio.Event()

        async def producer():
            try:
                i = 0
                n = len(offsets)
                while i < n:
                    if stop_event.is_set():
                        break
                    batch = offsets[i : i + CONCURRENT_FETCHES]
                    # Fetch this window in parallel — order preserved because
                    # we only push results to the queue after the whole
                    # batch resolves, and gather() keeps input order.
                    results = await asyncio.gather(
                        *[
                            self._fetch_chunk(media_session, location, o, chunk_size)
                            for o in batch
                        ]
                    )
                    for chunk in results:
                        if stop_event.is_set():
                            break
                        await queue.put(chunk)
                    i += len(batch)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logging.error(f"Prefetch producer error: {e}")
                try:
                    queue.put_nowait(e)  # Forward exception to consumer
                except asyncio.QueueFull:
                    pass
            finally:
                try:
                    queue.put_nowait(_SENTINEL)
                except asyncio.QueueFull:
                    pass

        producer_task = asyncio.create_task(producer())
        # asyncio only holds a WEAK ref to tasks internally — with nothing
        # else referencing it, GC can reap a still-pending task early. This
        # module-level set keeps a strong ref alive until the task is done.
        _BG_PRODUCER_TASKS.add(producer_task)
        producer_task.add_done_callback(_BG_PRODUCER_TASKS.discard)
        current_part = 1

        try:
            while True:
                item = await queue.get()

                if item is _SENTINEL:
                    break

                if isinstance(item, Exception):
                    raise item  # aiohttp closes cleanly; Chrome can resume

                chunk: bytes = item
                if not chunk:
                    break

                if part_count == 1:
                    yield chunk[first_part_cut:last_part_cut]
                elif current_part == 1:
                    yield chunk[first_part_cut:]
                elif current_part == part_count:
                    yield chunk[:last_part_cut]
                else:
                    yield chunk

                current_part += 1

        except GeneratorExit:
            # Client disconnected mid-download — signal the producer to stop.
            logging.debug("Client disconnected; stopping prefetch producer.")
            stop_event.set()
            raise
        except Exception as e:
            logging.error(f"Error while streaming file: {e}")
            stop_event.set()
            raise
        finally:
            stop_event.set()
            if not producer_task.done():
                # Give the in-flight fetch a chance to finish on its own
                # (cooperative stop) instead of yanking it mid-await.
                # asyncio.shield protects producer_task from being cancelled
                # a second time if THIS await itself gets cancelled/closed
                # (e.g. our own generator is being force-closed too) — it
                # keeps running in the background, held alive by
                # _BG_PRODUCER_TASKS, and cleans itself up.
                try:
                    await asyncio.wait_for(asyncio.shield(producer_task), timeout=5)
                except asyncio.TimeoutError:
                    logging.warning(
                        "Prefetch producer didn't stop in time; force-cancelling."
                    )
                    producer_task.cancel()
                except (asyncio.CancelledError, Exception):
                    pass
            logging.debug(f"Finished yielding file with {current_part} parts.")
            work_loads[index] -= 1

    async def clean_cache(self) -> None:
        """
        Periodically clears the in-memory file-ID cache to reduce memory usage.
        """
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()
            logging.debug("Cleaned the cache")


async def cancel_all_producers() -> None:
    """Cancel any still-running prefetch producer tasks on shutdown.

    Without this, in-flight stream downloads keep sockets/tasks alive and
    the process can miss the platform's SIGTERM grace window (Heroku R12,
    Koyeb/Render equivalents), getting force-killed instead of exiting clean.
    """
    tasks = list(_BG_PRODUCER_TASKS)
    if not tasks:
        return
    for t in tasks:
        if not t.done():
            t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logging.info(f"Cancelled {len(tasks)} in-flight stream producer task(s) for shutdown")
