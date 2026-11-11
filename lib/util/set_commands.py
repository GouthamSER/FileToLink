import logging
from pyrogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from info import ADMINS

# Menu shown to every user.
USER_COMMANDS = [
    BotCommand("start", "Start the bot and get a welcome message"),
    BotCommand("how", "How to use the bot"),
    BotCommand("help", "Show help and usage instructions"),
    BotCommand("about", "Get information about the bot"),
    BotCommand("ping", "Check the bot's status and response time"),
]

# Extra menu shown only in an admin's private chat (user commands + these).
ADMIN_COMMANDS = [
    BotCommand("stats", "(Admin) View usage statistics and resource consumption"),
    BotCommand("users", "(Admin) Show the total number of users"),
    BotCommand("broadcast", "(Admin) Send a message to all users"),
    BotCommand("ban", "(Admin) Ban a user"),
    BotCommand("unban", "(Admin) Unban a user"),
    BotCommand("banlist", "(Admin) List banned users"),
    BotCommand("log", "(Admin) Send bot logs"),
    BotCommand("restart", "(Admin) Update and restart the bot"),
]


async def set_bot_commands(client):
    """Register the command menu on every startup."""
    try:
        await client.set_bot_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
        logging.info("Default bot commands set (%d)", len(USER_COMMANDS))
    except Exception:
        logging.error("Failed to set default bot commands", exc_info=True)
        return

    for admin in ADMINS:
        if not isinstance(admin, int):
            continue  # usernames can't be used as a chat scope
        try:
            await client.set_bot_commands(
                USER_COMMANDS + ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin),
            )
        except Exception as e:
            # Admin must have started the bot at least once.
            logging.warning("Admin command menu not set for %s: %s", admin, e)
