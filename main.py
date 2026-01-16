import telebot
import os
import zipfile
import shutil
import json
import qrcode
import datetime
import re
from telebot import types
from datetime import timedelta
from flask import Flask
from threading import Thread

# --- CONFIGURATION ---
API_TOKEN = '8469204740:AAFiZUpXbmQMdkM4bimceB6TVWgRYPA13_8'  # Apna Token yahan lagayein
ADMIN_ID = 8541572102               # Apni Personal Telegram ID
ADMIN_GROUP_ID = -1003423423159     # Admin Group ID

bot = telebot.TeleBot(API_TOKEN)

# --- DATABASE FILES ---
DB_USERS = "users_db.json"
DB_GROUPS = "groups_db.json"
SETTINGS_FILE = "settings.json"

# --- BAD WORDS LIST ---
BAD_WORDS = ["kutta", "kamina", "bc", "mc", "f**k", "scam", "madarchod"]

# --- DEFAULT SETTINGS ---
default_settings = {
    "upi_id": "pratiksingh4@fam",
    "price": 49,
    "group_price": 19,
    "offer_text": "Limited Time Offer"
}

# --- DATA MANAGER (Database) ---

def load_data():
    if not os.path.exists(DB_USERS):
        with open(DB_USERS, 'w') as f: json.dump({}, f)
    with open(DB_USERS, 'r') as f: users = json.load(f)

    if not os.path.exists(DB_GROUPS):
        with open(DB_GROUPS, 'w') as f: json.dump({"allowed_groups": []}, f)
    with open(DB_GROUPS, 'r') as f: groups = json.load(f)

    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f: json.dump(default_settings, f)
    with open(SETTINGS_FILE, 'r') as f: settings = json.load(f)
    return users, groups, settings

def save_data(users=None, groups=None, settings=None):
    if users is not None:
        with open(DB_USERS, 'w') as f: json.dump(users, f, indent=4)
    if groups is not None:
        with open(DB_GROUPS, 'w') as f: json.dump(groups, f, indent=4)
    if settings is not None:
        with open(SETTINGS_FILE, 'w') as f: json.dump(settings, f, indent=4)

def is_user_premium(user_id):
    users, _, _ = load_data()
    str_id = str(user_id)
    if str_id in users and users[str_id].get("is_premium"):
        expiry = datetime.datetime.strptime(users[str_id]["expiry_date"], "%Y-%m-%d")
        if datetime.datetime.now() < expiry:
            return True
        else:
            users[str_id]["is_premium"] = False
            save_data(users=users)
    return False

def is_group_allowed(chat_id):
    _, groups, _ = load_data()
    return chat_id in groups["allowed_groups"]

def is_admin_in_chat(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# --- GROUP SECURITY HANDLERS ---

@bot.my_chat_member_handler()
def on_bot_join_group(message):
    chat_id = message.chat.id
    new_status = message.new_chat_member.status
    if new_status in ['member', 'administrator']:
        if not is_group_allowed(chat_id):
            text = (
                f"🛑 **STOP! Group Not Verified**\n\n"
                "Please buy the Group Plan to activate me.\n"
                f"👤 **Contact Owner:** [Click Here](tg://user?id={ADMIN_ID})\n"
                f"🆔 **Group ID:** `{chat_id}`"
            )
            try: bot.send_message(chat_id, text, parse_mode="Markdown")
            except: pass

@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'])
def group_moderation(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_group_allowed(chat_id): return 

    # Bad Words
    if message.text:
        for word in BAD_WORDS:
            if word in message.text.lower():
                try: bot.delete_message(chat_id, message.message_id); return
                except: pass

    # Admin Check
    if is_admin_in_chat(chat_id, user_id): return

    # Restrictions
    should_delete = False
    if message.content_type in ['photo', 'video', 'document', 'audio']: should_delete = True
    if message.text or message.caption:
        content = message.text or message.caption
        if re.search(r"(https?://|www\.|t\.me/)", content): should_delete = True

    if should_delete:
        try: bot.delete_message(chat_id, message.message_id)
        except: pass

# --- ADMIN COMMANDS ---

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    text = "👮‍♂️ **Admin Panel**\nUse `/addgroup <id>`, `/addvip <id>`, `/broadcast`"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['addgroup'])
def add_group(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        gid = int(message.text.split()[1])
        _, groups, _ = load_data()
        if gid not in groups["allowed_groups"]:
            groups["allowed_groups"].append(gid)
            save_data(groups=groups)
            bot.reply_to(message, f"✅ Group `{gid}` Activated.")
            try: bot.send_message(gid, "🟢 **Bot Activated!**")
            except: pass
    except: pass

@bot.message_handler(commands=['addvip'])
def add_vip(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        uid = message.text.split()[1]
        users, _, _ = load_data()
        expiry = datetime.datetime.now() + timedelta(days=30)
        users[str(uid)] = {"is_premium": True, "expiry_date": expiry.strftime("%Y-%m-%d")}
        save_data(users=users)
        bot.reply_to(message, f"✅ User `{uid}` is now VIP.")
    except: pass

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    if not message.reply_to_message: return
    users, _, _ = load_data()
    count = 0
    for uid in users:
        try:
            bot.copy_message(uid, message.chat.id, message.reply_to_message.message_id)
            count += 1
        except: pass
    bot.reply_to(message, f"✅ Sent to {count} users.")

# --- PAYMENT SYSTEM ---

@bot.message_handler(commands=['start'], func=lambda m: m.chat.type == 'private')
def start_private(message):
    users, _, _ = load_data()
    uid = str(message.from_user.id)
    if uid not in users:
        users[uid] = {"is_premium": False, "expiry_date": None}
        save_data(users=users)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💎 Buy Premium", callback_data="buy_premium"),
        types.InlineKeyboardButton("🛡️ Buy Group Plan", callback_data="buy_group")
    )
    bot.send_message(message.chat.id, "👋 **MT Manager Style Extractor**\nAPK bhejo -> `assets/res.zip` ka data milega.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    _, _, settings = load_data()
    if call.data == "buy_premium":
        send_qr(call.message, settings['price'], "User Premium")
    elif call.data == "buy_group":
        send_qr(call.message, settings['group_price'], "Group Plan")
    elif call.data == "upload_ss":
        msg = bot.send_message(call.message.chat.id, "📸 **Send Screenshot now.**")
        bot.register_next_step_handler(msg, process_ss)

def send_qr(message, amount, plan):
    _, _, settings = load_data()
    upi = f"upi://pay?pa={settings['upi_id']}&pn=Admin&am={amount}&cu=INR"
    img = qrcode.make(upi)
    img.save("qr.png")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📤 Upload Screenshot", callback_data="upload_ss"))
    with open("qr.png", "rb") as f:
        bot.send_photo(message.chat.id, f, caption=f"💰 **{plan}**\nPrice: ₹{amount}\nPay & Upload Screenshot.", reply_markup=markup)
    os.remove("qr.png")

def process_ss(message):
    if message.content_type == 'photo':
        bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=f"💰 **New Payment**\nUser: `{message.from_user.id}`")
        bot.reply_to(message, "✅ Sent to Admin.")

# --- 🚀 MT MANAGER STYLE LOGIC (Updated) ---

@bot.message_handler(content_types=['document'], func=lambda m: m.chat.type == 'private')
def handle_mt_manager_apk(message):
    user_id = message.from_user.id
    
    # Premium Limit Check
    if not is_user_premium(user_id) and message.document.file_size > 20 * 1024 * 1024:
        bot.reply_to(message, "🛑 **20MB Limit!** Buy Premium for unlimited.")
        return

    if not message.document.file_name.endswith('.apk'):
        bot.reply_to(message, "❌ Sirf `.apk` file bhejein.")
        return

    status_msg = bot.reply_to(message, "⏳ **Analysing APK like MT Manager...**")
    
    # Paths Setup
    root_temp = f"temp_mt_{user_id}"
    if os.path.exists(root_temp): shutil.rmtree(root_temp)
    os.makedirs(root_temp)
    
    try:
        # 1. APK Download
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        apk_path = os.path.join(root_temp, "app.apk")
        with open(apk_path, "wb") as f: f.write(downloaded)
        
        # 2. Extract APK & Find 'assets/res.zip'
        res_zip_found = False
        res_zip_path = os.path.join(root_temp, "res.zip")
        
        bot.edit_message_text("📂 **Searching 'assets/res.zip'...**", message.chat.id, status_msg.message_id)
        
        with zipfile.ZipFile(apk_path, 'r') as apk_zip:
            # Check list specifically for assets/res.zip
            if "assets/res.zip" in apk_zip.namelist():
                # Extract ONLY res.zip from APK to temp
                with apk_zip.open("assets/res.zip") as zf, open(res_zip_path, 'wb') as f:
                    shutil.copyfileobj(zf, f)
                res_zip_found = True
            else:
                # Fallback
                for file in apk_zip.namelist():
                    if file.startswith("assets/") and file.endswith(".zip"):
                        with apk_zip.open(file) as zf, open(res_zip_path, 'wb') as f:
                            shutil.copyfileobj(zf, f)
                        res_zip_found = True
                        break

        # 3. Process 'res.zip' if found
        if res_zip_found:
            bot.edit_message_text("🔓 **Decrypting res.zip...**", message.chat.id, status_msg.message_id)
            
            # Extract content of res.zip
            final_extract_dir = os.path.join(root_temp, "final_files")
            os.makedirs(final_extract_dir)
            
            with zipfile.ZipFile(res_zip_path, 'r') as nested_zip:
                nested_zip.extractall(final_extract_dir)
            
            # 4. Zip the content and Send
            bot.edit_message_text("📦 **Repacking Data...**", message.chat.id, status_msg.message_id)
            
            output_zip = os.path.join(root_temp, "Extracted_Assets")
            shutil.make_archive(output_zip, 'zip', final_extract_dir)
            
            with open(output_zip + ".zip", "rb") as f:
                bot.send_document(
                    message.chat.id, 
                    f, 
                    caption="✅ **Extraction Successful!**\n📂 Yeh raha aapka `assets/res.zip` ka data."
                )
            bot.delete_message(message.chat.id, status_msg.message_id)
            
        else:
            error_msg = "❌ **Error:** `assets/res.zip` nahi mila.\nYeh tool sirf specific apps par kaam karta hai."
            bot.edit_message_text(error_msg, message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")
    finally:
        if os.path.exists(root_temp): shutil.rmtree(root_temp)

# --- 🚀 KEEP ALIVE (Flask) ---
app = Flask('')

@app.route('/')
def home():
    return "I am alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("🔥 Bot Running...")
    keep_alive()  
    bot.infinity_polling()