import telebot
import requests
import os
import time
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

# ==================== Configuration ====================
# Get token from Environment Variable on Render or hardcode it for testing
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M')

# The New API URL
API_URL = "https://meowmeow.rf.gd/gand/mobile.php?num={}&i=1"

# Webhook Configuration
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-api-b6ql.onrender.com') # Auto-detected on Render

# Initialize Bot and Flask
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ==================== Helper Functions ====================
def clean_number(number: str) -> str:
    """Extracts only digits and ensures 10 digit format."""
    cleaned = ''.join(filter(str.isdigit, number))
    if len(cleaned) > 10:
        cleaned = cleaned[-10:] # Take last 10 digits
    return cleaned

def fetch_data(mobile: str):
    """Fetches data from the new API."""
    try:
        url = API_URL.format(mobile)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"API Error: {e}")
        return None

# ==================== Bot Handlers ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_name = message.from_user.first_name
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 Search Number", callback_data="search_mode"))
    
    welcome_text = (
        f"Hi {user_name} 👋\n\n"
        f"I am a Mobile Info Lookup Bot.\n"
        f"Click the button below to start searching."
    )
    
    bot.reply_to(message, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "search_mode")
def callback_query(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Please send the **10-digit Mobile Number** you want to look up.")
    
    # Register next step handler to capture the number
    bot.register_next_step_handler(msg, process_number_step)

def process_number_step(message):
    if not message.text:
        bot.reply_to(message, "Please send text only.")
        return

    mobile = clean_number(message.text)

    if len(mobile) != 10:
        bot.reply_to(message, "❌ Invalid number format. Please send a valid 10-digit number.")
        return

    status_msg = bot.reply_to(message, "🔄 Fetching details... Please wait.")

    data = fetch_data(mobile)

    # Logic to parse the specific JSON structure provided
    # {"success":true,"result":[{"id":..., "mobile":..., "name":...}]}
    
    if data and data.get("success") and data.get("result"):
        results = data.get("result", [])
        
        if len(results) > 0:
            # We take the first result, or loop if you want multiple
            info = results[0]
            
            response_text = (
                f"✅ **Details Found**\n\n"
                f"📱 **Mobile:** `{info.get('mobile', 'N/A')}`\n"
                f"👤 **Name:** {info.get('name', 'N/A')}\n"
                f"👨‍🦳 **Father Name:** {info.get('father_name', 'N/A')}\n"
                f"🏠 **Address:** {info.get('address', 'N/A')}\n"
                f"📞 **Alt Mobile:** `{info.get('alt_mobile', 'N/A')}`\n"
                f"📡 **Circle:** {info.get('circle', 'N/A')}\n"
                f"🆔 **ID Number:** {info.get('id_number', 'N/A')}\n"
            )
            
            # Delete "Fetching" message and send result
            bot.delete_message(message.chat.id, status_msg.message_id)
            bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
            
            # Show search button again
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔍 Search Again", callback_data="search_mode"))
            bot.send_message(message.chat.id, "Search another?", reply_markup=markup)
            
        else:
            bot.edit_message_text("❌ No data found for this number.", message.chat.id, status_msg.message_id)
    else:
        bot.edit_message_text("❌ No details found or API error.", message.chat.id, status_msg.message_id)

# ==================== Flask Routes for Render ====================

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    # Set webhook using the URL Render provides
    if WEBHOOK_URL:
        bot.set_webhook(url=WEBHOOK_URL + "/" + BOT_TOKEN)
        return f"Webhook set to {WEBHOOK_URL}", 200
    else:
        return "Webhook not set. Env var RENDER_EXTERNAL_URL missing.", 200

@app.route("/health")
def health_check():
    return "Alive", 200

# ==================== Main Execution ====================
if __name__ == "__main__":
    # Render provides PORT environment variable
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
