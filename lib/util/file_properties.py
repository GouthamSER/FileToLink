import mimetypes
from pyrogram import Client
from typing import Any, Optional
from pyrogram.types import Message
from pyrogram.file_id import FileId
from pyrogram.raw.types.messages import Messages
from lib.server.exceptions import FIleNotFound


async def parse_file_id(message: "Message") -> Optional[FileId]:
    media = get_media_from_message(message)
    if media:
        return FileId.decode(media.file_id)

async def parse_file_unique_id(message: "Messages") -> Optional[str]:
    media = get_media_from_message(message)
    if media:
        return media.file_unique_id

async def get_file_ids(client: Client, chat_id: int, id: int) -> Optional[FileId]:
    message = await client.get_messages(chat_id, id)
    if message.empty:
        raise FIleNotFound
    media = get_media_from_message(message)
    file_unique_id = await parse_file_unique_id(message)
    file_id = await parse_file_id(message)
    mime_type = getattr(media, "mime_type", "") or ""
    # media.file_name can exist as an actual None (photos, voice notes, video
    # notes, some videos) rather than being absent, so getattr's default
    # doesn't help - guard explicitly and synthesize a name.
    file_name = getattr(media, "file_name", None) or None
    if not file_name:
        ext = mimetypes.guess_extension(mime_type) or ""
        if not ext and mime_type.startswith("video"):
            ext = ".mp4"
        elif not ext and mime_type.startswith("audio"):
            ext = ".mp3"
        elif not ext and mime_type.startswith("image"):
            ext = ".jpg"
        file_name = f"file_{file_unique_id or id}{ext}"
    setattr(file_id, "file_size", getattr(media, "file_size", 0))
    setattr(file_id, "mime_type", mime_type)
    setattr(file_id, "file_name", file_name)
    setattr(file_id, "unique_id", file_unique_id)
    return file_id

def get_media_from_message(message: "Message") -> Any:
    media_types = (
        "audio",
        "document",
        "photo",
        "sticker",
        "animation",
        "video",
        "voice",
        "video_note",
    )
    for attr in media_types:
        media = getattr(message, attr, None)
        if media:
            return media


def get_hash(media_msg: Message) -> str:
    media = get_media_from_message(media_msg)
    return getattr(media, "file_unique_id", "")[:6]

def get_name(media_msg: Message) -> str:
    media = get_media_from_message(media_msg)
    return getattr(media, 'file_name', None) or ""

def get_media_file_size(m):
    media = get_media_from_message(m)
    return getattr(media, "file_size", 0)
