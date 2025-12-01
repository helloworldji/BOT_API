import telebot
from telebot import types
from flask import Flask, request
import requests
import os
import logging

# --- Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-api-b6ql.onrender.com')

# Global variable to store the cookie in memory
# (Note: In a real app, you'd use a database, but this works for a simple bot)
CURRENT_COOKIE = None 

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
    """
    Fetches data using the manually provided '__test' cookie.
    """
    global CURRENT_COOKIE
    
    if not CURRENT_COOKIE:
        return "NO_COOKIE"

    try:
        url = f"https://meowmeow.rf.gd/gand/mobile.php?num={mobile_number}"
        
        # We must mimic a browser exactly
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cookie': f'__test={CURRENT_COOKIE}' 
        }

        logging.info(f"Fetching with cookie: {CURRENT_COOKIE[:10]}...")
        
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if we got the security page again (HTML) instead of JSON
        if "aes.js" in response.text or "script" in response.text:
            return "COOKIE_EXPIRED"
            
        return response.json()

    except Exception as e:
        logging.error(f"Request Failed: {e}")
        return None

# --- Bot Handlers ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        f"👋 Hello {message.from_user.first_name}!\n\n"
        "**System Status:** " + ("🟢 Online" if CURRENT_COOKIE else "🔴 Cookie Missing") + "\n\n"
        "Use /setcookie <value> to update the security token."
    )
    bot.reply_to(message, welcome_text, reply_markup=get_search_keyboard())

@bot.message_handler(commands=['setcookie'])
def set_cookie_command(message):
    """Command to manually update the __test cookie."""
    global CURRENT_COOKIE
    try:
        # Extract the cookie value from the message (e.g., "/setcookie d8s7f9d8s7...")
        cookie_value = message.text.split()[1]
        CURRENT_COOKIE = cookie_value.strip()
        bot.reply_to(message, "✅ **Cookie Updated!**\nTry searching now.")
    except IndexError:
        bot.reply_to(message, "⚠️ Usage: `/setcookie <your_cookie_value>`\n\nGo to the website -> F12 -> Application -> Cookies -> Copy value of `__test`.")

@bot.callback_query_handler(func=lambda call: call.data == "search_num")
def callback_query(call):
    bot.answer_callback_query(call.id)
    if not CURRENT_COOKIE:
        bot.send_message(call.message.chat.id, "🔴 **Error:** Cookie is missing.\nPlease use `/setcookie` first.")
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

    if data == "NO_COOKIE":
        bot.send_message(chat_id, "🔴 **System Paused.**\nPlease send a new cookie using `/setcookie`.")
    elif data == "COOKIE_EXPIRED":
        bot.send_message(chat_id, "⚠️ **Cookie Expired.**\nThe security token has changed. Please fetch a new `__test` cookie and update it.")
    elif data and isinstance(data, dict) and data.get("success"):
        info = data["result"][0]
        result_text = (
            "✅ **Details Found:**\n\n"
            f"👤 Name: `{info.get('name', 'N/A')}`\n"
            f"📍 Addr: `{info.get('address', 'N/A')}`\n"
            f"📱 Mob: `{info.get('mobile', 'N/A')}`"
        )
        bot.send_message(chat_id, result_text, parse_mode="Markdown", reply_markup=get_search_again_keyboard())
    else:
        bot.send_message(chat_id, "⚠️ No data found.", reply_markup=get_search_again_keyboard())

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
