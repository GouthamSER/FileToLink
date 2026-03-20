import aiohttp
from urllib.parse import quote
from info import SHORTLINK, SHORTLINK_URL, SHORTLINK_API, ISGD

class temp(object):
    ME = None
    BOT = None
    U_NAME = None
    B_NAME = None


async def get_shortlink(link):
    # is.gd shortlink (no API key needed)
    if ISGD:
        try:
            url = f"https://is.gd/create.php?format=simple&url={quote(link)}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    result = await resp.text()
                    if result.startswith("http"):
                        return result.strip()
        except Exception:
            pass  # fallback to original link if is.gd fails
        return link

    # Shortzy-based shortlink (gplinks, mdisk, etc.)
    if SHORTLINK:
        from shortzy import Shortzy
        shortzy = Shortzy(api_key=SHORTLINK_API, base_site=SHORTLINK_URL)
        link = await shortzy.convert(link)
    return link
