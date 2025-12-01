import telebot
from telebot import types
from flask import Flask, request
import requests
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
    Fetches data using standard Requests, but with Browser Headers.
    """
    try:
        # The exact URL structure you confirmed works
        url = f"https://meowmeow.rf.gd/gand/mobile.php?num={mobile_number}"
        
        # We MUST send these headers. If we don't, rf.gd sees "Python" and blocks it immediately.
        # These headers make the bot say "I am a Chrome Browser" to the server.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }

        logging.info(f"Requesting: {url}")
        
        # Create a session to handle cookies automatically like a browser
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        logging.info(f"Status Code: {response.status_code}")

        # Try to parse the JSON
        try:
            return response.json()
        except Exception:
            # If JSON fails, it might be the HTML security page
            logging.error(f"Response was not JSON. Content: {response.text[:200]}")
            return None

    except Exception as e:
        logging.error(f"Request Failed: {e}")
        return None

# --- Bot Handlers ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        f"👋 Hello {message.from_user.first_name}!\n\n"
        "Click the button below to search."
    )
    bot.reply_to(message, welcome_text, reply_markup=get_search_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "search_num")
def callback_query(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Enter **10-digit number**:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_number_step)

def process_number_step(message):
    chat_id = message.chat.id
    mobile_number = message.text.strip()

    if not mobile_number.isdigit() or len(mobile_number) != 10:
        bot.send_message(chat_id, "❌ Invalid number.", reply_markup=get_search_again_keyboard())
        return

    loading_msg = bot.send_message(chat_id, "⏳ Fetching...")

    data = fetch_api_data(mobile_number)
    
    try:
        bot.delete_message(chat_id, loading_msg.message_id)
    except:
        pass

    if data and isinstance(data, dict) and data.get("success"):
        # Data found
        if data.get("result"):
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
             bot.send_message(chat_id, "⚠️ Data found but result is empty.", reply_markup=get_search_again_keyboard())
    else:
        # Error / No Data
        bot.send_message(chat_id, "⚠️ **No data found.**\n(Server might be blocking requests)", parse_mode="Markdown", reply_markup=get_search_again_keyboard())

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
