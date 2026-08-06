import asyncio
import logging
from info import *
from pyrogram import Client
from lib.util.config_parser import TokenParser
from lib.bot import multi_clients, work_loads, File2Link


async def initialize_clients():
    multi_clients[0] = File2Link
    work_loads[0] = 0
    all_tokens = TokenParser().parse_from_env()
    if not all_tokens:
        print("No additional clients found, using default client")
        return
    
    async def start_client(client_id, token):
        try:
            print(f"Starting - Client {client_id}")
            if client_id == len(all_tokens):
                await asyncio.sleep(2)
                print("This will take some time, please wait...")
            client = await Client(
                name=str(client_id),
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=token,
                sleep_threshold=SLEEP_THRESHOLD,
                no_updates=True,
                in_memory=True
            ).start()
            work_loads[client_id] = 0
            return client_id, client
        except Exception:
            logging.error(f"Failed starting Client - {client_id} Error:", exc_info=True)
            return None

    results = await asyncio.gather(
        *[start_client(i, token) for i, token in all_tokens.items()],
        return_exceptions=True,
    )
    # Drop failed clients (None) and any exception objects that slipped through
    # instead of crashing dict() and killing multi-client / load balancing entirely.
    good_clients = [r for r in results if isinstance(r, tuple)]
    failed = len(results) - len(good_clients)
    if failed:
        logging.warning(f"{failed} client(s) failed to start and were skipped for load balancing")

    multi_clients.update(dict(good_clients))
    if len(multi_clients) != 1:
        print("Multi-Client Mode Enabled")
    else:
        print("No additional clients were initialized, using default client")


async def stop_clients():
    """Gracefully stop every started Pyrogram client (main + multi-clients).

    Needed so SIGTERM shutdown (Heroku/Koyeb/Render) actually closes the
    open MTProto sockets fast instead of hanging past the platform grace
    period and getting SIGKILLed (Heroku R12 Exit timeout).
    """
    for client_id, client in list(multi_clients.items()):
        try:
            await client.stop()
            print(f"Stopped - Client {client_id}")
        except Exception:
            logging.error(f"Failed stopping Client - {client_id} Error:", exc_info=True)
