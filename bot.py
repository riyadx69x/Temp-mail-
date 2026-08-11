import random
import string
import re
import asyncio
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
seen_messages = set()

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

            # শুধু ইমেইল এড্রেসটি দেখাবে, কোনো বাড়তি মেসেজ থাকবে না
            response_text = f"Your temporary email address:\n\n`{email}`"

            keyboard = [[InlineKeyboardButton("Open in Browser ➡️", url=f"https://mail.tm/inbox")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                response_text, 
                parse_mode="Markdown", 
                reply_markup=reply_markup,
                reply_to_message_handler=get_main_keyboard()
            )
            # কিবোর্ড বাটন যুক্ত করে পাঠানো
            await update.message.reply_text("👇", reply_markup=get_main_keyboard())

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def check_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE, manual=True):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        if manual:
            await create_or_refresh_account(update, context, user_id)
        return

    token = user_sessions[user_id]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    msg_res = requests.get(f"{BASE_URL}/messages", headers=headers)

    if msg_res.status_code == 200:
        messages = msg_res.json().get("hydra:member", [])
        if not messages:
            if manual:
                await update.message.reply_text("📭 Inbox is empty. No new messages yet.", reply_markup=get_main_keyboard())
        else:
            for msg in messages:
                msg_id = msg['id']
                if msg_id in seen_messages:
                    continue
                
                seen_messages.add(msg_id)
                detail_res = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)
                detail = detail_res.json()
                
                sender = detail.get('from', {}).get('address', 'Unknown')
                subject = detail.get('subject', 'No Subject')
                text_body = detail.get('text', '') or detail.get('intro', '')
                
                full_text = f"{subject} {text_body}"
                code_match = re.search(r'\b\d{4,6}\b', full_text)
                
                if code_match:
                    otp_code = code_match.group(0)
                    code_display = f"`{otp_code}`"
                else:
                    code_display = f"`{text_body[:50]}`"

                # স্ক্রিনশটের হুবহু লেআউট অনুযায়ী ডিজাইন
                formatted_msg = (
                    f"New email message\n\n"
                    f"From: \"{sender.split('@')[0]}\" <{sender}>\n\n"
                    f"Subject: {subject}\n\n"
                    f"{code_display}"
                )
                
                keyboard = [[InlineKeyboardButton("Open in Browser ➡️", url=f"https://mail.tm/inbox")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # কার কাছে মেসেজ পাঠাতে হবে তা নিশ্চিত করা
                chat_id = update.effective_chat.id if update else user_id
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=formatted_msg,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )

async def background_inbox_checker(context: ContextTypes.DEFAULT_TYPE):
    for user_id in list(user_sessions.keys()):
        class DummyUpdate:
            pass
        dummy = DummyUpdate()
        dummy.effective_user = type('obj', (object,), {'id': user_id})()
        await check_inbox(dummy, context, manual=False)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if text == "➕ Generate New / Delete":
        if user_id in user_sessions:
            del user_sessions[user_id]
        await create_or_refresh_account(update, context, user_id)
    elif text == "🔄 Refresh Inbox":
        await check_inbox(update, context, manual=True)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.job_queue.run_repeating(background_inbox_checker, interval=3, first=3)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_buttons))
    app.run_polling()
