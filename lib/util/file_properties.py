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
    if not media:
        raise FIleNotFound
    file_unique_id = await parse_file_unique_id(message)
    file_id = await parse_file_id(message)
    if not file_id:
        raise FIleNotFound

    mime_type = getattr(media, "mime_type", "") or ""
    if not mime_type:
        media_type = getattr(message, "media", None)
        type_name = media_type.value if media_type else ""
        if type_name == "photo":
            mime_type = "image/jpeg"
        elif type_name in ("video", "video_note", "animation"):
            mime_type = "video/mp4"
        elif type_name in ("audio", "voice"):
            mime_type = "audio/ogg" if type_name == "voice" else "audio/mpeg"
        elif type_name == "sticker":
            mime_type = "image/webp"

    file_name = getattr(media, "file_name", None) or None
    if not file_name:
        file_name = get_name(message)
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
    if not media:
        return ""
    file_name = getattr(media, 'file_name', None)
    if file_name:
        return file_name
    mime_type = getattr(media, 'mime_type', '') or ''
    media_type = getattr(media_msg, 'media', None)
    type_name = media_type.value if media_type else 'file'
    ext = mimetypes.guess_extension(mime_type) or ''
    if not ext:
        if type_name == 'photo' or mime_type.startswith('image'):
            ext = '.jpg'
        elif type_name in ('video', 'video_note', 'animation') or mime_type.startswith('video'):
            ext = '.mp4'
        elif type_name in ('audio', 'voice') or mime_type.startswith('audio'):
            ext = '.mp3' if type_name == 'audio' else '.ogg'
        elif type_name == 'sticker':
            ext = '.webp'
    unique_id = getattr(media, 'file_unique_id', '')
    return f"{type_name}_{unique_id[:8]}{ext}" if unique_id else f"{type_name}{ext}"

def get_media_file_size(m):
    media = get_media_from_message(m)
    return getattr(media, "file_size", 0)
