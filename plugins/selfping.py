import asyncio
import aiohttp
from info import URL

# Settings (not objects)
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)
RETRY_DELAY = 300
MAX_DELAY = 3600

async def self_ping_task():
    """Keep-alive ping with connection pooling."""
    retry_delay = RETRY_DELAY
    
    # Create connector inside async function where loop exists
    connector = aiohttp.TCPConnector(
        limit=5,
        ttl_dns_cache=300,
        use_dns_cache=True,
    )
    
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=TIMEOUT,
        raise_for_status=False
    ) as session:
        while True:
            start = asyncio.get_event_loop().time()
            
            try:
                async with session.get(URL, ssl=False) as resp:
                    if resp.status == 200:
                        print(f"✓ Ping OK")
                        retry_delay = RETRY_DELAY
                    else:
                        print(f"⚠ Ping status: {resp.status}")
                        
            except asyncio.TimeoutError:
                print(f"✗ Timeout")
            except aiohttp.ClientError as e:
                print(f"✗ Client error: {type(e).__name__}")
            except Exception as e:
                print(f"✗ Error: {e}")
                retry_delay = min(retry_delay * 1.5, MAX_DELAY)
            
            elapsed = asyncio.get_event_loop().time() - start
            await asyncio.sleep(max(0, retry_delay - elapsed))
