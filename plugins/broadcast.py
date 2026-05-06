import logging
import datetime
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from database.users_chats_db import db
from info import ADMINS

# Rate limiting constants (adjust based on your account type)
BROADCAST_DELAY = 0.1  # 100ms between each message (10 msgs/sec)
FLOOD_SLEEP_THRESHOLD = 5  # Sleep when rate limit approaching

@Client.on_message(filters.command(["broadcast", "bc"]) & filters.user(ADMINS))
async def pm_broadcast(bot, message):
    """Broadcast a message to all users with proper rate limiting"""
    
    # Get the message to broadcast
    b_msg = await bot.ask(
        chat_id=message.from_user.id,
        text="Now Send Me Your Broadcast Message"
    )
    
    try:
        users = await db.get_all_users()
        sts = await message.reply_text("Broadcasting your messages...")
        start_time = time.time()
        total_users = await db.total_users_count()
        
        # Initialize counters
        done = 0
        blocked = 0
        deleted = 0
        failed = 0
        success = 0
        
        async for user in users:
            if "id" not in user:
                failed += 1
                done += 1
                continue
            
            try:
                user_id = int(user["id"])
                is_success, reason = await broadcast_messages(bot, user_id, b_msg)
                
                if is_success:
                    success += 1
                elif reason == "Blocked":
                    blocked += 1
                elif reason == "Deleted":
                    deleted += 1
                else:  # Error or other failure
                    failed += 1
                    
            except Exception as e:
                logging.error(f"Error processing user {user.get('id')}: {e}")
                failed += 1
            
            done += 1
            
            # Update progress every 20 users
            if done % 20 == 0:
                await sts.edit(
                    f"📢 Broadcast in progress:\n\n"
                    f"Total Users: {total_users}\n"
                    f"Completed: {done} / {total_users}\n"
                    f"✅ Success: {success}\n"
                    f"🚫 Blocked: {blocked}\n"
                    f"👤 Deleted: {deleted}\n"
                    f"❌ Failed: {failed}"
                )
            
            # Rate limiting - delay between messages
            await asyncio.sleep(BROADCAST_DELAY)
        
        # Final report
        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        await sts.edit(
            f"✅ Broadcast Completed!\n"
            f"⏱️ Time: {time_taken}\n\n"
            f"Total Users: {total_users}\n"
            f"✅ Success: {success}\n"
            f"🚫 Blocked: {blocked}\n"
            f"👤 Deleted: {deleted}\n"
            f"❌ Failed: {failed}"
        )
        
    except Exception as e:
        logging.error(f"Broadcast error: {e}", exc_info=True)
        await message.reply_text(f"❌ Broadcast failed:\n`{e}`")


async def broadcast_messages(bot, user_id, message):
    """
    Send a message to a user with proper error handling
    Returns: (success: bool, reason: str)
    """
    try:
        # Copy the message to the user
        await message.copy(chat_id=user_id)
        return True, "Success"
        
    except FloodWait as e:
        # Handle rate limiting - wait and retry
        logging.warning(f"FloodWait: {e.value}s - Sleeping...")
        await asyncio.sleep(e.value + 1)  # Add 1s buffer
        # Retry the message
        return await broadcast_messages(bot, user_id, message)
        
    except InputUserDeactivated:
        # User deleted their account
        await db.delete_user(user_id)
        logging.info(f"User {user_id} deleted their account - removed from DB")
        return False, "Deleted"
        
    except UserIsBlocked:
        # User blocked the bot
        logging.info(f"User {user_id} blocked the bot")
        return False, "Blocked"
        
    except PeerIdInvalid:
        # Invalid peer ID - user doesn't exist
        await db.delete_user(user_id)
        logging.warning(f"User {user_id} has invalid peer ID - removed from DB")
        return False, "Error"
        
    except Exception as e:
        # Any other error
        logging.error(f"User {user_id} - Error: {type(e).__name__}: {e}")
        return False, "Error"
