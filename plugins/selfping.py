import asyncio, aiohttp
from info import URL

async def self_ping_task():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL) as resp:
                    if resp.status == 200:
                        print("Self-ping successful.")
        except Exception as e:
            print(f"Self-ping failed: {e}")
        await asyncio.sleep(1200)
