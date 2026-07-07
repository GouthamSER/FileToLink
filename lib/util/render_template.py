import jinja2
from info import *
from lib.bot import File2Link
from lib.util.human_readable import humanbytes
from lib.util.file_properties import get_file_ids
from lib.server.exceptions import InvalidHash
import urllib.parse
import logging


async def render_page(id, secure_hash, src=None):
    file = await File2Link.get_messages(int(LOG_CHANNEL), int(id))
    file_data = await get_file_ids(File2Link, int(LOG_CHANNEL), int(id))
    if file_data.unique_id[:6] != secure_hash:
        logging.debug(f"link hash: {secure_hash} - {file_data.unique_id[:6]}")
        logging.debug(f"Invalid hash for message with - ID {id}")
        raise InvalidHash

    raw_name = file_data.file_name or f"file_{secure_hash}"

    src = urllib.parse.urljoin(
        URL,
        f"{id}/{urllib.parse.quote_plus(raw_name)}?hash={secure_hash}",
    )

    tag = (file_data.mime_type or "").split("/")[0].strip()
    file_size = humanbytes(file_data.file_size)
    template_file = "lib/template/req.html" if tag in ["video", "audio"] else "lib/template/dl.html"

    with open(template_file) as f:
        template = jinja2.Template(f.read())

    file_name = raw_name.replace("_", " ")

    return template.render(
        file_name=file_name,
        file_url=src,
        file_size=file_size,
        file_unique_id=file_data.unique_id,
    )
