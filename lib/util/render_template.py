import jinja2
import functools
from info import *
from lib.bot import File2Link
from lib.util.human_readable import humanbytes
from lib.util.file_properties import get_file_ids
from lib.server.exceptions import InvalidHash
import urllib.parse
import logging


# Compile each template ONCE and cache it — previously every single page
# view re-read the HTML file off disk AND recompiled the Jinja AST from
# scratch, discarded immediately after rendering. Under real traffic
# (every /watch/ and /dl/ hit) that's pure repeated CPU+memory churn for
# zero benefit since these files never change while the process is
# running. lru_cache keeps at most 2 compiled templates (req.html,
# dl.html) alive for the process lifetime — a few KB total, negligible,
# and strictly less work than the old recompile-every-request behavior.
@functools.lru_cache(maxsize=2)
def _get_template(template_file: str) -> jinja2.Template:
    with open(template_file) as f:
        return jinja2.Template(f.read())


async def render_page(id, secure_hash, page="watch"):
    file = await File2Link.get_messages(int(LOG_CHANNEL), int(id))
    file_data = await get_file_ids(File2Link, int(LOG_CHANNEL), int(id))
    if file_data.unique_id[:6] != secure_hash:
        logging.debug(f"link hash: {secure_hash} - {file_data.unique_id[:6]}")
        logging.debug(f"Invalid hash for message with - ID {id}")
        raise InvalidHash

    raw_name = file_data.file_name or f"file_{secure_hash}"

    # quote_plus encodes spaces as '+' — that's query-string syntax, not
    # valid for a URL *path* segment. Some Android download managers (and
    # anything doing a naive percent-decode without query-unquote) read
    # that '+' back literally instead of a space, corrupting the saved
    # filename. quote() with '%20' is the spec-correct choice for a path.
    src = urllib.parse.urljoin(
        URL,
        f"{id}/{urllib.parse.quote(raw_name, safe='')}?hash={secure_hash}",
    )

    # page="watch" -> always the player page, page="dl" -> always the
    # download page, regardless of mime type. This is what the Telegram
    # buttons/captions ask for explicitly (Watch vs Download intent), so
    # don't let mime-sniffing override the caller's choice.
    tag = (file_data.mime_type or "").split("/")[0].strip()
    if page == "dl":
        template_file = "lib/template/dl.html"
    elif page == "watch":
        template_file = "lib/template/req.html" if tag in ["video", "audio"] else "lib/template/dl.html"
    else:
        template_file = "lib/template/req.html" if tag in ["video", "audio"] else "lib/template/dl.html"

    file_size = humanbytes(file_data.file_size)

    template = _get_template(template_file)

    file_name = raw_name.replace("_", " ")

    return template.render(
        file_name=file_name,
        file_name_raw=raw_name,
        file_url=src,
        file_size=file_size,
        file_unique_id=file_data.unique_id,
    )
