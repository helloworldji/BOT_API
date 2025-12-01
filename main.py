import telebot
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Bot token (private repo OK)
BOT_TOKEN = "7587534243:AAEwvsy_Mr6YbUvOSzVPMNW1hqf8xgUU_0M"
API_URL = "https://meowmeow.rf.gd/gand/mobile.php?num={}&i=1"

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

def menu_markup():
    k = InlineKeyboardMarkup()
    k.add(InlineKeyboardButton("🔍 Search Number", callback_data="search"))
    return k

def result_markup():
    k = InlineKeyboardMarkup()
    k.add(
        InlineKeyboardButton("🔄 Search Again", callback_data="search"),
        InlineKeyboardButton("🏠 Menu", callback_data="menu")
    )
    return k

@bot.message_handler(commands=['start'])
def start(m):
    name = m.from_user.first_name or "User"
    bot.send_message(m.chat.id, f"Hi {name}!\nTap below to search a mobile number.", reply_markup=menu_markup())

@bot.callback_query_handler(func=lambda c: True)
def handle_cb(c):
    chat_id = c.message.chat.id
    if c.data == "menu":
        start(c.message)
        try:
            bot.delete_message(chat_id, c.message.message_id)
        except:
            pass
    elif c.data == "search":
        user_state[chat_id] = True
        bot.edit_message_text("📲 Send a 10-digit mobile number:", chat_id, c.message.message_id)
    bot.answer_callback_query(c.id)

@bot.message_handler(func=lambda m: True)
def handle_msg(m):
    cid = m.chat.id
    if user_state.get(cid):
        num = clean_number(m.text)
        if len(num) != 10:
            bot.reply_to(m, "❌ Invalid number. Please send exactly 10 digits.")
            return

        wait_msg = bot.send_message(cid, "⏳ Looking up...")
        results = None
        try:
            resp = requests.get(API_URL.format(num), timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    results = data.get("result", [])
        except Exception as e:
            pass  # Silent fail for speed

        bot.delete_message(cid, wait_msg.message_id)

        if not results:
            bot.send_message(cid, "⚠️ No records found.", reply_markup=result_markup())
            return

        seen = set()
        count = 0
        for rec in results:
            key = (rec.get("mobile"), rec.get("name"))
            if key in seen or count >= 3:
                continue
            seen.add(key)
            count += 1

            name = rec.get("name", "N/A")
            fname = rec.get("father_name", "N/A")
            mob = fmt_phone(rec.get("mobile", num))
            alt = rec.get("alt_mobile", "")
            alt = fmt_phone(alt) if alt and len(alt) == 10 else "Not Available"
            addr = fmt_addr(rec.get("address", ""))
            circle = rec.get("circle", "N/A")
            id_num = rec.get("id_number", "N/A")

            msg = f"""✅ <b>Result</b>

👤 <b>Name:</b> {name}
👨 <b>Father:</b> {fname}
📱 <b>Mobile:</b> <code>{mob}</code>
📱 <b>Alternate:</b> <code>{alt}</code>
📍 <b>Address:</b>
{addr}
🌐 <b>Circle:</b> {circle}
🆔 <b>ID:</b> <code>{id_num}</code>"""

            bot.send_message(cid, msg, parse_mode="HTML", reply_markup=result_markup())

        user_state.pop(cid, None)
    else:
        bot.send_message(cid, "💡 Use the button below to search.", reply_markup=menu_markup())

# Flask webhook for Render
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
    return {"status": "running"}

@app.route('/health')
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import os
    bot.remove_webhook()
    time = __import__('time')
    time.sleep(1)
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-render-url.onrender.com")
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
