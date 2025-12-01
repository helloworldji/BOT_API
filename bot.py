import telebot
from telebot import types
from flask import Flask, request, abort
import cloudscraper  # REPLACES 'requests' to bypass rf.gd anti-bot protection
import os
import time
import logging

# --- Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-api-b6ql.onrender.com')

# --- Initialization ---
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
logging.basicConfig(level=logging.INFO)

# Initialize the CloudScraper to mimic a Chrome browser
# This is CRITICAL for accessing rf.gd sites
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

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
    Fetches data using CloudScraper to bypass anti-bot protection.
    """
    try:
        # 1. Construct the URL.
        # Python f-string replaces {mobile_number} with the actual digits.
        # It does NOT add curly braces to the final link.
        # Example: https://meowmeow.rf.gd/gand/mobile.php?num=9559156326
        url = f"https://meowmeow.rf.gd/gand/mobile.php?num={mobile_number}"
        
        logging.info(f"Fetching URL: {url}")

        # 2. Use scraper.get() instead of requests.get()
        # This handles the cookies and User-Agent automatically.
        response = scraper.get(url, timeout=15)
        
        # 3. Check status
        if response.status_code == 200:
            # rf.gd might return HTML error pages even with 200 OK
            # We try to parse JSON. If it fails, it's likely a security page.
            try:
                return response.json()
            except ValueError:
                logging.error("Response was not JSON. Likely an HTML security page.")
                return None
        else:
            logging.error(f"API Error Status: {response.status_code}")
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

    # Basic Validation
    if not mobile_number.isdigit() or len(mobile_number) != 10:
        bot.send_message(chat_id, "❌ Invalid number. Please enter exactly 10 digits.", reply_markup=get_search_again_keyboard())
        return

    loading_msg = bot.send_message(chat_id, "⏳ Fetching details... (This may take a moment)")

    # Call the API
    data = fetch_api_data(mobile_number)
    
    # Clean up loading message
    try:
        bot.delete_message(chat_id, loading_msg.message_id)
    except Exception:
        pass

    # Parse Response
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
        # Fallback error message
        bot.send_message(
            chat_id, 
            "⚠️ **No data found** or the external server blocked the request.\nTry searching again later.", 
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
