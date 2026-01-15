import logging, html, os, json, sys, subprocess, asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

# --- 1. KONFIGURASI UTAMA ---
TOKEN = os.getenv("BOT_TOKEN", '8412972026:AAHkUMziUGDo__JGGoQUf8bKKnazX4P-sV8')
DEFAULT_CHANNEL = os.getenv("CH_ID", '@GALLERY_TPV')
MAIN_OWNER_ID = 7411619973  
OWNER_ID = int(os.getenv("OWN_ID", MAIN_OWNER_ID))

IS_CLONE = os.getenv("IS_CLONE", "False") == "True"
suffix = f"_{OWNER_ID}" if IS_CLONE else ""

USER_DATA_FILE = f"user_stats{suffix}.json"
CONFIG_FILE = f"bot_config{suffix}.json"
USERS_LIST_FILE = f"all_users{suffix}.json"
BAN_FILE = f"banned_users{suffix}.json" # Database Ban
CLONE_DB = "permanent_clones.json"

DEFAULT_TEMPLATE = "✨ <b>𝐍𝐄𝐖 𝐌𝐄𝐍𝐅𝐄𝐒𝐒!</b> ✨\n\n{TEXT}\n\n👤 <b>Sender:</b> {SENDER}"

# --- KEYBOARD ---
MAIN_KEYBOARD = ReplyKeyboardMarkup([['👤 Kirim Anonim', '📝 Tampilkan Nama'], ['💳 Isi Kuota (Bayar)', '📊 Cek Kuota']], resize_keyboard=True)
OWNER_KEYBOARD = ReplyKeyboardMarkup([['🤖 CLONE', '📋 LIST CLONE'], ['⚙️ CUSTOM POST', '📢 BROADCAST'], ['🔓 MODE GRATIS', '🔒 MODE BAYAR'], ['👤 MENU USER']], resize_keyboard=True)
CLONE_ADMIN_KEYBOARD = ReplyKeyboardMarkup([['⚙️ CUSTOM POST', '📢 BROADCAST'], ['🔓 MODE GRATIS', '🔒 MODE BAYAR'], ['👤 MENU USER']], resize_keyboard=True)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 2. DATABASE HELPER ---
def load_json(file_name):
    if not os.path.exists(file_name):
        default = [] if any(x in file_name for x in ["all_users", "clones", "permanent", "banned"]) else {}
        with open(file_name, "w") as f: json.dump(default, f)
        return default
    with open(file_name, "r") as f:
        try:
            data = json.load(f)
            return data if data is not None else []
        except: return []

def save_json(file_name, data):
    with open(file_name, "w") as f: json.dump(data, f, indent=4)

def is_banned(uid):
    return str(uid) in load_json(BAN_FILE)

# --- 3. CALLBACK HANDLER (MODIFIKASI: TAMBAH BAN/UNBAN) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID: return
    data = query.data

    if data.startswith("ban_"):
        uid = data.split("_")[1]
        banned = load_json(BAN_FILE)
        if uid not in banned:
            banned.append(uid)
            save_json(BAN_FILE, banned)
        await query.answer("User Berhasil di Ban!")
        await query.edit_message_caption(caption=query.message.caption + "\n\n🚫 <b>STATUS: BANNED</b>", parse_mode=ParseMode.HTML)

    elif data.startswith("unban_"):
        uid = data.split("_")[1]
        banned = load_json(BAN_FILE)
        if uid in banned:
            banned.remove(uid)
            save_json(BAN_FILE, banned)
        await query.answer("Ban User Dicabut!")
        await query.edit_message_caption(caption=query.message.caption + "\n\n✅ <b>STATUS: AKTIF</b>", parse_mode=ParseMode.HTML)

    elif data.startswith("delclone_"):
        try:
            # Perbaikan: ambil index dengan benar
            parts = data.split("_")
            idx = int(parts[1]) 
            clones = load_json(CLONE_DB)
            if 0 <= idx < len(clones):
                removed = clones.pop(idx)
                save_json(CLONE_DB, clones)
                # Gunakan .get untuk menghindari KeyError
                nama_bot = removed.get('user', 'Bot Clone')
                await query.edit_message_text(f"✅ {nama_bot} berhasil dihapus dari database.")
            else:
                await query.answer("Gagal: Index tidak ditemukan")
        except Exception as e:
            await query.answer(f"Error: {e}")

    elif data.startswith("count_"):
        _, tid, val = data.split("_")
        val = max(1, int(val))
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➖", callback_data=f"count_{tid}_{val-1}"), InlineKeyboardButton(f"💎 {val}", callback_data="n"), InlineKeyboardButton("➕", callback_data=f"count_{tid}_{val+1}")], [InlineKeyboardButton("✅ KONFIRMASI", callback_data=f"acc_{tid}_{val}")]])
        await query.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("acc_"):
        _, tid, val = data.split("_")
        db_user = load_json(USER_DATA_FILE)
        if tid not in db_user: db_user[tid] = {"kuota": 0}
        db_user[tid]["kuota"] += int(val)
        save_json(USER_DATA_FILE, db_user)
        await query.edit_message_caption(caption=query.message.caption + f"\n\n✅ <b>BERHASIL +{val}</b>")
        try: await context.bot.send_message(tid, f"✅ Pembayaran diterima! +{val} kuota ditambahkan.")
        except: pass

    elif data == "cp_tpl":
        context.user_data['edit_mode'] = 'template'
        await query.message.reply_text("📝 Kirim template baru. Gunakan {TEXT} & {SENDER}.")
    elif data == "cp_ch":
        context.user_data['edit_mode'] = 'channel'
        await query.message.reply_text("📢 Kirim username channel baru (@Channel).")
    
    await query.answer()


# --- 4. HANDLING PESAN ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    uid_int = update.effective_user.id
    uid = str(uid_int); msg = update.message; text = msg.text or msg.caption or ""
    
    if is_banned(uid_int): return 
    # --- LOGIKA TERIMA FOTO PEMBAYARAN ---
    if 'wait_pay' in context.user_data and msg.photo:
        del context.user_data['wait_pay']
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➖", callback_data=f"count_{uid}_4"), InlineKeyboardButton("💎 5", callback_data="n"), InlineKeyboardButton("➕", callback_data=f"count_{uid}_6")], [InlineKeyboardButton("✅ KONFIRMASI", callback_data=f"acc_{uid}_5")]])
        await context.bot.send_photo(OWNER_ID, photo=msg.photo[-1].file_id, caption=f"💰 Bukti Bayar: {uid}", reply_markup=kb)
        return await msg.reply_text("✅ Terkirim ke admin.")
    if msg.photo and uid_int != OWNER_ID:
        caption_owner = (
            f"💳 <b>BUKTI PEMBAYARAN BARU</b>\n\n"
            f"👤 Dari: {html.escape(update.effective_user.first_name)}\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"💡 Gunakan tombol untuk tambah kuota."
        )
        # Tombol penyesuaian kuota (Default mulai dari 5)
        kb_owner = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➖", callback_data=f"count_{uid}_4"),
                InlineKeyboardButton("💎 5", callback_data="n"),
                InlineKeyboardButton("➕", callback_data=f"count_{uid}_6")
            ],
            [InlineKeyboardButton("✅ KONFIRMASI", callback_data=f"acc_{uid}_5")]
        ])
        
        await context.bot.send_photo(
            chat_id=OWNER_ID,
            photo=msg.photo[-1].file_id,
            caption=caption_owner,
            reply_markup=kb_owner,
            parse_mode=ParseMode.HTML
        )
        return await msg.reply_text("✅ Bukti pembayaran telah terkirim ke owner. Mohon tunggu konfirmasi.")

    # --- 1. ROUTING TOMBOL (CEK TOMBOL DULU) ---
    if uid_int == OWNER_ID:
        if text == '🤖 CLONE':
            context.user_data.clear() # Bersihkan state lain
            context.user_data['waiting_clone'] = True
            return await msg.reply_text("🤖 <b>MODE CLONING AKTIF</b>\n\nSilakan kirimkan <b>Token Bot</b> baru dari @BotFather.", parse_mode=ParseMode.HTML)
        
        if text == '📋 LIST CLONE':
            clones = load_json(CLONE_DB)
            if not clones: return await msg.reply_text("Belum ada bot yang dikloning.")
            kb = [[InlineKeyboardButton(f"🗑 Hapus Clone {i+1}", callback_data=f"delclone_{i}")] for i, c in enumerate(clones)]
            return await msg.reply_text("📋 <b>DAFTAR CLONE AKTIF</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

        if text == '⚙️ CUSTOM POST':
            cfg = load_json(CONFIG_FILE)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Template", callback_data="cp_tpl"), InlineKeyboardButton("📢 Channel", callback_data="cp_ch")]])
            return await msg.reply_text(f"⚙️ <b>CUSTOM POST</b>\n\nTarget: {cfg.get('target_channel', DEFAULT_CHANNEL)}\nTemplate:\n<code>{html.escape(cfg.get('post_template', DEFAULT_TEMPLATE))}</code>", reply_markup=kb, parse_mode=ParseMode.HTML)

        if text == '📢 BROADCAST':
            context.user_data.clear()
            context.user_data['waiting_bc'] = True
            return await msg.reply_text("📢 Silakan kirim pesan yang ingin di-broadcast ke semua user:")

        if text == '🔓 MODE GRATIS':
            cfg = load_json(CONFIG_FILE); cfg["gratis"] = True; save_json(CONFIG_FILE, cfg)
            return await msg.reply_text("✅ Mode GRATIS aktif!")

        if text == '🔒 MODE BAYAR':
            cfg = load_json(CONFIG_FILE); cfg["gratis"] = False; save_json(CONFIG_FILE, cfg)
            return await msg.reply_text("✅ Mode BERBAYAR aktif!")

        if text == '👤 MENU USER':
            return await msg.reply_text("Menu User Aktif.", reply_markup=MAIN_KEYBOARD)
    # --- TOMBOL USER (TAMBAHKAN INI) ---
    if text == '👤 Kirim Anonim':
        context.user_data['mode'] = 'anonim'
        return await msg.reply_text("Silakan kirim pesan Anda. Identitas Anda akan disembunyikan.")

    if text == '📝 Tampilkan Nama':
        context.user_data['mode'] = 'nama'
        return await msg.reply_text("Silakan kirim pesan Anda. Nama Anda akan ditampilkan di postingan.")

    if text == '💳 Isi Kuota (Bayar)':
        return await msg.reply_text(
            "💳 <b>CARA ISI KUOTA</b>\n\n"
            "1. Silakan transfer ke rekening: <b>[ISI REKENING ANDA]</b>\n"
            "2. Kirim <b>Foto Bukti Transfer</b> ke bot ini.\n"
            "3. Admin akan mengonfirmasi dan kuota akan masuk.",
            parse_mode=ParseMode.HTML
        )

    # --- 2. LOGIKA INPUT (CAPTURE DATA SETELAH TOMBOL DIKLIK) ---
    
    # Capture Token Clone
    if uid_int == OWNER_ID and context.user_data.get('waiting_clone'):
        token_input = text.strip()
        context.user_data.pop('waiting_clone')
        try:
            env = os.environ.copy()
            env["BOT_TOKEN"] = token_input
            env["IS_CLONE"] = "True"
            env["OWN_ID"] = str(uid_int)
            subprocess.Popen([sys.executable, sys.argv[0]], env=env)
            clones = load_json(CLONE_DB); clones.append({"token": token_input, "owner": uid_int}); save_json(CLONE_DB, clones)
            return await msg.reply_text("✅ Clone Berhasil dihidupkan!")
        except Exception as e:
            return await msg.reply_text(f"❌ Gagal: {e}")

    # Capture Broadcast
    if uid_int == OWNER_ID and context.user_data.get('waiting_bc'):
        context.user_data.pop('waiting_bc')
        all_users = load_json(USERS_LIST_FILE)
        count = 0
        for u in all_users:
            try:
                await context.bot.send_message(u, text)
                count += 1
                await asyncio.sleep(0.05)
            except: continue
        return await msg.reply_text(f"✅ Berhasil broadcast ke {count} user.")

    # Capture Edit Template/Channel
    if uid_int == OWNER_ID and 'edit_mode' in context.user_data:
        mode = context.user_data.pop('edit_mode')
        cfg = load_json(CONFIG_FILE)
        if mode == 'template': cfg["post_template"] = text; await msg.reply_text("✅ Template diperbarui!")
        elif mode == 'channel': cfg["target_channel"] = text; await msg.reply_text(f"✅ Target: {text}")
        save_json(CONFIG_FILE, cfg); return

    # --- 3. USER LOGIC (CEK KUOTA, DLL) ---
    if text == '📊 Cek Kuota':
        db_user = load_json(USER_DATA_FILE)
        return await msg.reply_text(f"📊 Kuota: {db_user.get(uid, {}).get('kuota', 0)}")
    
    # ... (Sisa logika Isi Kuota dan Kirim Menfess Anda di bawah sini) ...

    # --- PENGIRIMAN MENFESS & LOG KE OWNER ---
    if 'mode' in context.user_data:
        db = load_json(USER_DATA_FILE)
        if uid_int != OWNER_ID and not load_json(CONFIG_FILE).get("gratis", False) and db.get(uid, {}).get("kuota", 0) <= 0:
            return await msg.reply_text("❌ Kuota habis!", reply_markup=MAIN_KEYBOARD)
        
        mode = context.user_data.pop('mode')
        full_name = html.escape(update.effective_user.full_name)
        sender = "Anonim 👤" if mode == "anon" else f"<a href='tg://user?id={uid_int}'>{full_name}</a> 📝"

        cfg = load_json(CONFIG_FILE)
        final_text = cfg.get("post_template", DEFAULT_TEMPLATE).replace("{TEXT}", text).replace("{SENDER}", sender)
        
        try:
            target = cfg.get("target_channel", DEFAULT_CHANNEL)
            if msg.photo: snt = await context.bot.send_photo(target, msg.photo[-1].file_id, caption=final_text, parse_mode=ParseMode.HTML)
            else: snt = await context.bot.send_message(target, final_text, parse_mode=ParseMode.HTML)
            
            if uid_int != OWNER_ID and not cfg.get("gratis", False):
                db[uid]["kuota"] -= 1; save_json(USER_DATA_FILE, db)
            
            # --- LOG KE OWNER BOT ---
            log_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚫 BAN USER", callback_data=f"ban_{uid}"), InlineKeyboardButton("✅ UNBAN", callback_data=f"unban_{uid}")]])
            log_text = f"📩 <b>LOG MENFESS BARU</b>\n\n<b>Dari:</b> {full_name} (<code>{uid}</code>)\n<b>Isi:</b>\n{html.escape(text)}"
            if msg.photo: await context.bot.send_photo(OWNER_ID, photo=msg.photo[-1].file_id, caption=log_text, reply_markup=log_kb, parse_mode=ParseMode.HTML)
            else: await context.bot.send_message(OWNER_ID, log_text, reply_markup=log_kb, parse_mode=ParseMode.HTML)
            
            link = f"t.me/{target.replace('@','')}/{snt.message_id}"
            await msg.reply_text("✅ Terkirim!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Lihat Postingan ↗️", url=link)]]))
            await msg.reply_text("Menu:", reply_markup=MAIN_KEYBOARD)
        except Exception as e: await msg.reply_text(f"❌ Gagal: {e}")

# --- 5. RUNNER ---
async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    text = " ".join(context.args)
    if not text: return await update.message.reply_text("❌ `/bc pesan`")
    users = load_json(USERS_LIST_FILE)
    success = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 <b>INFO ADMIN</b>\n\n{text}", parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except: continue
    await update.message.reply_text(f"✅ Selesai! Berhasil: {success}")

async def clone_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MAIN_OWNER_ID or IS_CLONE: return
    if len(context.args) < 4: return
    t, u, c, o = context.args, context.args, context.args, context.args
    db = load_json(CLONE_DB); db.append({"token": t, "user": u, "ch": c, "own": int(o)}); save_json(CLONE_DB, db)
    subprocess.Popen([sys.executable, __file__], env={**os.environ, "BOT_TOKEN": t, "CH_ID": c, "OWN_ID": str(o), "IS_CLONE": "True"})
    await update.message.reply_text(f"✅ Bot @{u} Aktif!")
    # Logika pengiriman pesan ke channel
    list_tombol = ['👤 Kirim Anonim', '📝 Tampilkan Nama', '💳 Isi Kuota (Bayar)', '📊 Cek Kuota']
    
    if not text.startswith('/') and text not in list_tombol:
        db_user = load_json(USER_DATA_FILE)
        kuota = db_user.get(uid, {}).get('kuota', 0)
        
        if kuota > 0:
            # Kirim ke channel
            await context.bot.send_message(chat_id=DEFAULT_CHANNEL, text=f"✨ <b>MENFESS BARU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            # Kurangi kuota
            db_user[uid]['kuota'] -= 1
            save_json(USER_DATA_FILE, db_user)
            await msg.reply_text(f"✅ Terkirim! Sisa kuota: {db_user[uid]['kuota']}")
        else:
            await msg.reply_text("❌ Kuota habis, silakan isi ulang.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid_int = update.effective_user.id
    # Auto-save user list untuk broadcast
    users = load_json(USERS_LIST_FILE)
    if str(uid_int) not in users: users.append(str(uid_int)); save_json(USERS_LIST_FILE, users)
    
    db = load_json(USER_DATA_FILE)
    if str(uid_int) not in db: db[str(uid_int)] = {"kuota": 0}; save_json(USER_DATA_FILE, db)
    kb = OWNER_KEYBOARD if (uid_int == MAIN_OWNER_ID and not IS_CLONE) else (CLONE_ADMIN_KEYBOARD if uid_int == OWNER_ID else MAIN_KEYBOARD)
    await update.message.reply_text(f"👋 Halo!\nID: {uid_int}", reply_markup=kb)
    # Logika jika user mengirim pesan (bukan menekan tombol)
        # Proses pengiriman ke channel @GALLERY_TPV di sini
        # Cek kuota, ambil template, lalu send_message ke channel.
     # Pastikan bagian ini berada di paling bawah fungsi handle_message
    list_tombol = ['👤 Kirim Anonim', '📝 Tampilkan Nama', '💳 Isi Kuota (Bayar)', '📊 Cek Kuota']
    
    if not text.startswith('/') and text not in list_tombol:
        db_user = load_json(USER_DATA_FILE)
        kuota = db_user.get(uid, {}).get('kuota', 0)
        
        if kuota > 0:
            # Kirim ke channel
            await context.bot.send_message(chat_id=DEFAULT_CHANNEL, text=f"✨ <b>MENFESS BARU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            db_user[uid]['kuota'] -= 1
            save_json(USER_DATA_FILE, db_user)
            await msg.reply_text(f"✅ Pesan terkirim! Sisa kuota: {db_user[uid]['kuota']}")
        else:
            await msg.reply_text("❌ Kuota habis, silakan isi ulang.")
pass
def main():
    # Inisialisasi Aplikasi Master/Clone
    app = Application.builder().token(TOKEN).build()

    # Jalankan ulang clone yang terdaftar di database (Hanya untuk Master)
    if not IS_CLONE:
        clones = load_json(CLONE_DB)
        for c in clones:
            try:
                # Kita gunakan get() agar jika key tidak ada, bot tidak crash (KeyError)
                env = os.environ.copy()
                env["BOT_TOKEN"] = c.get('token', '')
                env["CH_ID"] = c.get('ch', DEFAULT_CHANNEL)
                env["OWN_ID"] = str(c.get('own', OWNER_ID))
                env["IS_CLONE"] = "True"
                
                if env["BOT_TOKEN"]:
                    subprocess.Popen([sys.executable, sys.argv[0]], env=env)
                    logging.info(f"Bot Clone {c.get('token')[:10]}... diaktifkan.")
            except Exception as e:
                logging.error(f"Gagal mengaktifkan clone: {e}")

    # Tambahkan Handlers
    app.add_handler(CommandHandler("start", start)) 
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # Tambahkan filters.PHOTO agar bot bisa menerima foto bukti transfer
    # Baris ini sudah dirapikan masuk ke dalam blok def main
    # Tambahkan filters.PHOTO agar bot tidak mengabaikan kiriman gambar
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))


    logging.info(f"Bot {'CLONE' if IS_CLONE else 'MASTER'} Berjalan...")
    app.run_polling()

if __name__ == '__main__':
    main()

