import telebot
from telebot import types
from flask import Flask, request
import requests
import os
import logging

# --- Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-api-b6ql.onrender.com')

# Valid Cookie Storage
# In a real app, use a database. Here we use a global variable.
# When the bot restarts (server sleep), you might need to set it again.
BOT_COOKIE = None

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
logging.basicConfig(level=logging.INFO)

# --- Helper Functions ---

def get_search_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔍 Search Number", callback_data="search_num"))
    return markup

def get_search_again_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Search Again", callback_data="search_num"))
    return markup

def fetch_api_data(mobile_number):
    global BOT_COOKIE
    
    # 1. Check if we have a cookie
    if not BOT_COOKIE:
        return "MISSING_COOKIE"

    try:
        url = f"https://meowmeow.rf.gd/gand/mobile.php?num={mobile_number}"
        
        # 2. Send the Request with the USER'S COOKIE
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cookie': BOT_COOKIE  # This is the magic key
        }
        
        logging.info(f"Using Cookie: {BOT_COOKIE[:15]}...")
        response = requests.get(url, headers=headers, timeout=10)
        
        # 3. Check for Security Block
        if "aes.js" in response.text or "cookie" in response.text.lower():
            return "EXPIRED_COOKIE"
            
        return response.json()

    except Exception as e:
        logging.error(f"Error: {e}")
        return None

# --- Bot Handlers ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    status = "🔴 Disconnected" if not BOT_COOKIE else "🟢 Connected"
    welcome_text = (
        f"👋 Hello {message.from_user.first_name}!\n\n"
        f"**Status:** {status}\n\n"
        "To make this work, you must provide the access token from your browser.\n\n"
        "1. Open the link in Chrome.\n"
        "2. Press F12 -> Application -> Cookies.\n"
        "3. Copy the value of `__test`.\n"
        "4. Type: `/auth <paste_cookie_here>`"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_search_keyboard())

@bot.message_handler(commands=['auth'])
def set_auth_cookie(message):
    """Command to set the cookie manually."""
    global BOT_COOKIE
    try:
        # User sends: /auth 8d7f8d7f8d7f...
        cookie_val = message.text.split(" ", 1)[1].strip()
        
        # Format it correctly for the header
        if "__test=" not in cookie_val:
            BOT_COOKIE = f"__test={cookie_val}"
        else:
            BOT_COOKIE = cookie_val
            
        bot.reply_to(message, "✅ **Access Token Saved!**\nNow try searching.")
    except IndexError:
        bot.reply_to(message, "⚠️ **Error:** Please paste the cookie value.\nExample: `/auth 90f8d7f8d7...`")

@bot.callback_query_handler(func=lambda call: call.data == "search_num")
def callback_query(call):
    bot.answer_callback_query(call.id)
    if not BOT_COOKIE:
        bot.send_message(call.message.chat.id, "🔴 **Auth Missing!**\nPlease use `/auth` to set the cookie first.")
        return

    msg = bot.send_message(call.message.chat.id, "Enter **10-digit number**:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_number_step)

def process_number_step(message):
    chat_id = message.chat.id
    mobile_number = message.text.strip()

    if not mobile_number.isdigit() or len(mobile_number) != 10:
        bot.send_message(chat_id, "❌ Invalid number.")
        return

    loading_msg = bot.send_message(chat_id, "⏳ Fetching...")
    
    data = fetch_api_data(mobile_number)
    
    try:
        bot.delete_message(chat_id, loading_msg.message_id)
    except:
        pass

    if data == "MISSING_COOKIE":
        bot.send_message(chat_id, "🔴 **Setup Required**\nUse `/auth <cookie_value>` to connect.")
    elif data == "EXPIRED_COOKIE":
        bot.send_message(chat_id, "⚠️ **Token Expired**\nThe server changed the lock. Please get a new cookie from your browser and use `/auth` again.")
    elif data and isinstance(data, dict) and data.get("success"):
        info = data["result"][0]
        result_text = (
            "✅ **Details Found:**\n\n"
            f"👤 Name: `{info.get('name', 'N/A')}`\n"
            f"👨‍👦 Father: `{info.get('father_name', 'N/A')}`\n"
            f"📍 Addr: `{info.get('address', 'N/A')}`\n"
            f"📱 Mob: `{info.get('mobile', 'N/A')}`"
        )
        bot.send_message(chat_id, result_text, parse_mode="Markdown", reply_markup=get_search_again_keyboard())
    else:
        bot.send_message(chat_id, "⚠️ **No data found.**", reply_markup=get_search_again_keyboard())

# --- Webhook Routes ---

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}")
    return "Webhook Set", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
