import sqlite3
import threading
import time
import re
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- КОНФИГИ ---
BOT_TOKEN = "8798378718:AAEmRvVmnWBKCDu_sHQY8bvVhclnMwUmnFM"
CHANNEL_ID = "@tryaslos"  # ЗАМЕНИ
SUGGESTION_LINK = "https://t.me/trassa993?direct"  # ЗАМЕНИ
DELAY_SECONDS = 60

HASHTAGS = [
    "#Новое_поколение",
    "#Игра_бога",
    "#Идеальный_мир",
    "#Голос_времени",
    "#Тринадцать_огней",
    "#Последняя_реальность",
    "#Сердце_вселенной",
    "#Точка_невозврата",
    "#Мастерская_47",
    "#внесезонов"
]

app_instance = None

# --- ПАРСИНГ ---
def parse_quiz(text):
    match = re.match(r'^(.+?)\s*\((.+)\)\s*$', text.strip())
    if not match:
        return None
    question = match.group(1).strip()
    options = [opt.strip() for opt in match.group(2).split(';') if opt.strip()]
    if len(options) < 2:
        return None
    
    correct_answer = None
    correct_option_id = None
    cleaned = []
    
    for i, opt in enumerate(options):
        if opt.endswith('*'):
            correct_answer = opt[:-1].strip()
            correct_option_id = i
            cleaned.append(correct_answer)
        else:
            cleaned.append(opt)
    
    if correct_option_id is None:
        correct_answer = cleaned[0]
        correct_option_id = 0
    
    return {
        "question": question,
        "options": cleaned,
        "correct_answer": correct_answer,
        "correct_option_id": correct_option_id
    }

# --- ФУНКЦИЯ ПУБЛИКАЦИИ (через requests, без asyncio) ---
def publish_quiz_delayed(chat_id, file_id, quiz_data, hashtag):
    try:
        print(f"⏳ Таймер запущен на {DELAY_SECONDS} секунд")
        time.sleep(DELAY_SECONDS)
        
        print("📤 Начинаю публикацию...")
        
        # 1. Отправляем фото
        url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        caption = f"🎯 ВИКТОРИНА\n{hashtag}\n\n<a href=\"{SUGGESTION_LINK}\">ТрясЛо №993 | Скинуть что-нибудь в предложку</a>"
        
        response = requests.post(
            url_photo,
            data={
                "chat_id": chat_id,
                "photo": file_id,
                "caption": caption,
                "parse_mode": "HTML"
            }
        )
        print(f"📸 Фото: {response.json().get('ok', False)}")
        
        # 2. Отправляем опрос
        url_poll = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
        
        # Формируем варианты в нужном формате
        options_json = [{"text": opt} for opt in quiz_data['options']]
        
        response = requests.post(
            url_poll,
            json={
                "chat_id": chat_id,
                "question": quiz_data['question'],
                "options": quiz_data['options'],
                "type": "quiz",
                "correct_option_id": quiz_data['correct_option_id'],
                "is_anonymous": True
            }
        )
        print(f"📊 Опрос: {response.json().get('ok', False)}")
        
        if response.json().get('ok'):
            print(f"✅ ВИКТОРИНА ОПУБЛИКОВАНА: {quiz_data['question'][:30]}...")
        else:
            print(f"❌ Ошибка API: {response.json()}")
        
    except Exception as e:
        print(f"❌ ОШИБКА ПУБЛИКАЦИИ: {e}")
        import traceback
        traceback.print_exc()

# --- ОБРАБОТЧИКИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот для викторин\n\n"
        "📝 Создать викторину: /quiz\n"
        "После подтверждения викторина опубликуется через 60 секунд"
    )

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step'] = 'waiting_for_quiz_text'
    await update.message.reply_text(
        "📝 Отправь в формате:\n"
        "`Вопрос (Вариант 1; Вариант 2*; Вариант 3; Вариант 4)`\n"
        "Где * — правильный ответ\n\n"
        "Пример:\n"
        "`Как зовут персонажа (Глен; Ашра; Кацпер; Воланд*)`"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        await update.message.reply_text("❌ Отправь текст")
        return
    
    step = context.user_data.get('step')
    
    if step == 'waiting_for_quiz_text':
        parsed = parse_quiz(text)
        if parsed and len(parsed['options']) >= 2:
            context.user_data['quiz_data'] = parsed
            context.user_data['step'] = 'waiting_for_hashtag'
            
            keyboard = []
            for hashtag in HASHTAGS:
                keyboard.append([InlineKeyboardButton(hashtag, callback_data=f"hashtag_{hashtag}")])
            keyboard.append([InlineKeyboardButton("✏️ Свой", callback_data="hashtag_custom")])
            
            await update.message.reply_text(
                f"❓ {parsed['question']}\n\n"
                f"✅ Правильный ответ: {parsed['correct_answer']}\n\n"
                "🏷️ Выбери хэштег:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ Неправильный формат. Пример: `Вопрос (А; Б*; В; Г)`")
        return
    
    # Обычный текст
    await update.message.reply_text("✅ Текст сохранён!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global app_instance
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("hashtag_"):
        hashtag = data.replace("hashtag_", "")
        
        if hashtag == "custom":
            await query.edit_message_text("✏️ Напиши свой хэштег (например, #МойХэштег)")
            context.user_data['step'] = 'waiting_for_custom_hashtag'
            return
        
        quiz_data = context.user_data.get('quiz_data')
        if not quiz_data:
            await query.edit_message_text("❌ Ошибка. Начни заново через /quiz")
            context.user_data.clear()
            return
        
        context.user_data['quiz_hashtag'] = hashtag
        context.user_data['step'] = 'waiting_for_image'
        
        await query.edit_message_text(
            f"✅ Хэштег: {hashtag}\n\n"
            "🖼️ Отправь картинку для поста."
        )
    
    elif data == "confirm_publish":
        quiz_data = context.user_data.get('quiz_data')
        hashtag = context.user_data.get('quiz_hashtag')
        file_id = context.user_data.get('file_id')
        
        if not quiz_data or not hashtag or not file_id:
            await query.edit_message_text("❌ Ошибка. Начни заново через /quiz")
            context.user_data.clear()
            return
        
        # ЗАПУСКАЕМ ТАЙМЕР
        thread = threading.Thread(
            target=publish_quiz_delayed,
            args=[CHANNEL_ID, file_id, quiz_data, hashtag]
        )
        thread.daemon = True
        thread.start()
        
        await query.edit_message_text(
            f"✅ Викторина запланирована!\n\n"
            f"⏳ Опубликую через {DELAY_SECONDS} секунд...\n\n"
            "Никуда не уходи, я вернусь! 🚀"
        )
        
        context.user_data.clear()
    
    elif data == "cancel_publish":
        await query.edit_message_text("❌ Отменено.")
        context.user_data.clear()

async def handle_custom_hashtag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('step') != 'waiting_for_custom_hashtag':
        return
    
    text = update.message.text.strip()
    if not text.startswith('#'):
        text = '#' + text
    
    context.user_data['quiz_hashtag'] = text
    context.user_data['step'] = 'waiting_for_image'
    
    await update.message.reply_text(
        f"✅ Хэштег: {text}\n\n"
        "🖼️ Отправь картинку для поста."
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('step') != 'waiting_for_image':
        return
    
    if not update.message.photo:
        await update.message.reply_text("❌ Отправь именно картинку")
        return
    
    photo = update.message.photo[-1]
    context.user_data['file_id'] = photo.file_id
    
    quiz_data = context.user_data.get('quiz_data')
    hashtag = context.user_data.get('quiz_hashtag')
    
    keyboard = [
        [InlineKeyboardButton("✅ Опубликовать через 60 секунд", callback_data="confirm_publish")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_publish")]
    ]
    
    await update.message.reply_text(
        f"🖼️ Картинка сохранена!\n\n"
        f"❓ {quiz_data['question']}\n"
        f"🏷️ {hashtag}\n\n"
        "Нажми кнопку, чтобы запустить таймер на 60 секунд.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- ЗАПУСК ---
def main():
    global app_instance
    app = Application.builder().token(BOT_TOKEN).build()
    app_instance = app
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", start_quiz))
    
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^#'), handle_custom_hashtag))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Бот запущен!")
    print(f"⏳ Задержка публикации: {DELAY_SECONDS} секунд")
    print(f"📅 Текущее время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    app.run_polling()

if __name__ == "__main__":
    main()
