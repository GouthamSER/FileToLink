import logging 
import datetime, time, asyncio
from pyrogram import Client, filters
from pyrogram.errors import *
from database.users_chats_db import db
from info import ADMINS

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def pm_broadcast(bot, message):
    if not message.reply_to_message:
        return await message.reply_text(
            "Reply to a message with /broadcast to send it to all users."
        )
    b_msg = message.reply_to_message
    try:
        users = await db.get_all_users()
        if not users:
            return await message.reply_text("❌ No users found in database, or database is not connected.")
        sts = await message.reply_text('Broadcasting your messages...')
        start_time = time.time()
        total_users = await db.total_users_count()
        done = 0
        blocked = 0
        deleted = 0
        failed = 0
        success = 0
        async for user in users:
            if 'id' in user:
                pti, sh = await broadcast_messages(int(user['id']), b_msg)
                if pti:
                    success += 1
                elif pti == False:
                    if sh == "Blocked":
                        blocked += 1
                    elif sh == "Deleted":
                        deleted += 1
                    elif sh == "Error":
                        failed += 1
                done += 1
                if not done % 20:
                    await sts.edit(f"Broadcast in progress:\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}")    
            else:
                # Handle the case where 'id' key is missing in the user dictionary 
                done += 1
                failed += 1
                if not done % 20:
                    await sts.edit(f"Broadcast in progress:\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}")    
    
        time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
        await sts.edit(f"Broadcast Completed:\nCompleted in {time_taken} seconds.\n\nTotal Users: {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}")
    except Exception as e:
        print(f"error: {e}")

# Don't Remove Credit Tg - @GouthamSER
# Ask Doubt on telegram @m_goutham_josh

async def broadcast_messages(user_id, message):
    for _ in range(3):
        try:
            await message.copy(chat_id=user_id)
            return True, "Success"
        except FloodWait as e:
            wait_time = int(getattr(e, "value", getattr(e, "x", 1))) + 1
            await asyncio.sleep(wait_time)
        except InputUserDeactivated:
            await db.delete_user(int(user_id))
            logging.info(f"{user_id} - Removed from Database, since deleted account.")
            return False, "Deleted"
        except UserIsBlocked:
            logging.info(f"{user_id} - Blocked the bot.")
            return False, "Blocked"
        except PeerIdInvalid:
            await db.delete_user(int(user_id))
            logging.info(f"{user_id} - PeerIdInvalid")
            return False, "Error"
        except Exception as e:
            logging.error(f"Error broadcasting to {user_id}: {e}")
            return False, "Error"
    return False, "Error"
