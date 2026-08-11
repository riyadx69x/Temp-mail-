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
    await create_or_refresh_account(update, context, user_id, is_new=True)

async def create_or_refresh_account(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, is_new=False, old_email=None):
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

        requests.post(
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

            response_text = ""
            if not is_new and old_email:
                response_text += f"Your old email address has been successfully deleted\n\n"
            
            response_text += f"New temporary email address:\n\n`{email}`"

            keyboard = [[InlineKeyboardButton("Open in Browser ➡️", url=f"https://mail.tm/inbox")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                response_text, 
                parse_mode="Markdown", 
                reply_markup=reply_markup
            )
            # কিবোর্ড বাটনগুলো নিচে এক্টিভ রাখার জন্য
            await update.message.reply_text("Select an option below:", reply_markup=get_main_keyboard())

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def check_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await create_or_refresh_account(update, context, user_id, is_new=True)
        return

    token = user_sessions[user_id]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    msg_res = requests.get(f"{BASE_URL}/messages", headers=headers)

    if msg_res.status_code == 200:
        messages = msg_res.json().get("hydra:member", [])
        if not messages:
            await update.message.reply_text("📭 Inbox is empty. No new messages yet.", reply_markup=get_main_keyboard())
        else:
            for msg in messages:
                msg_id = msg['id']
                detail_res = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)
                detail = detail_res.json()
                
                sender = detail.get('from', {}).get('address', 'Unknown')
                subject = detail.get('subject', 'No Subject')
                text_body = detail.get('text', '') or detail.get('intro', '')
                
                # স্ক্রিনশটের ডিজাইনের সাথে মিলিয়ে মেসেজ ফরম্যাট
                formatted_msg = (
                    f"New email message\n\n"
                    f"From: \"{sender.split('@')[0]}\" <{sender}>\n\n"
                    f"Subject: {subject}\n\n"
                    f"`{text_body}`"
                )
                
                keyboard = [[InlineKeyboardButton("Open in Browser ➡️", url=f"https://mail.tm/inbox")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    formatted_msg, 
                    parse_mode="Markdown", 
                    reply_markup=reply_markup
                )
    else:
        await update.message.reply_text("❌ Error checking inbox.", reply_markup=get_main_keyboard())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if text == "➕ Generate New / Delete":
        old_email = None
        if user_id in user_sessions:
            old_email = user_sessions[user_id]["email"]
            del user_sessions[user_id]
        await create_or_refresh_account(update, context, user_id, is_new=False, old_email=old_email)
    elif text == "🔄 Refresh Inbox":
        await check_inbox(update, context)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_buttons))
    app.run_polling()
