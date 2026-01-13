import logging
import html
import re
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatAction

# --- KONFIGURASI ---
TOKEN = '7887862356:AAHTa0kxaOAcDh7kAB7wOJl-4nD5oWLjtHE'
CHANNEL_ID = '@GALLERY_TPV'
BOT_USERNAME = 'agimenfessbot'
NAMA_BOT = 'MENFESSKU'
OWNER_ID = 7411619973  # ID Owner Anda

# File penyimpanan agar data tidak hilang saat restart
BAN_FILE = "banned_users.txt"
REGEX_FILE = "regex_filters.txt"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- FUNGSI DATABASE SEDERHANA ---
def load_data(file_name):
    if not os.path.exists(file_name): return []
    with open(file_name, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def save_data(file_name, data):
    with open(file_name, "w") as f:
        for item in data: f.write(f"{item}\n")

banned_users = set(load_data(BAN_FILE))
regex_filters = load_data(REGEX_FILE)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in banned_users:
        await update.message.reply_text("🚫 Anda telah diblokir dari bot ini.")
        return

    keyboard = [['👤 Kirim Anonim', '📝 Tampilkan Nama']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    welcome_text = (
        f"✨ <b>Selamat Datang di {NAMA_BOT}</b> ✨\n\n"
        "Silakan pilih identitas pengiriman kamu terlebih dahulu:"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# --- FITUR OWNER: MANAJEMEN BAN & REGEX ---
async def owner_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return

    text = update.message.text
    cmd = text.split(maxsplit=1)
    
    if text.startswith("/addregex") and len(cmd) > 1:
        pattern = cmd[1]
        try:
            re.compile(pattern)
            regex_filters.append(pattern)
            save_data(REGEX_FILE, regex_filters)
            await update.message.reply_text(f"✅ Regex ditambahkan: <code>{pattern}</code>", parse_mode=ParseMode.HTML)
        except: await update.message.reply_text("❌ Regex tidak valid.")

    elif text.startswith("/listregex"):
        msg = "🚫 <b>Daftar Regex:</b>\n" + "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(regex_filters)])
        await update.message.reply_text(msg if regex_filters else "Daftar kosong.", parse_mode=ParseMode.HTML)

    elif text.startswith("/delregex") and len(cmd) > 1:
        try:
            idx = int(cmd[1]) - 1
            removed = regex_filters.pop(idx)
            save_data(REGEX_FILE, regex_filters)
            await update.message.reply_text(f"🗑️ Dihapus: <code>{removed}</code>", parse_mode=ParseMode.HTML)
        except: await update.message.reply_text("Nomor salah.")

    elif text.startswith("/ban") and len(cmd) > 1:
        target = cmd[1]
        banned_users.add(target)
        save_data(BAN_FILE, list(banned_users))
        await update.message.reply_text(f"🔨 User <code>{target}</code> di-ban.")

    elif text.startswith("/unban") and len(cmd) > 1:
        target = cmd[1]
        banned_users.discard(target)
        save_data(BAN_FILE, list(banned_users))
        await update.message.reply_text(f"🔓 User <code>{target}</code> di-unban.")

# --- HANDLER UTAMA ---
async def handle_menfess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = str(msg.from_user.id)
    
    if user_id in banned_users: return

    keyboard = [['👤 Kirim Anonim', '📝 Tampilkan Nama']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    if msg.text in ['👤 Kirim Anonim', '📝 Tampilkan Nama']:
        context.user_data['mode'] = msg.text
        await msg.reply_text(f"✅ Mode: <b>{msg.text}</b>\nKirim pesan teks kamu:", reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.HTML)
        return

    mode = context.user_data.get('mode')
    if not mode:
        await msg.reply_text("⚠️ Pilih identitas dulu:", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return

    if not msg.text:
        await msg.reply_text("⚠️ Hanya teks yang diizinkan.", reply_markup=reply_markup)
        return

    # Filter Regex
    for pattern in regex_filters:
        if re.search(pattern, msg.text, re.IGNORECASE):
            await msg.reply_text("🚫 Pesan mengandung pola dilarang!", reply_markup=reply_markup)
            return

    # Kirim ke Channel
    sender = f'👤 <b>From: <a href="tg://user?id={user_id}">{html.escape(msg.from_user.full_name)}</a></b>' if mode == '📝 Tampilkan Nama' else "👤 <b>From: Anonim</b>"
    header = "━━━━━━━━━━━━━━━━━━━━\n💌 <b>NEW MENFESS!</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    footer = f"\n\n{sender}\n📅 <i>Sent via</i> @{BOT_USERNAME}\n━━━━━━━━━━━━━━━━━━━━"
    
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=f"{header}“ {html.escape(msg.text)} ”{footer}", parse_mode=ParseMode.HTML)
        
        # LOG ADMIN
        log_text = f"🚨 <b>LOG:</b>\nID: <code>{user_id}</code>\nUser: {html.escape(msg.from_user.full_name)}\nPesan: {html.escape(msg.text)}"
        await context.bot.send_message(chat_id=OWNER_ID, text=log_text, parse_mode=ParseMode.HTML)

        context.user_data.clear()
        await msg.reply_text(f"✅ <b>Terkirim!</b> Cek di {CHANNEL_ID}\nIngin kirim lagi? Pilih identitas:", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"❌ Error: {e}", reply_markup=reply_markup)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(["addregex", "listregex", "delregex", "ban", "unban"], owner_commands))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_menfess))
    print("--- BOT MENFESS PRO 2026 ACTIVE ---")
    app.run_polling(drop_pending_updates=True)

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is Running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

if __name__ == '__main__':
    keep_alive()  # Menjalankan server web kecil agar Render tidak mematikan bot
    main()        # Menjalankan bot Telegram

