import telebot
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configuration
BOT_TOKEN = "7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M"
WEBHOOK_URL = "https://bot-api-b6ql.onrender.com"
API_URL = "https://meowmeow.rf.gd/gand/mobile.php?num={}"

bot = telebot.TeleBot(BOT_TOKEN)
user_state = {}

def clean_number(s):
    n = ''.join(filter(str.isdigit, s))
    if n.startswith('91') and len(n) > 10:
        n = n[2:]
    if n.startswith('0') and len(n) == 11:
        n = n[1:]
    return n[-10:] if len(n) >= 10 else ""

def fmt_phone(p):
    return f"+91 {p[:5]} {p[5:]}" if len(p) == 10 else p

def fmt_addr(a):
    if not a or a.lower() == "null":
        return "Not Available"
    parts = [x.strip() for x in a.replace("!!", "!").split("!") if x.strip() and x.strip() != "null"]
    return "\n".join(parts[:4]) or "Not Available"

def menu_kb():
    k = InlineKeyboardMarkup()
    k.add(InlineKeyboardButton("🔍 Search Number", callback_data="search"))
    return k

def result_kb():
    k = InlineKeyboardMarkup()
    k.add(
        InlineKeyboardButton("🔄 Search Again", callback_data="search"),
        InlineKeyboardButton("🏠 Menu", callback_data="menu")
    )
    return k

@bot.message_handler(commands=['start'])
def start(m):
    name = m.from_user.first_name or "User"
    bot.send_message(m.chat.id, f"Hi {name}!\nTap below to search a mobile number.", reply_markup=menu_kb())

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    cid = c.message.chat.id
    if c.data == "menu":
        start(c.message)
        try:
            bot.delete_message(cid, c.message.message_id)
        except:
            pass
    elif c.data == "search":
        user_state[cid] = True
        bot.edit_message_text("📲 Send a 10-digit mobile number:", cid, c.message.message_id)
    bot.answer_callback_query(c.id)

@bot.message_handler(func=lambda m: True)
def handle(m):
    cid = m.chat.id
    if user_state.get(cid):
        num = clean_number(m.text)
        if len(num) != 10:
            bot.reply_to(m, "❌ Please send a valid 10-digit number.")
            return

        wait = bot.send_message(cid, "⏳ Searching...")
        results = None
        try:
            resp = requests.get(API_URL.format(num), timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    results = data.get("result", [])
        except:
            pass

        bot.delete_message(cid, wait.message_id)

        if not results:
            bot.send_message(cid, "⚠️ No data found.", reply_markup=result_kb())
            return

        seen = set()
        sent = 0
        for r in results:
            key = (r.get("mobile"), r.get("name"))
            if key in seen or sent >= 3:
                continue
            seen.add(key)
            sent += 1

            name = r.get("name", "N/A")
            fname = r.get("father_name", "N/A")
            mob = fmt_phone(r.get("mobile", num))
            alt = r.get("alt_mobile", "")
            alt = fmt_phone(alt) if alt and len(alt) == 10 else "Not Available"
            addr = fmt_addr(r.get("address", ""))
            circle = r.get("circle", "N/A")
            id_num = r.get("id_number", "N/A")

            msg = f"""✅ <b>Result</b>

👤 <b>Name:</b> {name}
👨 <b>Father:</b> {fname}
📱 <b>Mobile:</b> <code>{mob}</code>
📱 <b>Alternate:</b> <code>{alt}</code>
📍 <b>Address:</b>
{addr}
🌐 <b>Circle:</b> {circle}
🆔 <b>ID:</b> <code>{id_num}</code>"""
            bot.send_message(cid, msg, parse_mode="HTML", reply_markup=result_kb())

        user_state.pop(cid, None)
    else:
        bot.send_message(cid, "💡 Tap the button below to search.", reply_markup=menu_kb())

# Flask webhook server
from flask import Flask, request
app = Flask(__name__)

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Invalid', 403

@app.route('/')
def home():
    return {"status": "running", "webhook": f"{WEBHOOK_URL}/{BOT_TOKEN}"}

@app.route('/health')
def health():
    return {"status": "healthy"}

# Set webhook on startup
if __name__ == "__main__":
    import time
    bot.remove_webhook()
    time.sleep(1)
    full_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    bot.set_webhook(url=full_url)
    print(f"✅ Webhook set to: {full_url}")
    
    port = int(__import__('os').getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
