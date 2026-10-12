import time
import html
import logging

from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery

from info import is_admin
from database.users_chats_db import db

CONTACT_ADMIN = "@im_goutham_josh"

BAN_NOTICE = (
    "🚫 <b>You have been banned from this bot.</b>\n\n"
    "Reason: you sent <b>NSFW / adult content</b>, which is not allowed here.\n"
    "{reason}"
    "If you think this is a mistake, contact the admin: " + CONTACT_ADMIN
)

# Throttle repeated notices so a banned user spamming can't make the bot spam back.
_NOTICE_COOLDOWN = 60
_last_notice = {}


async def _not_banned_admin_filter(_, __, update):
    user = getattr(update, "from_user", None)
    if not user:
        return False
    if is_admin(user.id, user.username):
        return False
    return await db.is_banned(user.id)

banned_filter = filters.create(_not_banned_admin_filter)


def _notice_text(reason: str = "") -> str:
    r = f"Note: <i>{html.escape(reason)}</i>\n\n" if reason else ""
    return BAN_NOTICE.format(reason=r)


# ── Gate: runs before every other handler (group -1) ─────────────
@Client.on_message(filters.incoming & filters.private & banned_filter, group=-1)
async def block_banned_msg(client: Client, message: Message):
    uid = message.from_user.id
    now = time.time()
    if now - _last_notice.get(uid, 0) > _NOTICE_COOLDOWN:
        _last_notice[uid] = now
        doc = await db.get_ban(uid)
        try:
            await message.reply_text(
                _notice_text((doc or {}).get("reason", "")),
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass
    message.stop_propagation()


@Client.on_callback_query(banned_filter, group=-1)
async def block_banned_cb(client: Client, query: CallbackQuery):
    try:
        await query.answer(
            f"🚫 You are banned (NSFW content). Contact {CONTACT_ADMIN}",
            show_alert=True,
        )
    except Exception:
        pass
    query.stop_propagation()


# ── helpers ──────────────────────────────────────────────────────
async def _resolve_target(client: Client, message: Message):
    """Return (user_id, name, username, reason) or None after replying error.

    Accepts: /ban <id|@username> [reason]   or reply to a user's message.
    """
    args = message.command[1:]
    reason = ""

    if args:
        target = args[0].strip()
        reason = " ".join(args[1:]).strip()
    elif message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name or "", u.username or "", reason
    else:
        await message.reply_text(
            "Usage:\n<code>/ban &lt;user_id | @username&gt; [reason]</code>\n"
            "or reply to a user's message with <code>/ban</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return None

    ref = int(target) if target.lstrip("-").isdigit() else target.lstrip("@")
    try:
        u = await client.get_users(ref)
        return u.id, u.first_name or "", u.username or "", reason
    except Exception:
        if isinstance(ref, int):
            # Numeric id unknown to Telegram cache: still ban by id.
            return ref, "", "", reason
        await message.reply_text(
            f"❌ Can't resolve <code>{html.escape(target)}</code>.\n"
            "Username unknown to the bot — use the numeric user ID.",
            parse_mode=enums.ParseMode.HTML,
        )
        return None


# ── /ban ─────────────────────────────────────────────────────────
@Client.on_message(filters.command("ban") & filters.private)
async def ban_cmd(client: Client, message: Message):
    if not message.from_user or not is_admin(message.from_user.id, message.from_user.username):
        return

    res = await _resolve_target(client, message)
    if not res:
        return
    uid, name, username, reason = res

    if is_admin(uid, username):
        await message.reply_text("❌ Can't ban an admin.")
        return

    already = await db.is_banned(uid)
    try:
        await db.ban_user(uid, name=name, username=username, reason=reason, by=message.from_user.id)
    except Exception as e:
        logging.error(f"ban_user failed: {e}")
        await message.reply_text(f"❌ DB error: <code>{html.escape(str(e))}</code>", parse_mode=enums.ParseMode.HTML)
        return

    # Tell the banned user why.
    notified = True
    try:
        await client.send_message(uid, _notice_text(reason), parse_mode=enums.ParseMode.HTML)
    except Exception:
        notified = False  # user blocked bot / never started it

    who = f"<code>{uid}</code>" + (f" (@{username})" if username else "")
    await message.reply_text(
        f"{'♻️ Already banned, updated' if already else '🚫 Banned'}: {who}\n"
        f"Notice sent: {'✅' if notified else '❌ (user unreachable)'}",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /unban ───────────────────────────────────────────────────────
@Client.on_message(filters.command("unban") & filters.private)
async def unban_cmd(client: Client, message: Message):
    if not message.from_user or not is_admin(message.from_user.id, message.from_user.username):
        return

    res = await _resolve_target(client, message)
    if not res:
        return
    uid, _, username, _ = res

    if not await db.unban_user(uid):
        await message.reply_text(f"ℹ️ <code>{uid}</code> is not banned.", parse_mode=enums.ParseMode.HTML)
        return

    try:
        await client.send_message(uid, "✅ You have been unbanned. Please follow the rules.")
    except Exception:
        pass
    await message.reply_text(f"✅ Unbanned <code>{uid}</code>", parse_mode=enums.ParseMode.HTML)


# ── /banlist ─────────────────────────────────────────────────────
@Client.on_message(filters.command("banlist") & filters.private)
async def banlist_cmd(client: Client, message: Message):
    if not message.from_user or not is_admin(message.from_user.id, message.from_user.username):
        return

    docs = await db.get_banned_users(limit=50)
    total = await db.total_banned_count()
    if not docs:
        await message.reply_text("No banned users.")
        return

    lines = []
    for d in docs:
        uname = f" @{d['username']}" if d.get("username") else ""
        why = f" — {html.escape(d['reason'])}" if d.get("reason") else ""
        lines.append(f"• <code>{d['id']}</code>{uname}{why}")
    await message.reply_text(
        f"🚫 <b>Banned users ({total})</b>\n\n" + "\n".join(lines),
        parse_mode=enums.ParseMode.HTML,
  )
