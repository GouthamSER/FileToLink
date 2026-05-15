import logging
import datetime
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from database.users_chats_db import db
from info import ADMINS

# Rate limiting constants (adjust based on your account type)
# Telegram allows ~30 messages per second, but we use conservative rates
BROADCAST_DELAY = 0.08  # 80ms between each message (12.5 msgs/sec) - INCREASED from 0.1
FLOOD_SLEEP_THRESHOLD = 5  # Sleep when rate limit approaching
BATCH_SIZE = 30  # Process users in batches for better performance

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
        sts = await message.reply_text("📢 Starting broadcast...\nFetching user count...")
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
            
            # Update progress every 20 users (or less frequently for large broadcasts)
            if done % max(20, total_users // 50) == 0:
                try:
                    await sts.edit(
                        f"📢 <b>Broadcast in progress:</b>\n\n"
                        f"📊 <b>Total Users:</b> {total_users}\n"
                        f"✅ <b>Completed:</b> {done} / {total_users} ({(done/total_users*100):.1f}%)\n"
                        f"✅ <b>Success:</b> {success}\n"
                        f"🚫 <b>Blocked:</b> {blocked}\n"
                        f"👤 <b>Deleted:</b> {deleted}\n"
                        f"❌ <b>Failed:</b> {failed}"
                    )
                except Exception as e:
                    logging.warning(f"Failed to update progress message: {e}")
            
            # Rate limiting - delay between messages
            await asyncio.sleep(BROADCAST_DELAY)
        
        # Final report
        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        final_text = (
            f"✅ <b>Broadcast Completed Successfully!</b>\n"
            f"⏱️ <b>Time Taken:</b> {time_taken}\n\n"
            f"📊 <b>Final Statistics:</b>\n"
            f"👥 <b>Total Users:</b> {total_users}\n"
            f"✅ <b>Success:</b> {success} ({(success/total_users*100):.1f}%)\n"
            f"🚫 <b>Blocked:</b> {blocked} ({(blocked/total_users*100):.1f}%)\n"
            f"👤 <b>Deleted:</b> {deleted} ({(deleted/total_users*100):.1f}%)\n"
            f"❌ <b>Failed:</b> {failed} ({(failed/total_users*100):.1f}%)"
        )
        
        try:
            await sts.edit(final_text)
        except Exception as e:
            logging.error(f"Failed to send final report: {e}")
            await message.reply_text(final_text)
        
    except Exception as e:
        logging.error(f"Broadcast error: {e}", exc_info=True)
        await message.reply_text(f"❌ <b>Broadcast failed:</b>\n<code>{str(e)}</code>")


async def broadcast_messages(bot, user_id, message):
    """
    Send a message to a user with proper error handling
    Returns: (success: bool, reason: str)
    
    Args:
        bot: Pyrogram Client instance
        user_id: Target user ID
        message: Message object to copy/forward
    """
    try:
        # Forward/copy the message to the user (handles all media types correctly)
        await message.forward(chat_id=user_id)
        return True, "Success"
        
    except FloodWait as e:
        # Handle rate limiting - wait and retry
        wait_time = e.value
        logging.warning(f"FloodWait for user {user_id}: {wait_time}s - Sleeping...")
        await asyncio.sleep(wait_time + 1)  # Add 1s buffer
        # Retry the message
        try:
            return await broadcast_messages(bot, user_id, message)
        except Exception as retry_e:
            logging.error(f"Retry failed for user {user_id}: {retry_e}")
            return False, "Error"
        
    except InputUserDeactivated:
        # User deleted their account
        try:
            await db.delete_user(user_id)
            logging.info(f"User {user_id} deleted their account - removed from DB")
        except Exception as db_e:
            logging.warning(f"Failed to delete user {user_id} from DB: {db_e}")
        return False, "Deleted"
        
    except UserIsBlocked:
        # User blocked the bot
        logging.info(f"User {user_id} blocked the bot")
        return False, "Blocked"
        
    except PeerIdInvalid:
        # Invalid peer ID - user doesn't exist
        try:
            await db.delete_user(user_id)
            logging.warning(f"User {user_id} has invalid peer ID - removed from DB")
        except Exception as db_e:
            logging.warning(f"Failed to delete user {user_id} from DB: {db_e}")
        return False, "Error"
        
    except Exception as e:
        # Any other error
        logging.error(f"User {user_id} - Error: {type(e).__name__}: {e}")
        return False, "Error"
