# --- IMPORTS ---
import telebot
import os
import zipfile
import shutil
import json
import qrcode
import datetime
import re
import time
import hashlib
import threading
import random
from telebot import types
from datetime import timedelta
from flask import Flask

# ====================================================================
# --- ⚙️ CONFIGURATION (APNI DETAILS YAHAN BHAREIN) ---
# ====================================================================

API_TOKEN = '8469204740:AAFiZUpXbmQMdkM4bimceB6TVWgRYPA13_8'  # BotFather Token
ADMIN_ID = 8541572102               # Apni Numeric Telegram ID
ADMIN_GROUP_ID = -1003423423159     # Logs Group ID
REFERRAL_REWARD = 10                # Ek invite par kitne coins milenge
DAILY_BONUS_AMOUNT = 4             # Daily bonus coins
COIN_PRICE_VIP = 50                # 1 Month VIP ke liye kitne coins chahiye
FREE_DAILY_LIMIT = 1                # Free user daily kitni APK extract karega

# ====================================================================
# --- 📁 SYSTEM & DATABASE PATHS ---
# ====================================================================

bot = telebot.TeleBot(API_TOKEN)
startTime = time.time()

DB_USERS = "users_db.json"
DB_GROUPS = "groups_db.json"
SETTINGS_FILE = "settings.json"
DB_BANNED = "banned_db.json"
DB_COUPONS = "coupons_db.json"

# Default Settings
default_settings = {
    "upi_id": "pratiksingh4@fam",
    "price": 49,
    "group_price": 19,
    "maintenance_mode": False
}

# ====================================================================
# --- 💾 DATABASE MANAGER ---
# ====================================================================

def load_data():
    if not os.path.exists(DB_USERS): json.dump({}, open(DB_USERS, 'w'))
    if not os.path.exists(DB_GROUPS): json.dump({"allowed_groups": []}, open(DB_GROUPS, 'w'))
    if not os.path.exists(SETTINGS_FILE): json.dump(default_settings, open(SETTINGS_FILE, 'w'))
    if not os.path.exists(DB_BANNED): json.dump({"banned_ids": []}, open(DB_BANNED, 'w'))
    if not os.path.exists(DB_COUPONS): json.dump({}, open(DB_COUPONS, 'w'))
        
    return (json.load(open(DB_USERS)), json.load(open(DB_GROUPS)), 
            json.load(open(SETTINGS_FILE)), json.load(open(DB_BANNED)), 
            json.load(open(DB_COUPONS)))

def save_data(users=None, groups=None, settings=None, banned=None, coupons=None):
    if users is not None: json.dump(users, open(DB_USERS, 'w'), indent=4)
    if groups is not None: json.dump(groups, open(DB_GROUPS, 'w'), indent=4)
    if settings is not None: json.dump(settings, open(SETTINGS_FILE, 'w'), indent=4)
    if banned is not None: json.dump(banned, open(DB_BANNED, 'w'), indent=4)
    if coupons is not None: json.dump(coupons, open(DB_COUPONS, 'w'), indent=4)

# ====================================================================
# --- 🛠️ HELPER FUNCTIONS ---
# ====================================================================

def get_readable_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    return f"{int(d)}d {int(h)}h {int(m)}m {int(s)}s"

def is_user_premium(user_id):
    users, _, _, _, _ = load_data()
    str_id = str(user_id)
    if str_id in users and users[str_id].get("is_premium"):
        expiry = datetime.datetime.strptime(users[str_id]["expiry_date"], "%Y-%m-%d")
        if datetime.datetime.now() < expiry:
            return True
        else:
            users[str_id]["is_premium"] = False
            save_data(users=users)
    return False

def calculate_hash(file_path):
    sha1 = hashlib.sha1()
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
            md5.update(chunk)
    return md5.hexdigest(), sha1.hexdigest()

def is_admin_in_group(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# ====================================================================
# --- 🛡️ GROUP SECURITY SYSTEM (NEW) ---
# ====================================================================

@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'], content_types=['text', 'photo', 'video', 'document', 'audio', 'sticker', 'animation'])
def group_protector(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    _, groups, _, _, _ = load_data()

    # 1. Check if Group has purchased Plan
    if chat_id not in groups["allowed_groups"]:
        # Agar group allowed nahi hai, kuch mat karo (Silent)
        # Ya agar bot ko tag kiya jaye tabhi reply kare
        if message.text and "/start" in message.text:
            bot.reply_to(message, "🚫 **Group Not Authorized!**\nBuy Group License to activate me.")
        return

    # 2. Check if Sender is Admin
    if is_admin_in_group(chat_id, user_id):
        return  # Admin hai to ignore karo (sab allowed hai)

    # 3. Non-Admin Restriction Logic
    should_delete = False
    warning_text = "🚫 **Allowed Only for Admins!**"

    # Check for Media
    if message.content_type in ['photo', 'video', 'document', 'audio', 'animation']:
        should_delete = True

    # Check for Links in Text
    if message.text or message.caption:
        text_content = message.text or message.caption
        if re.search(r"(https?://|www\.|t\.me/|@)", text_content):
            should_delete = True
            warning_text = "🚫 **Links/Ads Not Allowed!**"

    # Execute Delete
    if should_delete:
        try:
            bot.delete_message(chat_id, message.message_id)
            warn = bot.send_message(chat_id, f"{warning_text}\n👤 {message.from_user.first_name}, don't send this here.")
            # Warning message ko bhi 5 sec baad delete kar do taaki kachra na ho
            time.sleep(5)
            bot.delete_message(chat_id, warn.message_id)
        except:
            pass

# ====================================================================
# --- 👑 ADMIN PANEL ---
# ====================================================================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Stats", callback_data="adm_stats"),
        types.InlineKeyboardButton("💾 Backup Data", callback_data="adm_backup"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("🎟️ Create Coupon", callback_data="adm_coupon"),
        types.InlineKeyboardButton("🛠️ Maintenance", callback_data="adm_maint"),
        types.InlineKeyboardButton("🏢 Add Group", callback_data="adm_addgroup_help")
    )
    bot.reply_to(message, "⚡ **GOD MODE ACTIVATED** ⚡\nSelect an action:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_callback(call):
    if call.from_user.id != ADMIN_ID: return
    
    if call.data == "adm_stats":
        users, groups, _, banned, _ = load_data()
        prem_count = sum(1 for u in users.values() if u.get("is_premium"))
        txt = (f"📊 **System Statistics**\n\n"
               f"👥 Total Users: `{len(users)}`\n"
               f"💎 VIP Users: `{prem_count}`\n"
               f"🏢 Groups: `{len(groups['allowed_groups'])}`\n"
               f"💀 Banned: `{len(banned['banned_ids'])}`")
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data == "adm_maint":
        _, _, settings, _, _ = load_data()
        settings['maintenance_mode'] = not settings['maintenance_mode']
        save_data(settings=settings)
        status = "ON" if settings['maintenance_mode'] else "OFF"
        bot.answer_callback_query(call.id, f"Maintenance Mode is now {status}")

    elif call.data == "adm_backup":
        try:
            for f in [DB_USERS, DB_GROUPS, DB_COUPONS]:
                with open(f, 'rb') as doc:
                    bot.send_document(ADMIN_ID, doc, caption=f"💾 Backup: `{f}`")
            bot.answer_callback_query(call.id, "✅ Backup Sent!")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}")

    elif call.data == "adm_addgroup_help":
        bot.send_message(call.message.chat.id, "Use: `/addgroup -100xxxxxxx` to activate a group.")

@bot.message_handler(commands=['addgroup'])
def add_group_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        gid = int(message.text.split()[1])
        _, groups, _, _, _ = load_data()
        if gid not in groups["allowed_groups"]:
            groups["allowed_groups"].append(gid)
            save_data(groups=groups)
            bot.reply_to(message, f"✅ Group `{gid}` Activated!")
            try: bot.send_message(gid, "🟢 **Security Activated!** Non-Admins are now restricted.")
            except: pass
    except:
        bot.reply_to(message, "❌ Invalid ID.")

@bot.message_handler(commands=['broadcast'])
def broadcast_msg(message):
    if message.from_user.id != ADMIN_ID: return
    if not message.reply_to_message: return bot.reply_to(message, "❌ Reply to a message!")
    
    msg = bot.reply_to(message, "🚀 **Broadcasting...**")
    users, _, _, _, _ = load_data()
    sent, failed = 0, 0
    
    for uid in users:
        try:
            bot.copy_message(uid, message.chat.id, message.reply_to_message.message_id)
            sent += 1
            time.sleep(0.05)
        except: failed += 1
            
    bot.edit_message_text(f"✅ **Broadcast Done!**\nSuccess: {sent}\nFailed: {failed}", message.chat.id, msg.message_id)

@bot.message_handler(commands=['addvip'])
def add_vip_manual(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        uid = str(message.text.split()[1])
        users, _, _, _, _ = load_data()
        expiry = datetime.datetime.now() + timedelta(days=30)
        if uid not in users: users[uid] = {}
        users[uid].update({"is_premium": True, "expiry_date": expiry.strftime("%Y-%m-%d")})
        save_data(users=users)
        bot.reply_to(message, f"💎 VIP added to `{uid}`")
    except: bot.reply_to(message, "❌ Usage: `/addvip 123456`")

# ====================================================================
# --- 👤 USER HANDLERS ---
# ====================================================================

@bot.message_handler(commands=['start'], func=lambda m: m.chat.type == 'private')
def start(message):
    user_id = message.from_user.id
    _, _, settings, banned, _ = load_data()
    
    if user_id in banned['banned_ids']: return
    if settings['maintenance_mode'] and user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "🛠️ **Bot is under Maintenance.**")
        return
    
    users, _, _, _, _ = load_data()
    str_id = str(user_id)
    
    if str_id not in users:
        users[str_id] = {
            "is_premium": False, 
            "join_date": str(datetime.date.today()),
            "coins": 0,
            "referred_by": None,
            "last_extract_date": None,
            "daily_count": 0
        }
        
        args = message.text.split()
        if len(args) > 1:
            referrer = args[1]
            if referrer != str_id and referrer in users:
                users[str_id]["referred_by"] = referrer
                users[referrer]["coins"] = users[referrer].get("coins", 0) + REFERRAL_REWARD
                users[str_id]["coins"] = REFERRAL_REWARD
                try: bot.send_message(referrer, f"🎉 **Referral Bonus:** +{REFERRAL_REWARD} Coins")
                except: pass
        
        save_data(users=users)

    main_menu(message)

def main_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👤 Profile", callback_data="my_profile"),
        types.InlineKeyboardButton("💰 Wallet", callback_data="my_wallet"),
        types.InlineKeyboardButton("🎁 Daily Bonus", callback_data="claim_bonus"),
        types.InlineKeyboardButton("🤝 Refer & Earn", callback_data="refer_link"),
        types.InlineKeyboardButton("🛒 Buy Premium", callback_data="buy_prem"),
        types.InlineKeyboardButton("🛍️ Coin Shop", callback_data="coin_shop"),
        types.InlineKeyboardButton("🆘 Help", callback_data="help")
    )
    
    text = (f"👋 **Welcome Back!**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🚀 **Advanced APK Extractor**\n"
            f"Free Limit: {FREE_DAILY_LIMIT} APK/Day\n"
            f"VIP Limit: Unlimited\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📂 **Send an APK file** to start.")
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    str_id = str(user_id)
    users, _, settings, _, coupons = load_data()
    
    if call.data == "my_profile":
        user_data = users.get(str_id, {})
        status = "💎 VIP Member" if is_user_premium(user_id) else "👤 Free User"
        coins = user_data.get("coins", 0)
        daily_used = user_data.get("daily_count", 0)
        
        txt = (f"👤 **User Profile**\n"
               f"━━━━━━━━━━━━━━\n"
               f"🆔 ID: `{user_id}`\n"
               f"🏷️ Status: **{status}**\n"
               f"💰 Coins: `{coins}`\n"
               f"📉 Today's Usage: `{daily_used}/{FREE_DAILY_LIMIT}`\n")
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown", 
                              reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Back", callback_data="main_menu")))

    elif call.data == "my_wallet":
        coins = users.get(str_id, {}).get("coins", 0)
        bot.answer_callback_query(call.id, f"💰 Balance: {coins} Coins")

    elif call.data == "refer_link":
        link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        txt = (f"🤝 **Invite & Earn**\n\nEarn {REFERRAL_REWARD} Coins per invite!\n\n🔗 `{link}`")
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown",
                              reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Back", callback_data="main_menu")))

    elif call.data == "claim_bonus":
        last_bonus = users[str_id].get("last_bonus_time", 0)
        now = time.time()
        
        if now - last_bonus > 86400:
            users[str_id]["coins"] = users[str_id].get("coins", 0) + DAILY_BONUS_AMOUNT
            users[str_id]["last_bonus_time"] = now
            save_data(users=users)
            bot.answer_callback_query(call.id, f"✅ +{DAILY_BONUS_AMOUNT} Coins!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "⏳ Come back later!", show_alert=True)

    elif call.data == "coin_shop":
        coins = users.get(str_id, {}).get("coins", 0)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"💎 Buy VIP (1 Month) - {COIN_PRICE_VIP} Coins", callback_data="buy_vip_coins"))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
        bot.edit_message_text(f"🛍️ **Coin Shop**\n💰 Balance: `{coins}` Coins", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "buy_vip_coins":
        coins = users.get(str_id, {}).get("coins", 0)
        if coins >= COIN_PRICE_VIP:
            users[str_id]["coins"] -= COIN_PRICE_VIP
            expiry = datetime.datetime.now() + timedelta(days=30)
            users[str_id]["is_premium"] = True
            users[str_id]["expiry_date"] = expiry.strftime("%Y-%m-%d")
            save_data(users=users)
            bot.answer_callback_query(call.id, "🎉 Purchased 1 Month VIP!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ Not enough coins!", show_alert=True)

    elif call.data == "main_menu":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        main_menu(call.message)

    elif call.data in ["buy_prem", "buy_group"]:
        price = settings['price'] if call.data == "buy_prem" else settings['group_price']
        item = "Premium" if call.data == "buy_prem" else "Group License"
        upi = f"upi://pay?pa={settings['upi_id']}&pn=Admin&am={price}&cu=INR"
        qr = qrcode.make(upi)
        qr.save("qr.png")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📤 Upload Screenshot", callback_data="upload_ss"))
        with open("qr.png", "rb") as f:
            bot.send_photo(call.message.chat.id, f, caption=f"💰 **Pay ₹{price} for {item}**", reply_markup=markup)
        os.remove("qr.png")

    elif call.data == "upload_ss":
        msg = bot.send_message(call.message.chat.id, "📸 **Send screenshot.**")
        bot.register_next_step_handler(msg, lambda m: bot.forward_message(ADMIN_GROUP_ID, m.chat.id, m.message_id) and bot.reply_to(m, "✅ Sent to Admin."))

# ====================================================================
# --- 🚀 FREE LIMIT & EXTRACTOR ENGINE ---
# ====================================================================

@bot.message_handler(content_types=['document'], func=lambda m: m.chat.type == 'private')
def handle_docs(message):
    user_id = message.from_user.id
    _, _, settings, _, _ = load_data()
    
    if settings['maintenance_mode'] and user_id != ADMIN_ID:
        return bot.reply_to(message, "🛠️ Maintenance Mode is ON.")

    if not message.document.file_name.lower().endswith('.apk'):
        return bot.reply_to(message, "❌ Only `.apk` files accepted.")

    # --- DAILY LIMIT CHECK ---
    users, _, _, _, _ = load_data()
    str_id = str(user_id)
    today_str = str(datetime.date.today())
    
    is_vip = is_user_premium(user_id)
    
    if str_id not in users: users[str_id] = {} # Safety check
    
    # Initialize keys if missing
    if "last_extract_date" not in users[str_id]:
        users[str_id]["last_extract_date"] = today_str
        users[str_id]["daily_count"] = 0
    
    # Reset counter if new day
    if users[str_id]["last_extract_date"] != today_str:
        users[str_id]["last_extract_date"] = today_str
        users[str_id]["daily_count"] = 0
    
    # Check Limit (Skip for VIP)
    if not is_vip:
        if users[str_id]["daily_count"] >= FREE_DAILY_LIMIT:
            bot.reply_to(message, f"🛑 **Daily Limit Reached!**\nFree users can only extract {FREE_DAILY_LIMIT} APK per day.\n\n🛒 **Buy Premium** for Unlimited Access.", 
                         reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💎 Buy Premium", callback_data="buy_prem")))
            return

    # --- PROCESSING ---
    status_msg = bot.reply_to(message, "⏳ **Processing...**")
    
    # Increment count for Free users
    if not is_vip:
        users[str_id]["daily_count"] += 1
        save_data(users=users)
        
    temp_dir = f"temp_{user_id}_{int(time.time())}"
    os.makedirs(temp_dir, exist_ok=True)
    apk_path = os.path.join(temp_dir, "app.apk")
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(apk_path, 'wb') as f: f.write(downloaded_file)
        
        bot.edit_message_text("🔍 **Analyzing...**", message.chat.id, status_msg.message_id)
        md5, sha1 = calculate_hash(apk_path)
        
        found_res = False
        res_out = os.path.join(temp_dir, "res.zip")
        has_manifest = False
        dex_count = 0
        
        with zipfile.ZipFile(apk_path, 'r') as z:
            file_list = z.namelist()
            if "AndroidManifest.xml" in file_list: has_manifest = True
            dex_count = sum(1 for f in file_list if f.endswith(".dex"))
            
            for f in file_list:
                if "assets" in f and f.endswith(".zip"):
                    with z.open(f) as source, open(res_out, "wb") as target:
                        shutil.copyfileobj(source, target)
                    found_res = True
                    break
        
        report = (f"📦 **APK Report**\n"
                  f"📛 Name: `{message.document.file_name}`\n"
                  f"📜 Manifest: `{'✅' if has_manifest else '❌'}`\n"
                  f"🧠 Dex Files: `{dex_count}`\n"
                  f"🔐 MD5: `{md5}`")
        
        bot.edit_message_text(report, message.chat.id, status_msg.message_id, parse_mode="Markdown")
        
        if found_res:
            with open(res_out, 'rb') as f:
                bot.send_document(message.chat.id, f, caption="✅ **Extracted Resource File**")
        else:
            bot.send_message(message.chat.id, "⚠️ No `assets/res.zip` found.")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ====================================================================
# --- 🌐 SERVER ---
# ====================================================================

app = Flask(__name__)

@app.route('/')
def home(): return "BOT ALIVE", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
