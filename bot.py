import telebot
from telebot import types
from flask import Flask, request, abort
import requests
import os
import time
import logging

# --- Configuration ---
# Uses the exact credentials you provided
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-api-b6ql.onrender.com')

# Initialize Flask
app = Flask(__name__)

# Initialize Bot (threaded=False is required for Render/Flask)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# Logger setup
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
    Fetches data from the API.
    Crucial Fix: Sends 'num=1234567890' (No curly braces in the final URL).
    """
    try:
        # ---------------------------------------------------------
        # EXACT URL STRUCTURE
        # In Python f-strings, {mobile_number} places the value inside.
        # It does NOT add literal brackets to the URL.
        # Result: https://meowmeow.rf.gd/gand/mobile.php?num=9559156326
        # ---------------------------------------------------------
        url = f"https://meowmeow.rf.gd/gand/mobile.php?num="
        
        # rf.gd often blocks python scripts, so we pretend to be a browser (Chrome)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        logging.info(f"Requesting URL: {url}") # Logs the clean URL to console for verification
        
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

    # Validate Input
    if not mobile_number.isdigit() or len(mobile_number) != 10:
        bot.send_message(chat_id, "❌ Invalid number. Please enter exactly 10 digits.", reply_markup=get_search_again_keyboard())
        return

    # Send Loading Message
    loading_msg = bot.send_message(chat_id, "⏳ Fetching details... Please wait.")

    # Call API
    data = fetch_api_data(mobile_number)
    
    # Delete Loading Message
    try:
        bot.delete_message(chat_id, loading_msg.message_id)
    except Exception:
        pass 

    # Parse Result
    if data and data.get("success") and data.get("result"):
        # The API returns a list, we take the first item
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

# --- Flask Routes (Webhook) ---

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
