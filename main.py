import sqlite3
import re
import threading
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = "8798378718:AAEmRvVmnWBKCDu_sHQY8bvVhclnMwUmnFM"
CHANNEL_ID = "@tryaslos"
SUGGESTION_LINK = "https://t.me/trassa993?direct"
QUIZZES_DB = 'quizzes.db'

app_instance = None

def init_db():
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS scheduled (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, options TEXT, correct_option_id INTEGER, hashtag TEXT, file_id TEXT, publish_time TEXT)')
    conn.commit()
    conn.close()

def add_scheduled(question, options, correct_option_id, hashtag, file_id, publish_time):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('INSERT INTO scheduled (question, options, correct_option_id, hashtag, file_id, publish_time) VALUES (?, ?, ?, ?, ?, ?)',
              (question, options, correct_option_id, hashtag, file_id, publish_time.isoformat()))
    conn.commit()
    conn.close()
    print(f"✅ Добавлено в расписание: {question[:30]}... на {publish_time}")

def get_due_quizzes():
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('SELECT id, question, options, correct_option_id, hashtag, file_id, publish_time FROM scheduled WHERE publish_time <= ?', (datetime.now().isoformat(),))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_scheduled(quiz_id):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('DELETE FROM scheduled WHERE id = ?', (quiz_id,))
    conn.commit()
    conn.close()

def parse_datetime(text):
    now = datetime.now()
    match = re.search(r'(\d{1,2}):(\d{2})', text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if dt < now:
            dt = dt + timedelta(days=1)
        return dt
    return None

def parse_quiz(text):
    match = re.match(r'^(.+?)\s*\((.+)\)\s*$', text.strip())
    if not match:
        return None
    question = match.group(1).strip()
    options = [opt.strip() for opt in match.group(2).split(';') if opt.strip()]
    if len(options) < 2:
        return None
    correct_option_id = None
    cleaned = []
    for i, opt in enumerate(options):
        if opt.endswith('*'):
            correct_option_id = i
            cleaned.append(opt[:-1].strip())
        else:
            cleaned.append(opt)
    if correct_option_id is None:
        correct_option_id = 0
    return {"question": question, "options": cleaned, "correct_option_id": correct_option_id}

def check_scheduled():
    while True:
        try:
            due = get_due_quizzes()
            if due:
                print(f"🔄 Найдено {len(due)} викторин для публикации")
            for row in due:
                quiz_id, question, options, correct_option_id, hashtag, file_id, publish_time = row
                try:
                    bot = app_instance.bot
                    caption = f"🎯 ВИКТОРИНА\n{hashtag}\n\n<a href=\"{SUGGESTION_LINK}\">ТрясЛо №993 | Скинуть что-нибудь в предложку</a>"
                    bot.send_photo(chat_id=CHANNEL_ID, photo=file_id, caption=caption, parse_mode="HTML")
                    bot.send_poll(chat_id=CHANNEL_ID, question=question, options=options.split(', '), type="quiz", correct_option_id=correct_option_id, is_anonymous=True)
                    delete_scheduled(quiz_id)
                    print(f"✅ Опубликовано: {question[:30]}...")
                except Exception as e:
                    print(f"❌ Ошибка публикации: {e}")
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")
        time.sleep(30)

async def start(update, context):
    await update.message.reply_text("👋 Бот для викторин. /quiz — создать.")

async def start_quiz(update, context):
    context.user_data['step'] = 'waiting_for_quiz_text'
    await update.message.reply_text("📝 Отправь: `Вопрос (А; Б*; В; Г)`")

async def handle_message(update, context):
    text = update.message.text
    step = context.user_data.get('step')
    if step == 'waiting_for_quiz_text':
        parsed = parse_quiz(text)
        if parsed:
            context.user_data['quiz_data'] = parsed
            context.user_data['step'] = 'waiting_for_hashtag'
            keyboard = [[InlineKeyboardButton(h, callback_data=f"h_{h}")] for h in ["#Новое_поколение", "#Игра_бога", "#Идеальный_мир"]]
            await update.message.reply_text("Выбери хэштег:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ Неверный формат")
        return
    if step == 'waiting_for_time':
        dt = parse_datetime(text)
        if dt:
            context.user_data['publish_time'] = dt
            context.user_data['step'] = 'waiting_for_confirmation'
            keyboard = [[InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")]]
            await update.message.reply_text(f"📅 {dt.strftime('%d.%m.%Y в %H:%M')} МСК\nПодтверждаешь?", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ Введи время: 20:33")
        return

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('h_'):
        context.user_data['quiz_hashtag'] = data[2:]
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text("🖼️ Отправь картинку")
    elif data == 'confirm':
        quiz = context.user_data.get('quiz_data')
        hashtag = context.user_data.get('quiz_hashtag')
        file_id = context.user_data.get('file_id')
        publish_time = context.user_data.get('publish_time')
        if quiz and hashtag and file_id and publish_time:
            add_scheduled(quiz['question'], ', '.join(quiz['options']), quiz['correct_option_id'], hashtag, file_id, publish_time)
            await query.edit_message_text(f"✅ Запланировано на {publish_time.strftime('%d.%m %H:%M')}")
        else:
            await query.edit_message_text("❌ Ошибка")

async def handle_image(update, context):
    if context.user_data.get('step') == 'waiting_for_image' and update.message.photo:
        context.user_data['file_id'] = update.message.photo[-1].file_id
        context.user_data['step'] = 'waiting_for_time'
        await update.message.reply_text("📅 Введи время: 20:33")

def main():
    global app_instance
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app_instance = app
    threading.Thread(target=check_scheduled, daemon=True).start()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
