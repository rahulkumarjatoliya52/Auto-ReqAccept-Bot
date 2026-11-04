import threading
from web import run_server
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram import Client, filters
from pyrogram.types import *
from motor.motor_asyncio import AsyncIOMotorClient  
from os import environ as env
import asyncio, datetime, time
from pyrogram.enums import ParseMode
# ⚙️ Configuration Texts
ACCEPTED_TEXT = "
🔥 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗖𝗢𝗡𝗧𝗘𝗡𝗧 🎀
≪━─━─━─━─◈─━─━─━─━≫ 
❤️‍🔥𝐕!𝐫𝐚𝐥 𝐌𝐦s 🫦👇👇
https://t.me/+sIcUWOvj3edjZWFl
https://t.me/+sIcUWOvj3edjZWFl

🫦Viral Video 🍑👇
https://t.me/+GuWn8UZ9S3wxNTE1
https://t.me/+GuWn8UZ9S3wxNTE1

❤️‍🔥Desi Girls 🫦👇👇
https://t.me/+Tr0PnqAuXq8xNjVl
https://t.me/+Tr0PnqAuXq8xNjVl
"

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
          

@Bot.on_message(filters.command(["broadcast", "users"]) & filters.user(ADMINS))  
async def broadcast(c, m):
    if m.text == "/users":
        total_users = await Data.count_documents({})
        return await m.reply(f"Total Users: {total_users}")
    
    b_msg = m.reply_to_message
    if not b_msg:
        return await m.reply_text("Please reply to a message to broadcast it.")
        
    sts = await m.reply_text("Broadcasting your messages...")
    users = Data.find({})
    total_users = await Data.count_documents({})
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    
    async for user in users:
        user_id = int(user['id'])
        try:
            await b_msg.copy(chat_id=user_id)
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await b_msg.copy(chat_id=user_id)
            success += 1
        except InputUserDeactivated:
            await Data.delete_many({'id': user_id})
            failed += 1
        except UserIsBlocked:
            failed += 1
        except PeerIdInvalid:
            await Data.delete_many({'id': user_id})
            failed += 1
        except Exception as e:
            failed += 1
        done += 1
        if not done % 20:
            await sts.edit(f"Broadcast in progress:\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")    
            
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.delete()
    await m.reply_text(f"Broadcast Completed:\nCompleted in {time_taken} seconds.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}", quote=True)


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
    # await c.approve_chat_join_request(chat_id, user_id) 
    
    # 🌍 Fetch the custom message template from Koyeb env variables
    default_text = "Hello {mention}\nWelcome To {title}\n\nYou are Auto Approved!"
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
