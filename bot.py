import threading
from web import run_server
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram import Client, filters
from pyrogram.types import *
from motor.motor_asyncio import AsyncIOMotorClient  
from os import environ as env
import asyncio, datetime, time
import aiohttp
from pyrogram.enums import ParseMode
# ⚙️ Configuration Texts
ACCEPTED_TEXT = ""
START_TEXT = """✨ **WELCOME TO AUTO-MESSAGE BOT** ✨

**Hello {}**,\n\n**Welcome to my personal automated message bot! I am here to provide you high quality content effortlessly.**

🚀 **WHAT I CAN DO FOR YOU:**
🌟 **Provide Content:** **Get files, movies, and web series** .
⚡ **High-Speed Links:** **Get direct download and streaming links instantly.**
🔔 **Live Updates:** **We Broadcast New Movies To You.**

━━━━━━━━━━━━━━━━━━━━━━━━
🛠️ **HOW TO USE ME:**
**Just Click On Join To The Links Made By My Owner And I Will Auto Send Content ! **

*Enjoy your stay and happy streaming!* 🍿"""

# 🌍 Loading Koyeb Environment Variables
API_ID = int(env.get('API_ID'))
API_HASH = env.get('API_HASH')
BOT_TOKEN = env.get('BOT_TOKEN')
DB_URL = env.get('DB_URL')
ADMINS = int(env.get('ADMINS'))

# 🗄️ Database and Client Setup
Dbclient = AsyncIOMotorClient(DB_URL)
Cluster = Dbclient['Cluster0']
Data = Cluster['users']
Bot = Client(name='AutoAcceptBot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 🚀 Handlers Section

@Bot.on_message(filters.command("start") & filters.private)                     
async def start_handler(c, m):
    user_id = m.from_user.id
    
    # Save user to Database if not already present
    if not await Data.find_one({'id': user_id}): 
        await Data.insert_one({'id': user_id})
        
    # Inline buttons layout
    button = [[        
        InlineKeyboardButton('Support', url='https://t.me/JACK_xSELLER')
    ]]
    reply_markup = InlineKeyboardMarkup(button)
    
    # 🌍 Fetch a dedicated photo URL for the /start command from Koyeb
    start_photo_url = env.get("START_PHOTO", "")
    
    # Format the start text with the user's mention placeholder
    formatted_start_text = START_TEXT.format(m.from_user.mention)
    
    try:
        # If a valid start image link is present in Koyeb, send it
        if start_photo_url and (start_photo_url.startswith("http://") or start_photo_url.startswith("https://")):
            await c.send_photo(
                chat_id=user_id, 
                photo=start_photo_url, 
                caption=formatted_start_text, 
                reply_markup=reply_markup
            )
        else:
            # Fallback to plain text message if no start image link is set
            await m.reply_text(
                text=formatted_start_text, 
                disable_web_page_preview=True, 
                reply_markup=reply_markup
            )
    except Exception as e:
        print(f"Error in start handler: {e}")
          

async def api_copy(session, to_id, from_chat_id, message_id):
    """Copy a message using the Bot HTTP API (no access_hash / peer cache needed)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/copyMessage"
    payload = {"chat_id": to_id, "from_chat_id": from_chat_id, "message_id": message_id}
    for _ in range(3):  # retry on flood wait
        async with session.post(url, json=payload) as r:
            data = await r.json()
        if data.get("ok"):
            return True, None
        if data.get("error_code") == 429:
            await asyncio.sleep(data.get("parameters", {}).get("retry_after", 5) + 1)
            continue
        return False, f"{data.get('error_code')}: {data.get('description')}"
    return False, "429: flood wait retries exhausted"


def classify_error(err):
    e = (err or "").lower()
    if "blocked" in e:
        return "blocked"
    if "deactivated" in e:
        return "deactivated"
    if "chat not found" in e or "initiate" in e:
        return "not_started"
    return "other"


def build_status(final, total, stats, start_time, errors):
    done = stats["done"]
    pct = int(done * 100 / total) if total else 100
    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)
    elapsed = max(time.time() - start_time, 0.001)
    speed = done / elapsed
    head = "✅ BROADCAST COMPLETED" if final else "📡 BROADCAST IN PROGRESS..."
    lines = [
        head,
        "",
        f"[{bar}] {pct}%",
        f"📊 Progress: {done} / {total}",
        "",
        f"✅ Success: {stats['success']}",
        f"🚫 Blocked bot: {stats['blocked']}",
        f"👻 Deactivated (removed): {stats['deactivated']}",
        f"💤 Never started bot: {stats['not_started']}",
        f"⚠️ Other errors: {stats['other']}",
        "",
    ]
    if final:
        lines.append(f"⏱ Time taken: {datetime.timedelta(seconds=int(elapsed))}")
        lines.append(f"⚡ Speed: {speed:.1f} msgs/sec")
        if errors:
            lines.append("")
            lines.append("Fail reasons:")
            for err, n in sorted(errors.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"• {n} x {err}")
    else:
        remaining = int((total - done) / speed) if speed > 0 else 0
        lines.append(f"⏱ Elapsed: {datetime.timedelta(seconds=int(elapsed))}")
        lines.append(f"⏳ ETA: ~{datetime.timedelta(seconds=remaining)}")
    return "\n".join(lines)


async def safe_edit(msg, text):
    try:
        await msg.edit_text(text, parse_mode=ParseMode.DISABLED)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        pass  # e.g. MessageNotModified - ignore


broadcast_running = False


@Bot.on_message(filters.command(["broadcast", "users"]) & filters.user(ADMINS))
async def broadcast(c, m):
    global broadcast_running

    if m.command[0].lower() == "users":
        total_users = await Data.count_documents({})
        return await m.reply(f"👥 Total Users: {total_users}")

    b_msg = m.reply_to_message
    if not b_msg:
        return await m.reply_text("⚠️ Reply to a message with /broadcast to send it to all users.")

    if broadcast_running:
        return await m.reply_text("⏳ A broadcast is already running. Please wait for it to finish.")

    broadcast_running = True
    try:
        total_users = await Data.count_documents({})
        if total_users == 0:
            return await m.reply_text("⚠️ There are no users in the database.")

        stats = {"done": 0, "success": 0, "blocked": 0, "deactivated": 0, "not_started": 0, "other": 0}
        errors = {}
        start_time = time.time()
        last_edit = 0

        sts = await m.reply_text(
            f"🚀 BROADCAST STARTED\n\n👥 Total users: {total_users}\n⏳ Sending messages...",
            quote=True,
        )

        async with aiohttp.ClientSession() as session:
            async for user in Data.find({}):
                user_id = int(user["id"])
                ok, err = await api_copy(session, user_id, b_msg.chat.id, b_msg.id)
                if ok:
                    stats["success"] += 1
                else:
                    kind = classify_error(err)
                    stats[kind] += 1
                    errors[err] = errors.get(err, 0) + 1
                    print(f"Broadcast failed for {user_id}: {err}")
                    if kind == "deactivated":
                        await Data.delete_many({"id": user_id})
                stats["done"] += 1
                await asyncio.sleep(0.05)  # ~20 msgs/sec, under Telegram limits

                # live update every 3 seconds (avoids Telegram edit flood limits)
                if time.time() - last_edit >= 3:
                    last_edit = time.time()
                    await safe_edit(sts, build_status(False, total_users, stats, start_time, errors))

        # final report: same message is edited (not deleted) so it stays in chat
        await safe_edit(sts, build_status(True, total_users, stats, start_time, errors))
    except Exception as e:
        print(f"Broadcast crashed: {e}")
        await m.reply_text(f"❌ Broadcast stopped due to an error: {e}")
    finally:
        broadcast_running = False


@Bot.on_chat_join_request()
async def req_accept(c, m):
    user = m.from_user
    if not user:
        return

    user_id = user.id
    chat_id = m.chat.id
    chat_title = m.chat.title or "Our Channel"
    
    # 💎 FIX 1: Generate a custom Markdown mention.
    # This prevents formatting collisions when we bold the entire message.
    user_mention = f"[{user.first_name}](tg://user?id={user_id})"
    
    # Save user to Database if not already present
    if not await Data.find_one({'id': user_id}): 
        await Data.insert_one({'id': user_id})
    
    # 🛠️ STEP 1: Keep this line commented out with '#' so requests stay pending!
    await c.approve_chat_join_request(chat_id, user_id) 
    
    # 🌍 Fetch the custom message template from Koyeb env variables
    default_text = env.get('default_text') or "Welcome to {title}, {mention}!"
    raw_message = env.get("WELCOME_MSG", default_text)
    
    # 🔧 FIX: Converts literal '\n' typed into Koyeb into actual clean line breaks
    raw_message = raw_message.replace("\\n", "\n")
    
    # 🌍 Fetch the optional photo URL from Koyeb env variables
    photo_url = env.get("WELCOME_PHOTO", "")
    
    # Formats the {mention} and {title} dynamically based on who joins
    try:
        formatted_message = raw_message.format(mention=user_mention, title=chat_title)
    except Exception as format_err:
        print(f"Formatting error: {format_err}")
        formatted_message = raw_message  # Fallback if placeholders are mistyped

    # 💎 FIX 2: Wrap the entire text in asterisks for bolding.
    bold_message = f"**{formatted_message}**"
    
    try: 
        if photo_url and (photo_url.startswith("http://") or photo_url.startswith("https://")):
            # 💎 FIX 3: Removed 'parse_mode' entirely. Pyrogram uses Markdown by default.
            await c.send_photo(
                chat_id=user_id, 
                photo=photo_url, 
                caption=bold_message
            )
        else:
            # 💎 FIX 3: Removed 'parse_mode' entirely. Pyrogram uses Markdown by default.
            await c.send_message(
                chat_id=user_id, 
                text=bold_message
            )
            
        print(f"Successfully sent formatted welcome to {user_id}")
    except Exception as e: 
        print(f"Failed to send message to {user_id}: {e}")


# 🏁 Execution Core
if __name__ == "__main__":
    # 1. Start the HTTP health check server in a background thread
    print("Starting background health check server...")
    web_thread = threading.Thread(target=run_server, daemon=True)
    web_thread.start()

    # 2. Start the Telegram Bot Client loop cleanly
    print("Starting Telegram Bot...")
    Bot.run()
