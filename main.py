import telebot
import yt_dlp
import os
import random
from telebot import types
from flask import Flask, request, jsonify, render_template
from threading import Thread

app = Flask('', template_folder='templates')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def receive_link():
    data = request.json
    url = data.get('url')
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'error', 'msg': 'User ID missing'})

    if ("youtube.com" in url or "youtu.be" in url) and MAINTENANCE_STATUS['youtube']:
        return jsonify({'status': 'maintenance', 'msg': 'يوتيوب في الصيانة حالياً'})

    Thread(target=process_url_flow, args=(user_id, url)).start()
    
    return jsonify({'status': 'ok'})

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

BOT_TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
APP_URL = "https://kareem-live.onrender.com"

MAINTENANCE_STATUS = {
    'youtube': True,
    'facebook': False,
    'instagram': False,
    'tiktok': False
}

if not BOT_TOKEN:
    print("Error: TOKEN is missing.")

bot = telebot.TeleBot(BOT_TOKEN)
users_file = "users.txt"
channel_file = "force_sub.txt"

BLOCKED_KEYWORDS = [
    "xnxx", "pornhub", "xvideos", "sex", "xxx", "nude", "pussy", 
    "dick", "cock", "boobs", "hentai", "milf", "sharmota", "neek", 
    "nik", "sks", "film sex", "سكس", "نيك", "اباحي", "شرموطة", 
    "toz", "kuss"
]

SUCCESS_MSGS = [
    "عاش! تم قفش الرابط بنجاح!",
    "طلبك أوامر، ثواني ويكون عندك...",
    "جاري تغليف الطلب... استعد!",
    "البوت شغال يا وحش... لحظة واحدة!",
    "ولا يهمك، جبنالك الرابط في ثانية!",
    "انت تؤمر.. جاري التحميل..."
]

def is_safe_content(text):
    text = text.lower()
    for word in BLOCKED_KEYWORDS:
        if word in text:
            return False
    return True

def save_and_notify_admin(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    username = message.from_user.username or "No User"
    
    if not os.path.exists(users_file):
        with open(users_file, "w") as f: pass
    with open(users_file, "r") as f:
        users = f.read().splitlines()
    if user_id not in users:
        with open(users_file, "a") as f:
            f.write(user_id + "\n")
        if ADMIN_ID:
            msg = (f"مستخدم جديد انضم للبوت!\nالاسم: {first_name}\n"
                   f"اليوزر: @{username}\nالأيدي: {user_id}")
            try: bot.send_message(ADMIN_ID, msg)
            except: pass
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

def process_url_flow(chat_id, url):
    if not is_safe_content(url):
        bot.send_message(chat_id, "🚫 محتوى محظور!")
        return

    status_msg = bot.send_message(chat_id, f"🔎 وصلني الرابط:\n{url}\n\nجاري الفحص...")
    
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'ignoreerrors': True, 'nocheckcertificate': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            bot.edit_message_text("❌ الرابط لا يعمل أو خاص.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
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
                types.InlineKeyboardButton("🎥 240p", callback_data="dl|240")
            )
            markup.add(
                types.InlineKeyboardButton("🎥 144p", callback_data="dl|144"),
                types.InlineKeyboardButton("🎵 Audio", callback_data="dl|audio")
            )
            markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel"))

            bot.delete_message(chat_id, status_msg.message_id)
            caption_text = f"🎬 {linked_title}\n\n{motivational_msg}\n👇 اختر الجودة:"
            
            if thumbnail:
                bot.send_photo(chat_id, thumbnail, caption=caption_text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(chat_id, caption_text, parse_mode="Markdown", reply_markup=markup)
        
        else:
            bot.edit_message_text(f"{motivational_msg}\n🖼️ جاري تحميل الصور...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            
            ydl_opts_img = {
                'outtmpl': 'media/%(title)s.%(ext)s',
                'quiet': True,
                'max_filesize': 50*1024*1024,
                'nocheckcertificate': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_img) as ydl_img:
                info_img = ydl_img.extract_info(url, download=True)
                filename = ydl_img.prepare_filename(info_img)
                caption = f"✅ @kareemcv"
                
                with open(filename, 'rb') as f:
                    bot.send_photo(chat_id, f, caption=caption)
                
                if os.path.exists(filename): os.remove(filename)
                bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ خطأ: {str(e)}", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_and_notify_admin(message)
    
    welcome_text = (
        f"أهلاً بك يا {message.from_user.first_name}! 👋\n\n"
        "🚀 لتحميل الفيديوهات بشكل أسرع وأشيك:\n"
        "اضغط على الزر بالأسفل لفتح نافذة التحميل 👇"
    )

    markup = types.InlineKeyboardMarkup()
    web_app_info = types.WebAppInfo(APP_URL)
    markup.add(types.InlineKeyboardButton(text="📱 اضغط للتحميل (Web App)", web_app=web_app_info))
    markup.add(types.InlineKeyboardButton("📢 قناة المطور", url="https://t.me/+8o0uI_JLmYwwZWJk"))
    
    current_user = str(message.from_user.id).strip()
    if str(ADMIN_ID) and current_user == str(ADMIN_ID):
        markup.add(types.InlineKeyboardButton("👮‍♂️ لوحة التحكم", callback_data="admin_main"))

    try:
        with open('start_image.jpg', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=welcome_text, reply_markup=markup)
    except:
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_text = message.text
    user_id = message.from_user.id

    if not check_sub(user_id):
        bot.reply_to(message, "⚠️ يجب الاشتراك في القناة أولاً.")
        return

    if "http" in user_text:
        Thread(target=process_url_flow, args=(user_id, user_text)).start()
    else:
        markup = types.InlineKeyboardMarkup(row_width=1)
        yt_text = "🔴 يوتيوب (صيانة)" if MAINTENANCE_STATUS['youtube'] else "✅ يوتيوب"
        markup.add(types.InlineKeyboardButton(yt_text, callback_data="search_yt"))
        bot.reply_to(message, f"🧐 البحث عن: {user_text}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data = call.data
    
    if data == "cancel":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    if data.startswith("dl|"):
        mode = data.split("|")[1]
        
        original_url = ""
        if call.message.reply_to_message:
            original_url = call.message.reply_to_message.text
        elif call.message.caption_entities:
            for entity in call.message.caption_entities:
                if entity.type == "text_link":
                    original_url = entity.url
                    break
        if not original_url and call.message.caption:
             import re
             urls = re.findall(r'(https?://[^\s]+)', call.message.caption)
             if urls: original_url = urls[0]

        if not original_url:
            bot.answer_callback_query(call.id, "❌ الرابط مفقود.")
            return
        
        bot.edit_message_caption(caption=f"🚀 جاري التحميل ({mode})...", chat_id=call.message.chat.id, message_id=call.message.message_id)
        
        try:
            ydl_opts = {
                'outtmpl': 'media/%(title)s.%(ext)s',
                'quiet': True,
                'max_filesize': 50*1024*1024,
                'nocheckcertificate': True
            }
            
            if mode == "audio": ydl_opts['format'] = 'bestaudio/best'
            elif mode == "720": ydl_opts['format'] = 'best[height<=720][ext=mp4]/best[ext=mp4]/best'
            elif mode == "480": ydl_opts['format'] = 'best[height<=480][ext=mp4]/best[ext=mp4]/best'
            elif mode == "360": ydl_opts['format'] = 'best[height<=360][ext=mp4]/best[ext=mp4]/best'
            elif mode == "240": ydl_opts['format'] = 'best[height<=240][ext=mp4]/best[ext=mp4]/best'
            elif mode == "144": ydl_opts['format'] = 'best[height<=144][ext=mp4]/best[ext=mp4]/best'
            else: ydl_opts['format'] = 'best[ext=mp4]/best'

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(original_url, download=True)
                filename = ydl.prepare_filename(info)
                caption = f" BOT ✅ @Kma_tbot"
                
                with open(filename, 'rb') as f:
                    if mode == "audio": bot.send_audio(call.message.chat.id, f, caption=caption)
                    else: bot.send_video(call.message.chat.id, f, caption=caption, supports_streaming=True)
                
                if os.path.exists(filename): os.remove(filename)
                bot.delete_message(call.message.chat.id, call.message.message_id)

        except Exception as e:
            bot.send_message(call.message.chat.id, "❌ فشل التحميل.")

    elif data == "search_yt":
         bot.answer_callback_query(call.id, "⚠️ يوتيوب مغلق للصيانة!", show_alert=True)

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
