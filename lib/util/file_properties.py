import os
import re
import mimetypes
from pyrogram import Client
from typing import Any, Optional
from pyrogram.types import Message
from pyrogram.file_id import FileId
from pyrogram.raw.types.messages import Messages
from lib.server.exceptions import FIleNotFound


def is_valid_ext(ext: str) -> bool:
    """Check if the extension looks like a valid file extension."""
    return bool(re.match(r'^\.[a-zA-Z0-9]{1,6}$', ext))


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

    raw_file_name = getattr(media, 'file_name', None) or ""
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

    # If raw_file_name has a valid extension, prioritize that extension
    if raw_file_name:
        _, raw_file_ext = os.path.splitext(raw_file_name)
        if is_valid_ext(raw_file_ext):
            ext = raw_file_ext

    # Check message caption for full, untruncated filename
    caption = getattr(media_msg, 'caption', None) or ""
    candidate = ""
    has_explicit_ext = False

    if caption and isinstance(caption, str):
        # 1. Clean markdown links: [text](url) -> [text]
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'[\1]', caption)
        # 2. Clean HTML links and other tags
        cleaned = re.sub(r'<a\s+[^>]*>(.*?)</a>', r'\1', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'<[^>]+>', '', cleaned)

        # 3. Take the first non-empty line
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if lines:
            first_line = lines[0].replace('\t', ' ')
            # Strip bot prefixes like "File Name : ", "▶️ File Name : ", "•• File Name : "
            prefix_pattern = r'^(?:[▶️\u25b6\ufe0f••\s📂🎬-]*)(?:File\s*Name|Filename|Title|Name)\s*:\s*'
            first_line = re.sub(prefix_pattern, '', first_line, flags=re.IGNORECASE).strip()

            _, cand_ext = os.path.splitext(first_line)
            if is_valid_ext(cand_ext):
                has_explicit_ext = True
                candidate = first_line
            else:
                candidate = first_line

    if candidate:
        cand_stem = os.path.splitext(candidate)[0] if has_explicit_ext else candidate

        if not raw_file_name:
            final_ext = os.path.splitext(candidate)[1] if has_explicit_ext else ext
            return f"{cand_stem}{final_ext}" if (final_ext and not cand_stem.endswith(final_ext)) else cand_stem

        raw_stem, raw_ext = os.path.splitext(raw_file_name)
        if not is_valid_ext(raw_ext):
            raw_ext = ext

        # Detect Telegram truncation (~60 chars limit):
        # e.g., raw_stem is a truncated prefix of cand_stem
        is_truncation = (
            cand_stem.startswith(raw_stem.rstrip('._- '))
            or (len(raw_stem) >= 20 and raw_stem[:25] in cand_stem)
            or (len(raw_stem) >= 45 and cand_stem.startswith(raw_stem[:40]))
        )

        # Generic filenames generated by cameras or Telegram
        generic_prefixes = ('video_', 'file_', 'vid_', 'aud_', 'img_', 'doc_')
        is_generic = (
            raw_stem.lower().startswith(generic_prefixes)
            or raw_file_name.lower() in ('video.mp4', 'file', 'file.mkv', 'video')
        )

        # Caption has explicit extension and is longer than raw_file_name
        is_longer_with_ext = has_explicit_ext and len(candidate) > len(raw_file_name)

        if is_truncation or is_generic or is_longer_with_ext:
            final_ext = os.path.splitext(candidate)[1] if has_explicit_ext else (raw_ext or ext)
            return f"{cand_stem}{final_ext}" if (final_ext and not cand_stem.endswith(final_ext)) else cand_stem

    if raw_file_name:
        return raw_file_name

    unique_id = getattr(media, 'file_unique_id', '')
    return f"{type_name}_{unique_id[:8]}{ext}" if unique_id else f"{type_name}{ext}"

def get_media_file_size(m):
    media = get_media_from_message(m)
    return getattr(media, "file_size", 0)
