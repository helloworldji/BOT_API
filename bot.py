import telebot
import requests
import os
import time
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

# ==================== Configuration ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M')

# 🆕 UPDATED API URL
API_URL = "http://userdata-api-741531179234.europe-west1.run.app/aadi/{}"

# Webhook Configuration
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-api-b6ql.onrender.com').rstrip('/')

# Initialize Bot (threaded=False is CRITICAL for Render)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# ==================== Helper Functions ====================
def clean_number(number: str) -> str:
    cleaned = ''.join(filter(str.isdigit, number))
    if len(cleaned) > 10:
        cleaned = cleaned[-10:]
    return cleaned

def fetch_data(mobile: str):
    try:
        # Appends mobile number to the URL
        url = API_URL.format(mobile)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Increased timeout slightly as cloud run can sometimes cold start
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"API Error: {e}")
        return None

# ==================== Bot Handlers ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    print("COMMAND: /start received")
    user_name = message.from_user.first_name
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 Search Number", callback_data="search_mode"))
    
    bot.reply_to(message, f"Hi {user_name} 👋\n\nClick the button to start searching.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "search_mode")
def callback_query(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Send the **10-digit Mobile Number**.")
    bot.register_next_step_handler(msg, process_number_step)

def process_number_step(message):
    if not message.text:
        bot.reply_to(message, "Text only please.")
        return

    mobile = clean_number(message.text)
    if len(mobile) != 10:
        bot.reply_to(message, "❌ Invalid number. Send 10 digits.")
        return

    status_msg = bot.reply_to(message, "🔄 Fetching details... Please wait.")
    data = fetch_data(mobile)
    
    # Logic to parse the specific JSON structure:
    # {"found": true, "data": [{"Name": "...", "C_O": "...", ...}]}
    if data and data.get("found") is True and data.get("data"):
        results = data.get("data", [])
        
        if len(results) > 0:
            info = results[0]
            
            # Clean up address formatting (replace !! with , )
            raw_address = info.get('Address', 'N/A')
            clean_addr = raw_address.replace('!!', ', ').replace('!', ', ') if raw_address else 'N/A'

            response_text = (
                f"✅ **Details Found**\n\n"
                f"📱 **Mobile:** `{info.get('Mobile_Number', mobile)}`\n"
                f"👤 **Name:** {info.get('Name', 'N/A')}\n"
                f"👨‍🦳 **Father Name:** {info.get('C_O', 'N/A')}\n"
                f"🏠 **Address:** {clean_addr}\n"
                f"📞 **Alt Mobile:** `{info.get('Alternative_No', 'N/A')}`\n"
                f"📧 **Email:** {info.get('Email_Id', 'N/A')}\n"
                f"📡 **Circle:** {info.get('Circle', 'N/A')}\n"
                f"🆔 **UID:** {info.get('UID', 'N/A')}\n"
            )
            
            bot.delete_message(message.chat.id, status_msg.message_id)
            bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
            
            # Reset Flow
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔍 Search Again", callback_data="search_mode"))
            bot.send_message(message.chat.id, "Search another?", reply_markup=markup)
            return

    bot.edit_message_text("❌ No data found.", message.chat.id, status_msg.message_id)

# ==================== Flask Routes ====================
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    try:
        print("WEBHOOK: Received Update")
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print(f"WEBHOOK ERROR: {e}")
        return "Error", 500

@app.route("/")
def webhook():
    bot.remove_webhook()
    time.sleep(0.5)
    url_to_set = WEBHOOK_URL + "/" + BOT_TOKEN
    print(f"Setting webhook to: {url_to_set}")
    bot.set_webhook(url=url_to_set)
    return f"Webhook set to {url_to_set}", 200

@app.route("/health")
def health_check():
    return "Alive", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
