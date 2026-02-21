import asyncio
import aiohttp
from info import URL

# Connection pool settings for reuse
connector = aiohttp.TCPConnector(
    limit=10,
    limit_per_host=5,
    ttl_dns_cache=300,
    use_dns_cache=True,
)

timeout = aiohttp.ClientTimeout(total=30, connect=10)

async def self_ping_task():
    """Keep-alive ping with connection pooling and exponential backoff."""
    retry_delay = 300  # Base delay 5 minutes
    max_delay = 3600   # Max delay 1 hour
    
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        raise_for_status=False
    ) as session:
        while True:
            start_time = asyncio.get_event_loop().time()
            
            try:
                async with session.get(URL, ssl=False) as resp:
                    if resp.status == 200:
                        print(f"✓ Self-ping OK | Status: {resp.status}")
                        retry_delay = 300  # Reset on success
                    else:
                        print(f"⚠ Self-ping returned: {resp.status}")
                        
            except asyncio.TimeoutError:
                print(f"✗ Self-ping timeout")
            except aiohttp.ClientError as e:
                print(f"✗ Self-ping client error: {type(e).__name__}")
            except Exception as e:
                print(f"✗ Self-ping failed: {e}")
                # Exponential backoff on unknown errors
                retry_delay = min(retry_delay * 1.5, max_delay)
            
            # Calculate sleep time accounting for request duration
            elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0, retry_delay - elapsed)
            
            await asyncio.sleep(sleep_time)
