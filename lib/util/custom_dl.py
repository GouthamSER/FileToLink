import math
import asyncio
import logging
from info import *
from typing import Dict, Union
from lib.bot import work_loads
from pyrogram import Client, utils, raw
from lib.util.file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid, FloodWait
from lib.server.exceptions import FIleNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource


# Number of chunks to prefetch concurrently.
# Pipelining these requests hides the per-chunk Telegram MTProto round-trip
# and is the single biggest speed improvement without adding extra bot clients.
PREFETCH_SIZE = 3


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
        work_loads[index] += 1
        logging.debug(f"Starting to yield file with client {index}.")
        media_session = await self.generate_media_session(client, file_id)
        location = await self.get_location(file_id)

        # Pre-build the ordered list of byte offsets for each chunk.
        offsets = [offset + i * chunk_size for i in range(part_count)]

        # Pipeline buffer: producer fetches ahead, consumer yields in order.
        queue: asyncio.Queue = asyncio.Queue(maxsize=PREFETCH_SIZE)
        _SENTINEL = object()

        async def producer():
            try:
                for chunk_offset in offsets:
                    chunk = await self._fetch_chunk(
                        media_session, location, chunk_offset, chunk_size
                    )
                    await queue.put(chunk)
            except Exception as e:
                logging.error(f"Prefetch producer error: {e}")
                await queue.put(e)  # Forward exception to consumer
            finally:
                await queue.put(_SENTINEL)

        producer_task = asyncio.create_task(producer())
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
            # Client disconnected mid-download — cancel prefetch to avoid leaking tasks.
            logging.debug("Client disconnected; cancelling prefetch producer.")
            producer_task.cancel()
        except Exception as e:
            logging.error(f"Error while streaming file: {e}")
            producer_task.cancel()
            raise
        finally:
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
