import random
import string
import requests
from telegram import ReplyKeyboardMarkup, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configuration
BOT_TOKEN = "8688225861:AAHT-8_7O0PDRjy3cWTEp6gfW3b-vpb-CSA"
BASE_URL = "https://api.mail.tm"
user_sessions = {}

def generate_random_string(length=8):
    letters = string.ascii_lowercase + string.digits
    return "".join(random.choice(letters) for i in range(length))

def get_main_keyboard():
    keyboard = [["➕ Generate New / Delete", "🔄 Refresh Inbox"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await create_or_refresh_account(update, context, user_id)

async def create_or_refresh_account(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        domain_res = requests.get(f"{BASE_URL}/domains")
        if domain_res.status_code != 200:
            await update.message.reply_text("❌ Failed to fetch domains.")
            return

        domains = domain_res.json().get("hydra:member", [])
        if not domains:
            await update.message.reply_text("❌ No domains available.")
            return

        domain = domains[0]["domain"]
        username = f"user_{generate_random_string(6)}"
        email = f"{username}@{domain}"
        password = generate_random_string(10)

        acc_res = requests.post(
            f"{BASE_URL}/accounts",
            json={"address": email, "password": password},
            headers={"Content-Type": "application/json"},
        )
        
        token_res = requests.post(
            f"{BASE_URL}/token",
            json={"address": email, "password": password},
            headers={"Content-Type": "application/json"},
        )
        
        if token_res.status_code == 200:
            token = token_res.json().get("token")
            user_sessions[user_id] = {"email": email, "token": token}

            keyboard = [[InlineKeyboardButton("Open in Browser ➡️", url=f"https://mail.tm/inbox")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"Your temporary email address:\n\n`{email}`", 
                parse_mode="Markdown", 
                reply_markup=reply_markup
            )
            await update.message.reply_text("Use the buttons below:", reply_markup=get_main_keyboard())

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def check_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await create_or_refresh_account(update, context, user_id)
        return

    token = user_sessions[user_id]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    msg_res = requests.get(f"{BASE_URL}/messages", headers=headers)

    if msg_res.status_code == 200:
        messages = msg_res.json().get("hydra:member", [])
        if not messages:
            await update.message.reply_text("📭 Inbox is empty.")
        else:
            for msg in messages:
                msg_id = msg['id']
                detail_res = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)
                detail = detail_res.json()
                
                text = f"New email message\n\nFrom: {detail.get('from', {}).get('address')}\nSubject: {detail.get('subject')}\n\n{detail.get('text', '')}"
                
                keyboard = [[InlineKeyboardButton("Open in Browser ➡️", url=f"https://mail.tm/inbox")]]
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ Error checking inbox.")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if text == "➕ Generate New / Delete":
        if user_id in user_sessions:
            await update.message.reply_text("Your old email address has been successfully deleted.")
        await create_or_refresh_account(update, context, user_id)
    elif text == "🔄 Refresh Inbox":
        await check_inbox(update, context)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_buttons))
    app.run_polling()
