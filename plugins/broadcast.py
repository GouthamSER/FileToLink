import logging
import datetime
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from database.users_chats_db import db
from info import ADMINS


@Client.on_message(filters.command(["broadcast", "bc"]) & filters.user(ADMINS))
async def pm_broadcast(bot, message):
    b_msg = await bot.ask(
        chat_id=message.from_user.id,
        text="Now Send Me Your Broadcast Message"
    )
    try:
        users = await db.get_all_users()
        sts = await message.reply_text("Broadcasting your messages...")
        start_time = time.time()
        total_users = await db.total_users_count()
        done = 0
        blocked = 0
        deleted = 0
        failed = 0
        success = 0

        async for user in users:
            if "id" in user:
                pti, sh = await broadcast_messages(int(user["id"]), b_msg)
                if pti:
                    success += 1
                elif pti == False:
                    if sh == "Blocked":
                        blocked += 1
                    elif sh == "Deleted":
                        deleted += 1
                    elif sh == "Error":
                        failed += 1
            else:
                # Handle the case where 'id' key is missing in the user dictionary
                failed += 1

            done += 1
            if not done % 20:
                await sts.edit(
                    f"Broadcast in progress:\n\n"
                    f"Total Users: {total_users}\n"
                    f"Completed: {done} / {total_users}\n"
                    f"Success: {success}\n"
                    f"Blocked: {blocked}\n"
                    f"Deleted: {deleted}\n"
                    f"Failed: {failed}"
                )

        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        await sts.edit(
            f"Broadcast Completed:\n"
            f"Completed in {time_taken}.\n\n"
            f"Total Users: {total_users}\n"
            f"Completed: {done} / {total_users}\n"
            f"Success: {success}\n"
            f"Blocked: {blocked}\n"
            f"Deleted: {deleted}\n"
            f"Failed: {failed}"
        )
    except Exception as e:
        logging.error(f"Broadcast error: {e}")
        await message.reply_text(f"Broadcast failed with error:\n`{e}`")


async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - Removed from Database (deleted account).")
        return False, "Deleted"
    except UserIsBlocked:
        logging.info(f"{user_id} - Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - PeerIdInvalid.")
        return False, "Error"
    except Exception as e:
        logging.error(f"{user_id} - Unexpected error: {e}")
        return False, "Error"
