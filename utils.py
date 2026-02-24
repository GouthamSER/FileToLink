from shortzy import Shortzy
from info import SHORTLINK_URL, SHORTLINK_API

class temp(object):
    ME = None
    BOT = None
    U_NAME = None
    B_NAME = None


async def get_shortlink(link):
    shortzy = Shortzy(api_key=SHORTLINK_API, base_site=SHORTLINK_URL)
    link = await shortzy.convert(link)
    return link

async def check_force_sub(client, user_id):
    not_joined = []
    for channel in FORCE_SUB_CHANNELS:
        try:
            await client.get_chat_member(channel, user_id)
        except UserNotParticipant:
            not_joined.append(channel)
        except:
            pass
    return not_joined
