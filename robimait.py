import requests
import re
import time
import hashlib
import html
from bs4 import BeautifulSoup
from flask import Flask, Response
import threading
import telegram
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
import os
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import pycountry

EXTRA_CODES = {"Kosovo": "XK"}  # special cases

def country_to_flag(country_name: str) -> str:
    code = EXTRA_CODES.get(country_name)
    if not code:
        try:
            country = pycountry.countries.lookup(country_name)
            code = country.alpha_2
        except LookupError:
            return ""
    return "".join(chr(127397 + ord(c)) for c in code.upper())

# Configuration
LOGIN_URL = "http://217.23.5.21/ints/signin"
XHR_URL = "http://217.23.5.21/ints/agent/res/data_smscdr.php?fdate1=2025-09-08%2000:00:00&fdate2=2025-09-08%2023:59:59&frange=&fclient=&fnum=&fcli=&fgdate=&fgmonth=&fgrange=&fgclient=&fgnumber=&fgcli=&fg=0&sEcho=1&iColumns=9&sColumns=%2C%2C%2C%2C%2C%2C%2C%2C&iDisplayStart=0&iDisplayLength=25&mDataProp_0=0&sSearch_0=&bRegex_0=false&bSearchable_0=true&bSortable_0=true&mDataProp_1=1&sSearch_1=&bRegex_1=false&bSearchable_1=true&bSortable_1=true&mDataProp_2=2&sSearch_2=&bRegex_2=false&bSearchable_2=true&bSortable_2=true&mDataProp_3=3&sSearch_3=&bRegex_3=false&bSearchable_3=true&bSortable_3=true&mDataProp_4=4&sSearch_4=&bRegex_4=false&bSearchable_4=true&bSortable_4=true&mDataProp_5=5&sSearch_5=&bRegex_5=false&bSearchable_5=true&bSortable_5=true&mDataProp_6=6&sSearch_6=&bRegex_6=false&bSearchable_6=true&bSortable_6=true&mDataProp_7=7&sSearch_7=&bRegex_7=false&bSearchable_7=true&bSortable_7=true&mDataProp_8=8&sSearch_8=&bRegex_8=false&bSearchable_8=true&bSortable_8=false&sSearch=&bRegex=false&iSortCol_0=0&sSortDir_0=desc&iSortingCols=1&_=1757348638167"
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7761576669  # apna Telegram numeric ID
DEVELOPER_ID = "@hiden_25"  # Replace with your Telegram ID
CHANNEL_LINK = "https://t.me/freeotpss" # Replace with your Telegram channel ID

# Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "http://217.23.5.21/ints/login"
}
AJAX_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "http://217.23.5.21/ints/agent/SMSCDRStats"
}

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot
bot = telegram.Bot(token=BOT_TOKEN)

# Session and state
session = requests.Session()
seen = set()
CHAT_IDS = set()
CHAT_IDS.add("-1001926462756")
otp_count = 0
last_otp_time = "N/A"

# Login function
def login():
    res = session.get("http://217.23.5.21/ints/login", headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    captcha_text = None
    for string in soup.stripped_strings:
        if "What is" in string and "+" in string:
            captcha_text = string.strip()
            break

    match = re.search(r"What is\s*(\d+)\s*\+\s*(\d+)", captcha_text or "")
    if not match:
        print("❌ Captcha not found.")
        return False

    a, b = int(match.group(1)), int(match.group(2))
    captcha_answer = str(a + b)
    print(f"✅ Captcha solved: {a} + {b} = {captcha_answer}")

    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "capt": captcha_answer
    }

    res = session.post(LOGIN_URL, data=payload, headers=HEADERS)
    if "SMSCDRStats" not in res.text:
        print("❌ Login failed.")
        return False

    print("✅ Logged in successfully.")
    return True

# Mask phone number (show first 4 and last 3 digits)
def mask_number(number):
    if len(number) <= 6:
        return number  # agar chhota number hai to mask na karo
    # sirf middle 3 digits mask honge
    mid = len(number) // 2
    return number[:mid-1] + "***" + number[mid+2:]

# Send message to Telegram with inline buttons
async def send_telegram_message(time_, country, number, sender, message):
    flag = country_to_flag(country)
    formatted = (
    f"<blockquote>{flag}<b> {country} {sender} OTP Received</b> ✨</blockquote>\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    f"<blockquote>📲 <b>Number:</b> <code>{mask_number(number)}</code></blockquote>\n"
    f"<blockquote>🗺️ <b>Country:</b> <code>{country}{flag} </code></blockquote>\n"
    f"<blockquote>📮 <b>Service:</b> <code>{sender}</code></blockquote>\n"
    f"<blockquote>📨 <b>Message:</b></blockquote>\n"
    f"<blockquote><code>{html.escape(message)}</code></blockquote>\n\n"
    "━━Be Active━━\n"
    "<blockquote>⚡ Powered by\n<a href='https://t.me/hiden_25'>VASU</a> ✨</blockquote>\n\n"
    "<blockquote>Designed By <a href='https://t.me/freeotpss'>Free OTPs</a> 🔥</blockquote>"
)

    keyboard = [
        [
            InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{DEVELOPER_ID.lstrip('@')}"),
            InlineKeyboardButton("📢 Channel", url=f"{CHANNEL_LINK}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Add 0.5s gap before sending any message
    await asyncio.sleep(1)

    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=formatted,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Failed to send to {chat_id}: {e}")


# Fetch OTPs and send to Telegram
# --- OTP Loop ---
def fetch_otp_loop():
    print("\n🔄 Starting OTP fetch loop...\n")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            res = session.get(XHR_URL, headers=AJAX_HEADERS)
            data = res.json()
            otps = data.get("aaData", [])
            otps = [row for row in otps if isinstance(row[0], str) and ":" in row[0]]

            new_found = False
            with open("otp_logs.txt", "a", encoding="utf-8") as f:
                for row in otps:
                    time_ = row[0]
                    operator = row[1].split(" ")[0]
                    number = row[2]
                    sender = row[3]
                    message = row[5]

                    hash_id = hashlib.md5((number + time_ + message).encode()).hexdigest()
                    if hash_id in seen:
                        continue
                    seen.add(hash_id)
                    new_found = True

                    # Save log
                    log_formatted = (
                        f"📱 Number: {number}\n"
                        f"🏷️ Sender ID: {sender}\n"
                        f"💬 Message: {message}\n"
                        f"{'-'*60}"
                    )
                    print(log_formatted)
                    f.write(log_formatted + "\n")

                    # ✅ Send OTP to groups
                    loop.run_until_complete(send_telegram_message(time_, operator, number, sender, message))

                    # ✅ Update status tracking
                    global otp_count, last_otp_time
                    otp_count += 1
                    last_otp_time = time_

            if not new_found:
                print("⏳ No new OTPs.")
        except Exception as e:
            print("❌ Error fetching OTPs:", e)

        time.sleep(2)
# /start ka handler
async def start_command(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is Active & Running! Contact If Any Problem @hiden_25")

# Add group command
async def addgroup(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized.")

    if not context.args:
        return await update.message.reply_text("Usage: /addgroup <chat_id>")

    chat_id = context.args[0]
    CHAT_IDS.add(chat_id)
    await update.message.reply_text(f"✅ Group {chat_id} added successfully.")

# Remove group command
async def removegroup(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized.")

    if not context.args:
        return await update.message.reply_text("Usage: /removegroup <chat_id>")

    chat_id = context.args[0]
    if chat_id in CHAT_IDS:
        CHAT_IDS.remove(chat_id)
        await update.message.reply_text(f"✅ Group {chat_id} removed successfully.")
    else:
        await update.message.reply_text("⚠️ Group not found.")

# Status command
async def status(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized.")

    msg = (
        f"📊 <b>Bot Status</b>\n\n"
        f"✅ Total OTPs: <code>{otp_count}</code>\n"
        f"⏱️ Last OTP Time: <code>{last_otp_time}</code>\n"
        f"📌 Forwarding Groups: {', '.join(CHAT_IDS) if CHAT_IDS else 'None'}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

def start_telegram_listener():
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start_command))
    tg_app.add_handler(CommandHandler("addgroup", addgroup))
    tg_app.add_handler(CommandHandler("removegroup", removegroup))
    tg_app.add_handler(CommandHandler("status", status))
    tg_app.run_polling()

# Health check endpoint
@app.route('/health')
def health():
    return Response("OK", status=200)
@app.route("/")
def root():
    logger.info("Root endpoint requested")
    return Response("OK", status=200)
    
# Start the OTP fetching loop in a separate thread
def start_otp_loop():
    while True:
        if login():
            print("✅ Login successful, starting OTP loop...")
            fetch_otp_loop()
            break   # loop se nikal jao agar sab sahi ho gaya
        else:
            print("⚠️ Login failed, retrying in 5 seconds...")
            time.sleep(5)

if __name__ == '__main__':
    # OTP loop background me
    otp_thread = threading.Thread(target=start_otp_loop, daemon=True)
    otp_thread.start()

    # Flask background me
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True)
    flask_thread.start()

    # Telegram bot MAIN thread me
    start_telegram_listener()
