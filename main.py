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
FORCE_SUB_CHANNEL = "@zry_x_75"  # Channel Username (Correct likhna)
CHANNEL_ID = -1003423729715          # Channel ID (Agar ye galat bhi hua to Username se kaam chal jayega)
REFERRAL_REWARD = 10                # Ek invite par kitne coins milenge
DAILY_BONUS_AMOUNT = 4             # Daily bonus coins
COIN_PRICE_VIP = 50                # 1 Month VIP ke liye kitne coins chahiye

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
    "upi_id": "yourupi@okaxis",
    "price": 49,
    "group_price": 19,
    "maintenance_mode": False
}

# ====================================================================
# --- 💾 DATABASE MANAGER (ADVANCED) ---
# ====================================================================

def load_data():
    # File Creation Checks
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

# --- FIXED CHECK SUB FUNCTION ---
def check_sub(user_id):
    try:
        # Method 1: Try with Channel ID (Most reliable if ID is correct)
        chat_member = bot.get_chat_member(CHANNEL_ID, user_id)
        if chat_member.status in ['creator', 'administrator', 'member']:
            return True
    except:
        # Fallback: Agar ID galat hai to error aayega, tab hum Username try karenge
        pass
    
    try:
        # Method 2: Try with Channel Username (Backup)
        chat_member = bot.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        if chat_member.status in ['creator', 'administrator', 'member']:
            return True
    except:
        # Agar dono fail ho gaye (Bot admin nahi hai ya channel exist nahi karta)
        return False

    return False

def calculate_hash(file_path):
    sha1 = hashlib.sha1()
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
            md5.update(chunk)
    return md5.hexdigest(), sha1.hexdigest()

# ====================================================================
# --- 👑 ADMIN PANEL & GOD COMMANDS ---
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
        types.InlineKeyboardButton("💰 Give Coins", callback_data="adm_coins")
    )
    bot.reply_to(message, "⚡ **GOD MODE ACTIVATED** ⚡\nSelect an action:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_callback(call):
    if call.from_user.id != ADMIN_ID: return
    
    if call.data == "adm_stats":
        users, groups, _, banned, _ = load_data()
        prem_count = sum(1 for u in users.values() if u.get("is_premium"))
        total_coins = sum(u.get("coins", 0) for u in users.values())
        
        txt = (f"📊 **System Statistics**\n\n"
               f"👥 Total Users: `{len(users)}`\n"
               f"💎 VIP Users: `{prem_count}`\n"
               f"💰 Circulating Coins: `{total_coins}`\n"
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

    elif call.data == "adm_coupon":
        bot.send_message(call.message.chat.id, "📝 Usage: `/addcoupon <CODE> <DAYS>`")

@bot.message_handler(commands=['addcoupon'])
def add_coupon(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        code, days = parts[1], int(parts[2])
        _, _, _, _, coupons = load_data()
        coupons[code] = days
        save_data(coupons=coupons)
        bot.reply_to(message, f"🎟️ **Coupon Created!**\nCode: `{code}`\nDuration: {days} Days")
    except:
        bot.reply_to(message, "❌ Error. Format: `/addcoupon SALE10 30`")

@bot.message_handler(commands=['addcoins'])
def add_coins_admin(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        uid, amount = str(parts[1]), int(parts[2])
        users, _, _, _, _ = load_data()
        
        if uid in users:
            users[uid]["coins"] = users[uid].get("coins", 0) + amount
            save_data(users=users)
            bot.reply_to(message, f"✅ Added {amount} coins to `{uid}`")
            bot.send_message(uid, f"💰 **Admin added {amount} coins to your wallet!**")
        else:
            bot.reply_to(message, "❌ User not found.")
    except:
        bot.reply_to(message, "❌ Usage: `/addcoins <USERID> <AMOUNT>`")

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

# ====================================================================
# --- 👤 USER HANDLERS (REFERRAL, WALLET, SHOP) ---
# ====================================================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    _, _, settings, banned, _ = load_data()
    
    # Checks
    if user_id in banned['banned_ids']: return
    if settings['maintenance_mode'] and user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "🛠️ **Bot is under Maintenance.**\nPlease come back later.")
        return
    
    users, _, _, _, _ = load_data()
    str_id = str(user_id)
    is_new_user = False
    
    if str_id not in users:
        is_new_user = True
        users[str_id] = {
            "is_premium": False, 
            "join_date": str(datetime.date.today()),
            "coins": 0,
            "referred_by": None
        }
        
        # Referral Logic
        args = message.text.split()
        if len(args) > 1:
            referrer = args[1]
            if referrer != str_id and referrer in users:
                users[str_id]["referred_by"] = referrer
                users[referrer]["coins"] = users[referrer].get("coins", 0) + REFERRAL_REWARD
                users[str_id]["coins"] = REFERRAL_REWARD # Bonus for new user too
                try: bot.send_message(referrer, f"🎉 **New Referral!** You earned +{REFERRAL_REWARD} Coins.")
                except: pass
        
        save_data(users=users)

    if not check_sub(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL.replace('@', '')}"))
        markup.add(types.InlineKeyboardButton("🔄 Check Status", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ **Access Locked!**\nJoin our channel to unlock the bot.", reply_markup=markup)
        return

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
            f"🚀 **Advanced MT Tool Bot**\n"
            f"Extract APKs, Earn Coins, Get VIP.\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📂 **Send any APK file** to start processing.")
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    str_id = str(user_id)
    users, _, settings, _, coupons = load_data()
    
    if call.data == "check_sub":
        if check_sub(user_id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            main_menu(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Not Joined Yet! (Try Joining Again)", show_alert=True)

    elif call.data == "my_profile":
        user_data = users.get(str_id, {})
        status = "💎 VIP Member" if is_user_premium(user_id) else "👤 Free User"
        coins = user_data.get("coins", 0)
        
        txt = (f"👤 **User Profile**\n"
               f"━━━━━━━━━━━━━━\n"
               f"🆔 ID: `{user_id}`\n"
               f"🏷️ Status: **{status}**\n"
               f"💰 Coins: `{coins}`\n"
               f"📅 Joined: `{user_data.get('join_date', 'N/A')}`")
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown", 
                              reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Back", callback_data="main_menu")))

    elif call.data == "my_wallet":
        coins = users.get(str_id, {}).get("coins", 0)
        bot.answer_callback_query(call.id, f"💰 Balance: {coins} Coins")

    elif call.data == "refer_link":
        link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        txt = (f"🤝 **Invite & Earn**\n\n"
               f"Invite friends and earn **{REFERRAL_REWARD} Coins** per invite!\n\n"
               f"🔗 **Your Link:**\n`{link}`\n\n"
               f"Tap to copy.")
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown",
                              reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Back", callback_data="main_menu")))

    elif call.data == "claim_bonus":
        last_bonus = users[str_id].get("last_bonus_time", 0)
        now = time.time()
        
        if now - last_bonus > 86400: # 24 Hours
            users[str_id]["coins"] = users[str_id].get("coins", 0) + DAILY_BONUS_AMOUNT
            users[str_id]["last_bonus_time"] = now
            save_data(users=users)
            bot.answer_callback_query(call.id, f"✅ Collected +{DAILY_BONUS_AMOUNT} Coins!", show_alert=True)
        else:
            wait = int(86400 - (now - last_bonus))
            bot.answer_callback_query(call.id, f"⏳ Come back in {get_readable_time(wait)}", show_alert=True)

    elif call.data == "coin_shop":
        coins = users.get(str_id, {}).get("coins", 0)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"💎 Buy VIP (1 Month) - {COIN_PRICE_VIP} Coins", callback_data="buy_vip_coins"))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
        
        bot.edit_message_text(f"🛍️ **Coin Shop**\n\n💰 Your Balance: `{coins}` Coins\nExchange coins for Premium.", 
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "buy_vip_coins":
        coins = users.get(str_id, {}).get("coins", 0)
        if coins >= COIN_PRICE_VIP:
            users[str_id]["coins"] -= COIN_PRICE_VIP
            expiry = datetime.datetime.now() + timedelta(days=30)
            users[str_id]["is_premium"] = True
            users[str_id]["expiry_date"] = expiry.strftime("%Y-%m-%d")
            save_data(users=users)
            bot.answer_callback_query(call.id, "🎉 Purchased 1 Month VIP!", show_alert=True)
            main_menu(call.message)
        else:
            bot.answer_callback_query(call.id, f"❌ Not enough coins! Need {COIN_PRICE_VIP}", show_alert=True)

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
        markup.add(types.InlineKeyboardButton("🔙 Cancel", callback_data="main_menu"))

        with open("qr.png", "rb") as f:
            bot.send_photo(call.message.chat.id, f, caption=f"💰 **Pay ₹{price} for {item}**\n\nScan QR & Send Screenshot.", reply_markup=markup)
        os.remove("qr.png")

    elif call.data == "upload_ss":
        msg = bot.send_message(call.message.chat.id, "📸 **Send the screenshot now.**")
        bot.register_next_step_handler(msg, lambda m: bot.forward_message(ADMIN_GROUP_ID, m.chat.id, m.message_id) and bot.reply_to(m, "✅ Sent to Admin."))

# ====================================================================
# --- 🚀 ULTRA GOD LEVEL APK ENGINE ---
# ====================================================================

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.chat.type != 'private': return # Only private processing
    
    user_id = message.from_user.id
    _, _, settings, _, _ = load_data()
    
    if settings['maintenance_mode'] and user_id != ADMIN_ID:
        return bot.reply_to(message, "🛠️ Maintenance Mode is ON.")

    if not check_sub(user_id): return bot.reply_to(message, "❌ Join Channel First.")
    
    if not message.document.file_name.lower().endswith('.apk'):
        return bot.reply_to(message, "❌ Only `.apk` files accepted.")

    is_vip = is_user_premium(user_id)
    limit = 2000 * 1024 * 1024 if is_vip else 50 * 1024 * 1024 # 2GB VIP, 50MB Free
    
    if message.document.file_size > limit:
        return bot.reply_to(message, "🛑 **File Too Big!** Buy Premium for 2GB Limit.")

    status_msg = bot.reply_to(message, "⏳ **Initializing Deep Scan...**\n⬇️ Downloading...")
    
    temp_dir = f"temp_{user_id}_{int(time.time())}"
    os.makedirs(temp_dir, exist_ok=True)
    apk_path = os.path.join(temp_dir, "app.apk")
    
    try:
        # Download
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(apk_path, 'wb') as f: f.write(downloaded_file)
        
        # Analyze
        bot.edit_message_text("🔍 **Analyzing Internals...**", message.chat.id, status_msg.message_id)
        md5, sha1 = calculate_hash(apk_path)
        
        # Advanced Zip Scan
        found_res = False
        res_out = os.path.join(temp_dir, "res.zip")
        
        has_manifest = False
        dex_count = 0
        has_lib = False
        arch_types = []
        
        with zipfile.ZipFile(apk_path, 'r') as z:
            file_list = z.namelist()
            total_files = len(file_list)
            
            # 1. Search for critical files
            if "AndroidManifest.xml" in file_list: has_manifest = True
            
            # 2. Count Dex files
            dex_count = sum(1 for f in file_list if f.endswith(".dex"))
            
            # 3. Detect Arch
            if any("lib/arm64-v8a" in f for f in file_list): arch_types.append("ARM64")
            if any("lib/armeabi-v7a" in f for f in file_list): arch_types.append("ARMv7")
            if any("lib/x86" in f for f in file_list): arch_types.append("x86")
            
            # 4. Extract res.zip (MT Manager Style)
            for f in file_list:
                if "assets" in f and f.endswith(".zip"):
                    with z.open(f) as source, open(res_out, "wb") as target:
                        shutil.copyfileobj(source, target)
                    found_res = True
                    break
        
        # Architecture String
        arch_str = ", ".join(arch_types) if arch_types else "Universal/Java"
        
        # Report Generation
        report = (f"📦 **Ultimate APK Report**\n"
                  f"━━━━━━━━━━━━━━━━━━\n"
                  f"📛 Name: `{message.document.file_name}`\n"
                  f"📁 Files: `{total_files}`\n"
                  f"📜 Manifest: `{'✅ Found' if has_manifest else '❌ Missing'}`\n"
                  f"🧠 Dex Files: `{dex_count}` (Multidex: {'Yes' if dex_count > 1 else 'No'})\n"
                  f"⚙️ Arch: `{arch_str}`\n"
                  f"🔐 MD5: `{md5}`\n"
                  f"🛡️ SHA1: `{sha1[:10]}...`")
        
        bot.edit_message_text(report + "\n\n📤 **Uploading Result...**", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        
        if found_res:
            with open(res_out, 'rb') as f:
                bot.send_document(message.chat.id, f, caption="✅ **Extracted Resource File**\n_(MT Manager Style)_")
        else:
            bot.send_message(message.chat.id, "⚠️ **Notice:** No internal `assets/res.zip` found.")

    except Exception as e:
        bot.reply_to(message, f"❌ **Error:** {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        try: bot.delete_message(message.chat.id, status_msg.message_id)
        except: pass

# ====================================================================
# --- 🌐 RENDER DEPLOYMENT SERVER (NO PORT ERROR FIX) ---
# ====================================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 ULTRA GOD BOT IS ALIVE - 200 OK", 200

def run_flask():
    # Render assigns a port automatically via environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# --- START BOT ---
if __name__ == "__main__":
    print("🚀 SYSTEM ONLINE: Loading Databases...")
    keep_alive()
    bot.infinity_polling(skip_pending=True)
