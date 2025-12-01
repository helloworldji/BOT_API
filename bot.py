import telebot
from telebot import types
from flask import Flask, request
from curl_cffi import requests  # REPLACES cloudscraper
import os
import logging

# --- Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-api-b6ql.onrender.com')

# --- Initialization ---
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
    Fetches data using curl_cffi to impersonate a real Chrome browser's TLS signature.
    """
    try:
        url = f"https://meowmeow.rf.gd/gand/mobile.php?num={mobile_number}"
        logging.info(f"Fetching URL: {url}")

        # IMPERSONATE CHROME
        # This sends the request exactly like Chrome version 110 would.
        response = requests.get(url, impersonate="chrome110", timeout=15)
        
        # Check if we actually got JSON or the HTML security page
        try:
            return response.json()
        except Exception:
            # If json decode fails, log the first 100 chars of the text to see what we got
            logging.error(f"Failed to parse JSON. Response text start: {response.text[:100]}")
            return None

    except Exception as e:
        logging.error(f"Request Failed: {e}")
        return None

# --- Bot Handlers ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        f"👋 Hello {message.from_user.first_name}!\n\n"
        "I can help you search for details using a mobile number.\n"
        "Click the button below to get started."
    )
    bot.reply_to(message, welcome_text, reply_markup=get_search_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "search_num")
def callback_query(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Please enter the **10-digit mobile number**:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_number_step)

def process_number_step(message):
    chat_id = message.chat.id
    mobile_number = message.text.strip()

    if not mobile_number.isdigit() or len(mobile_number) != 10:
        bot.send_message(chat_id, "❌ Invalid number. Please enter exactly 10 digits.", reply_markup=get_search_again_keyboard())
        return

    loading_msg = bot.send_message(chat_id, "⏳ Fetching details...")

    data = fetch_api_data(mobile_number)
    
    try:
        bot.delete_message(chat_id, loading_msg.message_id)
    except Exception:
        pass

    if data and data.get("success") and data.get("result"):
        info = data["result"][0]
        result_text = (
            "✅ **Details Found:**\n\n"
            f"👤 **Name:** `{info.get('name', 'N/A')}`\n"
            f"👨‍👦 **Father's Name:** `{info.get('father_name', 'N/A')}`\n"
            f"📍 **Address:** `{info.get('address', 'N/A')}`\n"
            f"📱 **Mobile:** `{info.get('mobile', 'N/A')}`"
        )
        bot.send_message(chat_id, result_text, parse_mode="Markdown", reply_markup=get_search_again_keyboard())
    else:
        # Detailed error message for you to understand what happened
        bot.send_message(
            chat_id, 
            "⚠️ **No data found.**\n\nThe external server (`rf.gd`) detected the bot and blocked the request.\nTry searching again in a few minutes.", 
            parse_mode="Markdown", 
            reply_markup=get_search_again_keyboard()
        )

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
    s = bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}")
    if s:
        return f"Webhook set to {RENDER_EXTERNAL_URL}", 200
    else:
        return "Webhook setup failed", 500

@app.route("/health")
def health_check():
    return "Alive", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
