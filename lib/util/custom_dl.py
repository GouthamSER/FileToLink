import math
import asyncio
import logging
from info import *
from typing import Dict, Union
from lib.bot import work_loads, multi_clients
from pyrogram import Client, utils, raw
from lib.util.file_properties import get_file_ids
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid, FloodWait, RPCError
from lib.server.exceptions import FIleNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource

PREFETCH_SIZE = 4
CONCURRENT_FETCHES = 3

_BG_PRODUCER_TASKS: set = set()


class ByteStreamer:
    def __init__(self, client: Client):
        self.clean_timer = 30 * 60
        self.client: Client = client
        self.cached_file_ids: Dict[int, FileId] = {}
        asyncio.create_task(self.clean_cache())

    async def get_file_properties(self, id: int) -> FileId:
        if id not in self.cached_file_ids:
            await self.generate_file_properties(id)
            logging.debug(f"Cached file properties for message with ID {id}")
        return self.cached_file_ids[id]

    async def generate_file_properties(self, id: int) -> FileId:
        file_id = await get_file_ids(self.client, LOG_CHANNEL, id)

        if not file_id and self.client is not multi_clients.get(0):
            logging.warning(
                f"Client couldn't read message {id} from LOG_CHANNEL "
                f"(likely missing admin access there) - retrying with main client."
            )
            main_client = multi_clients.get(0)
            if main_client:
                file_id = await get_file_ids(main_client, LOG_CHANNEL, id)

        logging.debug(f"Generated file ID and Unique ID for message with ID {id}")

        if not file_id:
            logging.debug(f"Message with ID {id} not found")
            raise FIleNotFound

        self.cached_file_ids[id] = file_id
        logging.debug(f"Cached media message with ID {id}")
        return self.cached_file_ids[id]

    async def generate_media_session(
        self,
        client: Client,
        file_id: FileId
    ) -> Session:
        media_session = client.media_sessions.get(file_id.dc_id, None)

        if media_session is None:
            if file_id.dc_id != await client.storage.dc_id():
                media_session = Session(
                    client,
                    file_id.dc_id,
                    await Auth(
                        client,
                        file_id.dc_id,
                        await client.storage.test_mode()
                    ).create(),
                    await client.storage.test_mode(),
                    is_media=True,
                )
                await media_session.start()

                for _ in range(6):
                    exported_auth = await client.invoke(
                        raw.functions.auth.ExportAuthorization(
                            dc_id=file_id.dc_id
                        )
                    )
                    try:
                        await media_session.send(
                            raw.functions.auth.ImportAuthorization(
                                id=exported_auth.id,
                                bytes=exported_auth.bytes
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
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id,
                    access_hash=file_id.chat_access_hash
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(
                        chat_id=-file_id.chat_id
                    )
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=utils.get_channel_id(file_id.chat_id),
                        access_hash=file_id.chat_access_hash
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
        retries: int = 7,
    ) -> bytes:
        delay = 1
        last_exc = None

        for attempt in range(retries):
            try:
                result = await media_session.send(
                    raw.functions.upload.GetFile(
                        location=location,
                        offset=offset,
                        limit=chunk_size,
                    ),
                )

                if isinstance(result, raw.types.upload.File):
                    return result.bytes

                return b""

            except FloodWait as e:
                wait = e.value + 1
                logging.warning(
                    f"FloodWait: sleeping {wait}s (attempt {attempt + 1})"
                )
                await asyncio.sleep(wait)
                last_exc = e

            except (TimeoutError, asyncio.TimeoutError) as e:
                logging.warning(
                    f"Timeout at offset {offset} "
                    f"(attempt {attempt + 1}/{retries}), "
                    f"retrying in {delay}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
                last_exc = e

            except (ConnectionError, ConnectionResetError, OSError) as e:
                logging.warning(
                    f"Connection error at offset {offset} "
                    f"(attempt {attempt + 1}/{retries}): {e}, "
                    f"retrying in {delay}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
                last_exc = e

            except RPCError as e:
                logging.warning(
                    f"Telegram RPC error at offset {offset} "
                    f"(attempt {attempt + 1}/{retries}): {e}, "
                    f"retrying in {delay}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
                last_exc = e

            except Exception as e:
                logging.error(
                    f"Unexpected error fetching chunk at offset {offset}: {e}"
                )
                raise

        logging.error(
            f"All {retries} retries exhausted for chunk at offset {offset}"
        )
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
        client = self.client
        logging.debug(f"Starting to yield file with client {index}.")

        try:
            media_session = await self.generate_media_session(client, file_id)
            location = await self.get_location(file_id)
        except Exception:
            work_loads[index] -= 1
            raise

        offsets = [
            offset + i * chunk_size
            for i in range(part_count)
        ]

        queue: asyncio.Queue = asyncio.Queue(maxsize=PREFETCH_SIZE)
        _SENTINEL = object()
        stop_event = asyncio.Event()

        async def producer():
            try:
                i = 0
                total = len(offsets)

                while i < total:
                    if stop_event.is_set():
                        break

                    batch = offsets[i:i + CONCURRENT_FETCHES]

                    results = await asyncio.gather(
                        *[
                            self._fetch_chunk(
                                media_session,
                                location,
                                current_offset,
                                chunk_size
                            )
                            for current_offset in batch
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
                    queue.put_nowait(e)
                except asyncio.QueueFull:
                    pass

            finally:
                try:
                    queue.put_nowait(_SENTINEL)
                except asyncio.QueueFull:
                    pass

        producer_task = asyncio.create_task(producer())
        _BG_PRODUCER_TASKS.add(producer_task)
        producer_task.add_done_callback(_BG_PRODUCER_TASKS.discard)

        current_part = 1

        try:
            while True:
                item = await queue.get()

                if item is _SENTINEL:
                    break

                if isinstance(item, Exception):
                    raise item

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
            logging.debug(
                "Client disconnected; stopping prefetch producer."
            )
            stop_event.set()
            raise

        except Exception as e:
            logging.error(f"Error while streaming file: {e}")
            stop_event.set()
            raise

        finally:
            stop_event.set()

            if not producer_task.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(producer_task),
                        timeout=5
                    )
                except asyncio.TimeoutError:
                    logging.warning(
                        "Prefetch producer didn't stop in time; "
                        "force-cancelling."
                    )
                    producer_task.cancel()
                except (asyncio.CancelledError, Exception):
                    pass

            logging.debug(
                f"Finished yielding file with {current_part} parts."
            )
            work_loads[index] -= 1

    async def clean_cache(self) -> None:
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()
            logging.debug("Cleaned the cache")


async def cancel_all_producers() -> None:
    tasks = list(_BG_PRODUCER_TASKS)

    if not tasks:
        return

    for task in tasks:
        if not task.done():
            task.cancel()

    await asyncio.gather(
        *tasks,
        return_exceptions=True
    )

    logging.info(
        f"Cancelled {len(tasks)} "
        f"in-flight stream producer task(s) for shutdown"
    )
