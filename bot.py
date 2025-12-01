import telebot
from telebot import types
from flask import Flask, request, abort
import requests
import os
import time
import logging

# --- Configuration ---
# In production on Render, these should be set in the "Environment" tab.
# We provide defaults here based on your request for immediate testing.
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-api-b6ql.onrender.com')

# Validate configuration
if not BOT_TOKEN or not RENDER_EXTERNAL_URL:
    raise ValueError("BOT_TOKEN and RENDER_EXTERNAL_URL must be set.")

# Initialize Flask
app = Flask(__name__)

# Initialize Bot (threaded=False is crucial for Flask/Render integration)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# Logger setup
logging.basicConfig(level=logging.INFO)

# --- Helper Functions ---

def get_search_keyboard():
    """Returns the inline keyboard with the Search button."""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔍 Search Number", callback_data="search_num"))
    return markup

def get_search_again_keyboard():
    """Returns the inline keyboard for searching again."""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Search Again", callback_data="search_num"))
    return markup

def fetch_api_data(mobile_number):
    """
    Calls the API and parses the JSON.
    Fixes the issue where brackets were included in the URL.
    """
    try:
        # User specified fix: ensure no extra braces, just the raw number
        url = f"https://meowmeow.rf.gd/gand/mobile.php?num={mobile_number}"
        
        # Headers specifically to mimic a browser, often needed for free hosting like rf.gd
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logging.error(f"API Error: {e}")
        return None

# --- Bot Handlers ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Handle /start command."""
    welcome_text = (
        f"👋 Hello {message.from_user.first_name}!\n\n"
        "I can help you search for details using a mobile number.\n"
        "Click the button below to get started."
    )
    bot.reply_to(message, welcome_text, reply_markup=get_search_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "search_num")
def callback_query(call):
    """Handle the Search Number button click."""
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Please enter the **10-digit mobile number**:", parse_mode="Markdown")
    
    # Register the next step to capture the input
    bot.register_next_step_handler(msg, process_number_step)

def process_number_step(message):
    """Validate input and call API."""
    chat_id = message.chat.id
    mobile_number = message.text.strip()

    # 1. Validation
    if not mobile_number.isdigit() or len(mobile_number) != 10:
        bot.send_message(chat_id, "❌ Invalid number. Please enter exactly 10 digits.", reply_markup=get_search_again_keyboard())
        return

    # 2. Send "Fetching" message
    loading_msg = bot.send_message(chat_id, "⏳ Fetching details... Please wait.")

    # 3. Call API
    data = fetch_api_data(mobile_number)
    
    # 4. Delete "Fetching" message
    try:
        bot.delete_message(chat_id, loading_msg.message_id)
    except Exception:
        pass # Ignore if message already deleted or too old

    # 5. Process Result
    if data and data.get("success") and data.get("result"):
        # The API returns a list in "result", we take the first item
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
        error_text = "⚠️ **No data found** for this number or the server is busy."
        bot.send_message(chat_id, error_text, parse_mode="Markdown", reply_markup=get_search_again_keyboard())

# --- Flask Routes for Render Webhook ---

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    """Webhook endpoint: Receives updates from Telegram."""
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    """Root endpoint: Sets the webhook."""
    bot.remove_webhook()
    # Set webhook to the Render URL + Bot Token
    s = bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}")
    if s:
        return f"Webhook set successfully to {RENDER_EXTERNAL_URL}", 200
    else:
        return "Webhook setup failed", 500

@app.route("/health")
def health_check():
    """Health check endpoint to keep the bot alive."""
    return "Alive", 200

# --- Entry Point ---

if __name__ == "__main__":
    # Render provides the PORT environment variable
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
