import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaDocument
import os
import hashlib
import sqlite3

# === Configuration ===
import os

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
POWERED_BY = "Powered by @nkp10101"

bot = telebot.TeleBot(TOKEN)

# === Database Setup ===
if not os.path.exists("users.db"):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    conn.commit()
    conn.close()

# === User Session Store ===
sessions = {}

# === Helper Functions ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_logged_in(user_id):
    return user_id in sessions

def user_folder(user_id):
    folder = f"user_data/{user_id}"
    os.makedirs(folder, exist_ok=True)
    return folder

# === Start Command ===
@bot.message_handler(commands=['start'])
def start(msg):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔐 Login", callback_data="login"))
    keyboard.add(InlineKeyboardButton("🆕 Sign Up", callback_data="signup"))
    keyboard.add(InlineKeyboardButton("📁 Storage", callback_data="storage"))
    bot.send_message(msg.chat.id, "Welcome to your private storage bot.
Choose an option:", reply_markup=keyboard)

# === Callback Handler ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    if call.data == "login":
        bot.send_message(call.message.chat.id, "Send your login like this:
`login username password`", parse_mode="Markdown")
    elif call.data == "signup":
        bot.send_message(call.message.chat.id, "Send your signup like this:
`signup username password`", parse_mode="Markdown")
    elif call.data == "storage":
        if not is_logged_in(user_id):
            bot.send_message(call.message.chat.id, "🔐 Please login first.")
            return
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📁 Create Folder", callback_data="create_folder"))
        keyboard.add(InlineKeyboardButton("🗑️ Delete Folder", callback_data="delete_folder"))
        keyboard.add(InlineKeyboardButton("📂 My Folders", callback_data="my_folders"))
        if user_id == ADMIN_ID:
            keyboard.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin"))
        bot.send_message(call.message.chat.id, "📦 Storage Options:", reply_markup=keyboard)

    elif call.data == "create_folder":
        bot.send_message(call.message.chat.id, "Send folder name to create:
`folder folder_name`", parse_mode="Markdown")
    elif call.data == "delete_folder":
        bot.send_message(call.message.chat.id, "Send folder name to delete:
`delete folder_name`", parse_mode="Markdown")
    elif call.data == "my_folders":
        folder_path = user_folder(user_id)
        folders = os.listdir(folder_path)
        if not folders:
            bot.send_message(call.message.chat.id, "❌ No folders found.")
            return
        for folder in folders:
            files = os.listdir(os.path.join(folder_path, folder))
            text = f"📁 *{folder}* - {len(files)} files"
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif call.data == "admin" and user_id == ADMIN_ID:
        users = sqlite3.connect("users.db").cursor().execute("SELECT * FROM users").fetchall()
        bot.send_message(call.message.chat.id, f"👥 Total Users: {len(users)}\nUser IDs: {[u[0] for u in users]}")

# === Message Handler ===
@bot.message_handler(func=lambda m: True, content_types=['text', 'document'])
def text_handler(msg):
    user_id = msg.from_user.id
    text = msg.text

    if text.startswith("signup "):
        _, username, password = text.split(" ", 2)
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        if c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone():
            bot.send_message(msg.chat.id, "⚠️ Username already exists.")
        else:
            c.execute("INSERT INTO users (user_id, username, password) VALUES (?, ?, ?)", (user_id, username, hash_password(password)))
            conn.commit()
            bot.send_message(msg.chat.id, "✅ Signup successful. You can now login.")
        conn.close()

    elif text.startswith("login "):
        _, username, password = text.split(" ", 2)
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        user = c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hash_password(password))).fetchone()
        if user:
            sessions[user_id] = username
            bot.send_message(msg.chat.id, "✅ Login successful.")
        else:
            bot.send_message(msg.chat.id, "❌ Invalid username or password.")
        conn.close()

    elif text.startswith("folder "):
        if not is_logged_in(user_id):
            bot.send_message(msg.chat.id, "Please login first.")
            return
        folder_name = text.split(" ", 1)[1]
        path = os.path.join(user_folder(user_id), folder_name)
        os.makedirs(path, exist_ok=True)
        bot.send_message(msg.chat.id, f"✅ Folder '{folder_name}' created.")

    elif text.startswith("delete "):
        if not is_logged_in(user_id):
            bot.send_message(msg.chat.id, "Please login first.")
            return
        folder_name = text.split(" ", 1)[1]
        path = os.path.join(user_folder(user_id), folder_name)
        if os.path.exists(path):
            for file in os.listdir(path):
                os.remove(os.path.join(path, file))
            os.rmdir(path)
            bot.send_message(msg.chat.id, f"🗑️ Folder '{folder_name}' deleted.")
        else:
            bot.send_message(msg.chat.id, "⚠️ Folder not found.")

    elif msg.document:
        if not is_logged_in(user_id):
            bot.send_message(msg.chat.id, "Please login first to upload files.")
            return
        folder_name = "default"
        folder_path = os.path.join(user_folder(user_id), folder_name)
        os.makedirs(folder_path, exist_ok=True)
        file_info = bot.get_file(msg.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_path = os.path.join(folder_path, msg.document.file_name)
        with open(file_path, "wb") as f:
            f.write(downloaded_file)
        bot.send_message(msg.chat.id, f"📤 File saved in folder '{folder_name}'.")

    if msg.text:
        bot.send_message(msg.chat.id, POWERED_BY)

print("🤖 Bot is running...")
bot.polling()
