```python id="q4e3ru"
import sqlite3
import asyncio
import os

from openai import OpenAI

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, BadRequest

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# ================= CHECK =================
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN topilmadi")

if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY topilmadi")

# ================= AI CLIENT =================
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

MODEL = "deepseek-chat"

# ================= CACHE =================
cache = {}

# ================= DATABASE =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS memory (
    user_id INTEGER,
    role TEXT,
    content TEXT
)
""")
conn.commit()

# ================= MEMORY =================
def save_message(user_id, role, content):
    cursor.execute(
        "INSERT INTO memory VALUES (?, ?, ?)",
        (user_id, role, content)
    )
    conn.commit()

def load_memory(user_id, limit=6):
    cursor.execute(
        "SELECT role, content FROM memory WHERE user_id=? ORDER BY rowid DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    return list(reversed(rows))

# ================= CLEAN =================
def clean(text):
    return text.replace("*", "").replace("#", "").strip()

# ================= AI CALL =================
def call_ai(history):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=history
        )

        return clean(response.choices[0].message.content)

    except Exception as e:
        print("AI ERROR:", e)
        return "AI is busy right now, please try again later."

# ================= STREAM EFFECT =================
async def stream_message(update, text):
    msg = await update.message.reply_text("...")

    chunk_size = max(30, len(text) // 8)
    last_text = ""

    for i in range(0, len(text), chunk_size):
        chunk = text[:i + chunk_size]

        if chunk != last_text:
            try:
                await msg.edit_text(chunk)
                last_text = chunk
            except (TimedOut, BadRequest):
                pass

        await asyncio.sleep(0.04)

    if text != last_text:
        try:
            await msg.edit_text(text)
        except:
            pass

# ================= ASK AI =================
async def ask_ai(user_id, text):
    key = text.lower().strip()

    if key in cache:
        return cache[key]

    loop = asyncio.get_event_loop()

    save_message(user_id, "user", text)

    history_db = load_memory(user_id)

    messages = [
        {
            "role": "system",
            "content": "You are a helpful, smart, concise AI assistant."
        }
    ]

    for role, content in history_db:
        messages.append({
            "role": role,
            "content": content
        })

    messages.append({
        "role": "user",
        "content": text
    })

    def _call():
        return call_ai(messages)

    reply = await loop.run_in_executor(None, _call)

    cache[key] = reply

    save_message(user_id, "assistant", reply)

    return reply

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "I am PS AI Assistant. How can I help you?"
    )

# ================= MESSAGE HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    await update.message.chat.send_action("typing")

    reply = await ask_ai(user_id, text)

    await stream_message(update, reply)

# ================= MAIN =================
def main():
    app = Application.builder() \
        .token(TELEGRAM_TOKEN) \
        .read_timeout(60) \
        .connect_timeout(60) \
        .build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("Bot RUNNING 🚀")

    app.run_polling()

if __name__ == "__main__":
    main()
```
