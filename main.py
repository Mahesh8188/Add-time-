import os
import asyncio
import re
from datetime import datetime, timedelta
from pyrogram import Client, filters, idle
from pyrogram.errors import UserAdminInvalid
from motor.motor_asyncio import AsyncIOMotorClient

# --------------------
# Environment Variables
# --------------------
API_ID = int(os.getenv("API_ID", "26741021"))
API_HASH = os.getenv("API_HASH", "7c5af0b88c33d2f5cce8df5d82eb2a94")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "6859451629"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://akimax8182:akimax8182@cluster0.drfp9pq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# --------------------
# Bot & DB Setup
# --------------------
app = Client("timed-group-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["timed_group_bot"]
members_col = db["members"]

# --------------------
# Time Parser
# --------------------
def parse_time(time_str):
    if time_str == "lifetime":
        return None
    match = re.match(r"(\d+)([mhdwy])", time_str)
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    if unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    elif unit == "y":
        return timedelta(days=value * 365)
    return None

# --------------------
# Commands
# --------------------
@app.on_message(filters.command("add") & filters.user(OWNER_ID))
async def add_user(_, message):
    if len(message.command) < 3:
        return await message.reply("Usage: `/add user_id time` (e.g. `/add 123456789 10m`)", quote=True)

    try:
        user_id = int(message.command[1])
    except:
        return await message.reply("❌ Invalid user_id", quote=True)

    time_str = message.command[2]
    delta = parse_time(time_str)
    if delta is None and time_str != "lifetime":
        return await message.reply("❌ Invalid time format. Use m/h/d/w/y or lifetime.", quote=True)

    expire_at = None if delta is None else datetime.utcnow() + delta
    chat_id = message.chat.id

    try:
        await app.add_chat_members(chat_id, [user_id])
    except Exception as e:
        return await message.reply(f"❌ Error: {e}", quote=True)

    await members_col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"expire_at": expire_at}},
        upsert=True,
    )

    await message.reply(
        f"✅ User `{user_id}` added to **{message.chat.title}**\n⏰ Expires: {expire_at if expire_at else 'Lifetime'}",
        quote=True,
    )

@app.on_message(filters.command("members") & filters.group)
async def members_list(_, message):
    chat_id = message.chat.id
    cursor = members_col.find({"chat_id": chat_id})
    users = await cursor.to_list(length=1000)

    if not users:
        return await message.reply("No active members stored for this group.", quote=True)

    text = "**📋 Active Members in this Group:**\n\n"
    for user in users:
        exp = user["expire_at"].strftime("%Y-%m-%d %H:%M:%S") if user["expire_at"] else "Lifetime"
        text += f"👤 `{user['user_id']}` → ⏰ {exp}\n"

    await message.reply(text, quote=True)

# --------------------
# Background Task
# --------------------
async def check_expired():
    while True:
        now = datetime.utcnow()
        cursor = members_col.find({"expire_at": {"$lte": now}})
        async for member in cursor:
            try:
                await app.ban_chat_member(member["chat_id"], member["user_id"])
                await app.unban_chat_member(member["chat_id"], member["user_id"])
            except UserAdminInvalid:
                pass
            except Exception as e:
                print(f"Error removing {member['user_id']} from {member['chat_id']}: {e}")
            await members_col.delete_one({"_id": member["_id"]})
        await asyncio.sleep(30)

# --------------------
# Start Bot
# --------------------
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply("🤖 Timed Group Bot is alive!\nUse /add & /members")

async def main():
    asyncio.create_task(check_expired())
    await app.start()
    print("✅ Timed Group Bot is running...")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())

from flask import Flask
import threading

app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "🤖 Bot is alive!"

def run_flask():
    app_web.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

if __name__ == "__main__":
    # Flask ko background thread me start karo
    threading.Thread(target=run_flask).start()
    # Bot ko async loop me start karo
    asyncio.run(main())
                                                   
