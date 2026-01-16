import telebot
import yt_dlp
import os
import random
import json
from datetime import date
from telebot import types
from flask import Flask, request, jsonify, render_template
from threading import Thread

# --- إعداد السيرفر ---
app = Flask('', template_folder='templates')

@app.route('/')
def home():
    # هنا التعديل عشان يفتح التطبيق مش يكتب نص
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def receive_data():
    data = request.json
    req_type = data.get('type')
    text = data.get('text')
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'error', 'msg': 'User ID missing'})

    # 1. معالجة الهدية
    if req_type == 'gift':
        success, gift, total = claim_daily_gift(user_id)
        if success:
            return jsonify({'status': 'ok', 'msg': f'مبروك! كسبت {gift} نقطة', 'new_points': total})
        else:
            return jsonify({'status': 'error', 'msg': 'أخذت الهدية اليوم!'})

    # 2. جلب النقاط
    if req_type == 'get_points':
        d, _ = get_user_data(user_id)
        points = d.get(str(user_id), {}).get('points', 0)
        return jsonify({'points': points})

    # 3. البحث والتحميل
    if req_type == 'search':
        # البحث هيبعت النتائج في شات البوت
        Thread(target=process_web_search, args=(user_id, text)).start()
    else:
        # التحميل هيبعت الفيديو في شات البوت
        if ("youtube.com" in text or "youtu.be" in text) and MAINTENANCE_STATUS['youtube']:
             pass 
        Thread(target=process_url_flow, args=(user_id, text)).start()
    
    return jsonify({'status': 'ok'})

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- إعدادات البوت ---
BOT_TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
# تأكد إن ده رابط موقعك الصح على ريندر
APP_URL = "https://kareem-live.onrender.com"

MAINTENANCE_STATUS = {
    'youtube': False,
    'facebook': False,
    'instagram': False,
    'tiktok': False
}

if not BOT_TOKEN:
    print("Error: TOKEN is missing.")

bot = telebot.TeleBot(BOT_TOKEN)
users_file = "users.txt"
rewards_file = "rewards.json"
channel_file = "force_sub.txt"

BLOCKED_KEYWORDS = [
    "xnxx", "pornhub", "xvideos", "sex", "xxx", "nude", "pussy", 
    "dick", "cock", "boobs", "hentai", "milf", "sharmota", "neek", 
    "nik", "sks", "film sex", "سكس", "نيك", "اباحي", "شرموطة", 
    "toz", "kuss"
]

SUCCESS_MSGS = [
    "عاش! الرابط وصل",
    "ثواني ويكون عندك",
    "جاري التجهيز",
    "طلبك وصل",
    "انت تؤمر"
]

# --- الدوال المساعدة ---

def get_user_data(user_id):
    if not os.path.exists(rewards_file):
        with open(rewards_file, "w") as f: json.dump({}, f)
    try:
        with open(rewards_file, "r") as f: data = json.load(f)
    except: data = {}
    
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = {"points": 0, "last_claimed": ""}
    return data, user_id

def claim_daily_gift(user_id):
    data, uid = get_user_data(user_id)
    today = str(date.today())
    
    if data[uid]["last_claimed"] == today:
        return False, 0, data[uid]["points"]
    
    gift = random.randint(1, 3)
    data[uid]["points"] += gift
    data[uid]["last_claimed"] = today
    
    with open(rewards_file, "w") as f: json.dump(data, f)
    return True, gift, data[uid]["points"]

def is_safe_content(text):
    text = text.lower()
    for word in BLOCKED_KEYWORDS:
        if word in text: return False
    return True

def save_and_notify_admin(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    username = f"@{message.from_user.username}" if message.from_user.username else "لا يوجد"
    
    # التأكد من وجود الملف
    if not os.path.exists(users_file):
        with open(users_file, "w") as f: pass
    
    # قراءة المستخدمين
    with open(users_file, "r") as f:
        users = f.read().splitlines()
    
    # لو المستخدم جديد
    if user_id not in users:
        with open(users_file, "a") as f:
            f.write(user_id + "\n")
        
        # حساب العدد الكلي بعد الإضافة
        total_members = len(users) + 1
        
        if ADMIN_ID:
            msg = (
                f"تم دخول شخص جديد إلى البوت الخاص بك 👾\n"
                f"-------------------------\n\n"
                f"• معلومات العضو الجديد .\n\n"
                f"• الاسم : {first_name}\n"
                f"• معرف : {username}\n"
                f"• الايدي : `{user_id}`\n"
                f"-------------------------\n"
                f"• عدد الأعضاء الكلي : {total_members}"
            )
            try:
                bot.send_message(ADMIN_ID, msg)
            except:
                pass
        return True
    return False

def check_sub(user_id):
    if not os.path.exists(channel_file): return True
    with open(channel_file, "r") as f: ch_user = f.read().strip()
    if not ch_user: return True
    try:
        member = bot.get_chat_member(ch_user, user_id)
        if member.status in ['creator', 'administrator', 'member']: return True
    except: return True
    return False

@bot.my_chat_member_handler()
def handle_status_change(message):
    if not ADMIN_ID: return
    user = message.from_user
    new_status = message.new_chat_member.status
    old_status = message.old_chat_member.status
    
    if new_status == "kicked":
        bot.send_message(ADMIN_ID, f"قام مستخدم بحظر البوت\nالاسم: {user.first_name}\nالأيدي: {user.id}")
    elif new_status == "member" and old_status == "kicked":
        bot.send_message(ADMIN_ID, f"قام مستخدم بإعادة استخدام البوت\nالاسم: {user.first_name}\nالأيدي: {user.id}")

# --- المعالجة ---

def process_web_search(chat_id, query):
    bot.send_message(chat_id, f"🔎 جاري البحث عن: {query}")
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
            results = ydl.extract_info(f"ytsearch5:{query}", download=False)['entries']
        
        if not results:
            bot.send_message(chat_id, "❌ لا توجد نتائج")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for vid in results:
            title = vid.get('title', 'Video')
            url = vid.get('webpage_url')
            markup.add(types.InlineKeyboardButton(f"🎬 {title}", callback_data=f"web_dl|{url}"))
            
        bot.send_message(chat_id, "👇 اختر للتحميل:", reply_markup=markup)

    except Exception as e:
        bot.send_message(chat_id, "❌ خطأ في البحث")

def process_url_flow(chat_id, url):
    if not is_safe_content(url):
        bot.send_message(chat_id, "🚫 محتوى محظور")
        return

    if ("youtube.com" in url or "youtu.be" in url) and MAINTENANCE_STATUS['youtube']:
        bot.send_message(chat_id, "⚠️ يوتيوب في الصيانة")
        return

    msg = bot.send_message(chat_id, f"🔎 الرابط وصل\nجاري الفحص...")
    
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'ignoreerrors': True, 'nocheckcertificate': True}
        if os.path.exists('cookies.txt'): ydl_opts['cookiefile'] = 'cookies.txt'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            bot.edit_message_text("❌ الرابط لا يعمل", chat_id=msg.chat.id, message_id=msg.message_id)
            return

        title = info.get('title', 'Link')
        thumbnail = info.get('thumbnail')
        duration = info.get('duration')
        linked_title = f"[{title}]({url})"
        motivational_msg = random.choice(SUCCESS_MSGS)

        if duration and duration > 0:
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🎥 720p", callback_data="dl|720"),
                types.InlineKeyboardButton("🎥 480p", callback_data="dl|480")
            )
            markup.add(
                types.InlineKeyboardButton("🎥 360p", callback_data="dl|360"),
                types.InlineKeyboardButton("🎵 Audio", callback_data="dl|audio")
            )
            markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel"))

            bot.delete_message(chat_id, msg.message_id)
            caption_text = f"🎬 {linked_title}\n\n{motivational_msg}\n👇 اختر الجودة:"
            
            if thumbnail:
                bot.send_photo(chat_id, thumbnail, caption=caption_text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(chat_id, caption_text, parse_mode="Markdown", reply_markup=markup)
        
        else:
            bot.edit_message_text(f"{motivational_msg}\n🖼️ جاري تحميل الصور...", chat_id=msg.chat.id, message_id=msg.message_id)
            
            ydl_opts_img = {
                'outtmpl': 'media/%(title)s.%(ext)s',
                'quiet': True,
                'max_filesize': 50*1024*1024,
                'nocheckcertificate': True
            }
            if os.path.exists('cookies.txt'): ydl_opts_img['cookiefile'] = 'cookies.txt'

            with yt_dlp.YoutubeDL(ydl_opts_img) as ydl_img:
                info_img = ydl_img.extract_info(url, download=True)
                filename = ydl_img.prepare_filename(info_img)
                caption = f"✅ @kareemcv"
                
                with open(filename, 'rb') as f:
                    bot.send_photo(chat_id, f, caption=caption)
                
                if os.path.exists(filename): os.remove(filename)
                bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        bot.edit_message_text("❌ فشل التحميل", chat_id=msg.chat.id, message_id=msg.message_id)
        if ADMIN_ID:
            err_msg = f"⚠️ تقرير خطأ:\nالمستخدم: {chat_id}\nالرابط: {url}\nالخطأ: {str(e)}"
            bot.send_message(ADMIN_ID, err_msg)

# --- الأوامر ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_and_notify_admin(message)
    data, uid = get_user_data(message.from_user.id)
    
    welcome_text = (
        f"أهلاً بك يا {message.from_user.first_name} 👋\n\n"
        
        "أنا بوت التحميل الشامل 🤖\n"
        "حمل من يوتيوب، تيك توك، فيسبوك، إنستجرام\n"
        "اضغط بالأسفل لفتح التطبيق 👇"
    )

    markup = types.InlineKeyboardMarkup()
    web_app_info = types.WebAppInfo(APP_URL)
    markup.add(types.InlineKeyboardButton(text="📱 اضغط للتحميل والبحث (Web App)", web_app=web_app_info))
    markup.add(types.InlineKeyboardButton("📢 قناة المطور", url="https://t.me/+8o0uI_JLmYwwZWJk"))
    
    if str(ADMIN_ID) and str(message.from_user.id) == str(ADMIN_ID):
        markup.add(types.InlineKeyboardButton("👮‍♂️ لوحة التحكم", callback_data="admin_main"))

    try:
        with open('start_image.jpg', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=welcome_text, reply_markup=markup)
    except:
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not check_sub(message.from_user.id):
        bot.reply_to(message, "⚠️ يجب الاشتراك في القناة أولاً")
        return

    if "http" in message.text:
        Thread(target=process_url_flow, args=(message.chat.id, message.text)).start()
    else:
        process_web_search(message.chat.id, message.text)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data = call.data
    
    # استقبال التحميل من الويب
    if data.startswith("web_dl|"):
        url = data.split("|")[1]
        process_url_flow(call.message.chat.id, url)
        return

    # --- لوحة التحكم (تم التصحيح هنا) ---
    if data == "admin_main":
        if str(call.from_user.id) != str(ADMIN_ID): return
        
        # ⚠️ مسح الرسالة القديمة (عشان الصورة)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
            types.InlineKeyboardButton("📢 الإذاعة", callback_data="admin_broadcast")
        )
        markup.add(types.InlineKeyboardButton("🔒 اشتراك إجباري", callback_data="admin_ch"))
        markup.add(types.InlineKeyboardButton("❌ إغلاق", callback_data="cancel"))
        
        # إرسال رسالة جديدة
        bot.send_message(call.message.chat.id, "👮‍♂️ لوحة التحكم الرئيسية\n اختر قسماً:", reply_markup=markup)
        return

    if data == "admin_stats":
        count = 0
        if os.path.exists(users_file):
            with open(users_file, "r") as f: count = len(f.readlines())
        bot.answer_callback_query(call.id, f"👥 عدد المستخدمين: {count}", show_alert=True)
        return

    if data == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "📝 أرسل الرسالة التي تريد إذاعتها:")
        bot.register_next_step_handler(msg, start_broadcast)
        return

    if data == "admin_ch":
        msg = bot.send_message(call.message.chat.id, "📝 أرسل معرف القناة (مثل @channel) أو 'off' للإلغاء:")
        bot.register_next_step_handler(msg, set_force_sub)
        return

    if data == "cancel":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    if data.startswith("dl|"):
        mode = data.split("|")[1]
        original_url = ""
        if call.message.caption_entities:
            for entity in call.message.caption_entities:
                if entity.type == "text_link": original_url = entity.url; break
        if not original_url and call.message.caption:
             import re
             urls = re.findall(r'(https?://[^\s]+)', call.message.caption)
             if urls: original_url = urls[0]

        if not original_url:
            bot.answer_callback_query(call.id, "❌ الرابط مفقود")
            return
        
        bot.edit_message_caption(caption=f"🚀 جاري التحميل ({mode})...", chat_id=call.message.chat.id, message_id=call.message.message_id)
        
        try:
            ydl_opts = {'outtmpl': 'media/%(title)s.%(ext)s', 'quiet': True, 'max_filesize': 50*1024*1024, 'nocheckcertificate': True}
            if os.path.exists('cookies.txt'): ydl_opts['cookiefile'] = 'cookies.txt'
            
            if mode == "audio": ydl_opts['format'] = 'bestaudio/best'
            elif mode == "720": ydl_opts['format'] = 'best[height<=720][ext=mp4]/best[ext=mp4]/best'
            elif mode == "480": ydl_opts['format'] = 'best[height<=480][ext=mp4]/best[ext=mp4]/best'
            elif mode == "360": ydl_opts['format'] = 'best[height<=360][ext=mp4]/best[ext=mp4]/best'
            else: ydl_opts['format'] = 'best[ext=mp4]/best'

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(original_url, download=True)
                filename = ydl.prepare_filename(info)
                # caption = f"✅ @kma_tbot"
                
                with open(filename, 'rb') as f:
                    if mode == "audio": bot.send_audio(call.message.chat.id, f, caption=caption)
                    else: bot.send_video(call.message.chat.id, f, caption=caption, supports_streaming=True)
                
                if os.path.exists(filename): os.remove(filename)
                bot.delete_message(call.message.chat.id, call.message.message_id)

        except Exception as e:
            bot.send_message(call.message.chat.id, "❌ فشل التحميل")
            if ADMIN_ID: bot.send_message(ADMIN_ID, f"⚠️ خطأ DL:\n{str(e)}")

    elif data == "search_yt":
         bot.answer_callback_query(call.id, "⚠️ يوتيوب مغلق للصيانة!", show_alert=True)

# دوال التحكم
def start_broadcast(message):
    if message.text == '/start': return
    if os.path.exists(users_file):
        with open(users_file, "r") as f: users = f.read().splitlines()
        count = 0
        for user in users:
            try:
                bot.copy_message(user, message.chat.id, message.message_id)
                count += 1
            except: pass
        bot.send_message(message.chat.id, f"✅ تم الإرسال لـ {count} مستخدم")
    else:
        bot.send_message(message.chat.id, "❌ لا يوجد مستخدمين")

def set_force_sub(message):
    if message.text == '/start': return
    text = message.text.strip()
    if text.lower() == 'off':
        with open(channel_file, "w") as f: f.write("")
        bot.send_message(message.chat.id, "✅ تم إلغاء الاشتراك الإجباري")
    else:
        with open(channel_file, "w") as f: f.write(text)
        bot.send_message(message.chat.id, f"✅ تم تعيين القناة: {text}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'my_chat_member'])
