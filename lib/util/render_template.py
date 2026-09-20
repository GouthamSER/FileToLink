import os
import mimetypes
import jinja2
import functools
from info import *
from lib.bot import File2Link
from lib.util.human_readable import humanbytes
from lib.util.file_properties import get_file_ids
from lib.server.exceptions import InvalidHash
import urllib.parse
import logging


# Compile each template ONCE and cache it
@functools.lru_cache(maxsize=4)
def _get_template(template_file: str) -> jinja2.Template:
    with open(template_file, "r", encoding="utf-8") as f:
        return jinja2.Template(f.read())


async def render_page(id, secure_hash, page="watch"):
    file = await File2Link.get_messages(int(LOG_CHANNEL), int(id))
    file_data = await get_file_ids(File2Link, int(LOG_CHANNEL), int(id))
    if file_data.unique_id[:6] != secure_hash:
        logging.debug(f"link hash: {secure_hash} - {file_data.unique_id[:6]}")
        logging.debug(f"Invalid hash for message with - ID {id}")
        raise InvalidHash

    raw_name = file_data.file_name or f"file_{secure_hash}"
    file_ext = os.path.splitext(raw_name)[1].lower().lstrip(".")
    mime_type = file_data.mime_type or ""
    if not mime_type:
        mime_type = mimetypes.guess_type(raw_name)[0] or "application/octet-stream"

    tag = mime_type.split("/")[0].strip().lower()
    video_exts = {"mp4", "mkv", "webm", "avi", "mov", "flv", "m4v", "3gp", "ts", "m2ts", "wmv", "ogv"}
    audio_exts = {"mp3", "aac", "wav", "flac", "ogg", "m4a", "opus", "wma"}

    is_video = tag == "video" or file_ext in video_exts
    is_audio = tag == "audio" or file_ext in audio_exts
    media_type = "video" if is_video else ("audio" if is_audio else "file")

    src = urllib.parse.urljoin(
        URL,
        f"{id}/{urllib.parse.quote(raw_name, safe='')}?hash={secure_hash}",
    )
    watch_src = urllib.parse.urljoin(
        URL,
        f"watch/{id}/{urllib.parse.quote(raw_name, safe='')}?hash={secure_hash}",
    )

    if page == "dl":
        template_file = "lib/template/dl.html"
    elif page == "watch":
        template_file = "lib/template/req.html" if (is_video or is_audio) else "lib/template/dl.html"
    else:
        template_file = "lib/template/req.html" if (is_video or is_audio) else "lib/template/dl.html"

    file_size = humanbytes(file_data.file_size)
    template = _get_template(template_file)
    file_name = raw_name.replace("_", " ")

    return template.render(
        file_name=file_name,
        file_name_raw=raw_name,
        file_url=src,
        watch_url=watch_src,
        dl_url=src,
        file_size=file_size,
        file_unique_id=file_data.unique_id,
        file_ext=file_ext.upper() if file_ext else "FILE",
        mime_type=mime_type,
        media_type=media_type,
        is_video=is_video,
        is_audio=is_audio,
    )
