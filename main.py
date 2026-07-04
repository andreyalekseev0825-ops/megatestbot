import time
import re
import requests
import threading
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- КОНФИГИ ---
BOT_TOKEN = "8798378718:AAEmRvVmnWBKCDu_sHQY8bvVhclnMwUmnFM"
CHANNEL_ID = "@tryaslos"  # ЗАМЕНИ
SUGGESTION_LINK = "https://t.me/trassa993?direct"  # ЗАМЕНИ

HASHTAGS = [
    "#Новое_поколение", "#Игра_бога", "#Идеальный_мир", "#Голос_времени",
    "#Тринадцать_огней", "#Последняя_реальность", "#Сердце_вселенной",
    "#Точка_невозврата", "#Мастерская_47", "#внесезонов"
]

# --- ПАРСИНГ ВРЕМЕНИ (с вычитанием 3 часов) ---
def parse_datetime(text):
    """
    Парсит время из текста и вычитает 3 часа (поправка на UTC).
    Форматы:
    - 20:33 → сегодня в 20:33
    - 15.07 20:33 → 15 июля в 20:33
    - 15.07.2026 20:33 → 15 июля 2026 в 20:33
    """
    now = datetime.now()
    
    # Только время (20:33)
    match = re.search(r'(\d{1,2}):(\d{2})', text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if dt < now:
            dt = dt + timedelta(days=1)
        # ВЫЧИТАЕМ 3 ЧАСА (поправка на UTC)
        dt = dt - timedelta(hours=3)
        return dt
    
    # Дата + время (15.07 20:33)
    match = re.search(r'(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})', text)
    if match:
        day, month, hour, minute = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
        dt = datetime(now.year, month, day, hour, minute)
        # ВЫЧИТАЕМ 3 ЧАСА
        dt = dt - timedelta(hours=3)
        return dt
    
    # Дата + время с годом (15.07.2026 20:33)
    match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})', text)
    if match:
        day, month, year, hour, minute = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4)), int(match.group(5))
        dt = datetime(year, month, day, hour, minute)
        dt = dt - timedelta(hours=3)
        return dt
    
    return None

# --- ПАРСИНГ ВИКТОРИНЫ ---
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

# --- ПУБЛИКАЦИЯ (синхронная) ---
def publish_quiz(chat_id, file_id, quiz_data, hashtag):
    try:
        caption = f"🎯 ВИКТОРИНА\n{hashtag}\n\n<a href=\"{SUGGESTION_LINK}\">ТрясЛо №993 | Скинуть что-нибудь в предложку</a>"
        
        # Отправляем фото
        url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        resp = requests.post(url_photo, data={
            "chat_id": chat_id,
            "photo": file_id,
            "caption": caption,
            "parse_mode": "HTML"
        })
        print(f"📸 Фото: {resp.json().get('ok', False)}")
        
        # Отправляем опрос
        url_poll = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
        resp = requests.post(url_poll, json={
            "chat_id": chat_id,
            "question": quiz_data['question'],
            "options": quiz_data['options'],
            "type": "quiz",
            "correct_option_id": quiz_data['correct_option_id'],
            "is_anonymous": True
        })
        print(f"📊 Опрос: {resp.json().get('ok', False)}")
        
        if resp.json().get('ok'):
            print(f"✅ ВИКТОРИНА ОПУБЛИКОВАНА: {quiz_data['question'][:30]}...")
        else:
            print(f"❌ Ошибка API: {resp.json()}")
            
    except Exception as e:
        print(f"❌ Ошибка публикации: {e}")

# --- ФУНКЦИЯ ДЛЯ ТАЙМЕРА ---
def schedule_publish(chat_id, file_id, quiz_data, hashtag, publish_time):
    """Ждёт до нужного времени и публикует"""
    try:
        now = datetime.now()
        delay = (publish_time - now).total_seconds()
        
        if delay > 0:
            print(f"⏳ Жду {int(delay)} секунд до публикации...")
            time.sleep(delay)
        else:
            print("⚠️ Время уже прошло, публикую сейчас")
        
        publish_quiz(chat_id, file_id, quiz_data, hashtag)
        
    except Exception as e:
        print(f"❌ Ошибка в таймере: {e}")

# --- ОБРАБОТЧИКИ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот для викторин\n\n"
        "📝 /quiz — создать викторину\n"
        "После ввода времени (например, 20:33) бот опубликует в указанное время"
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
    
    # --- ШАГ 1: Принимаем текст викторины ---
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
                f"✅ Правильный ответ: {parsed['options'][parsed['correct_option_id']]}\n\n"
                "🏷️ Выбери хэштег:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ Неправильный формат. Пример: `Вопрос (А; Б*; В; Г)`")
        return
    
    # --- ШАГ 4: Принимаем время ---
    if step == 'waiting_for_time':
        dt = parse_datetime(text)
        if dt:
            now = datetime.now()
            if dt < now:
                await update.message.reply_text(
                    "❌ Время уже прошло! Укажи будущее время.\n"
                    "Пример: `20:33` или `15.07 20:33`"
                )
                return
            
            context.user_data['publish_time'] = dt
            context.user_data['step'] = 'waiting_for_confirmation'
            
            # Показываем МСК время и сколько секунд осталось
            delay = int((dt - now).total_seconds())
            
            keyboard = [
                [InlineKeyboardButton("✅ Запланировать", callback_data="confirm_publish")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_publish")]
            ]
            
            await update.message.reply_text(
                f"📅 **Публикация:** {(dt + timedelta(hours=3)).strftime('%d.%m.%Y в %H:%M')} МСК\n"
                f"⏳ **Осталось:** {delay} секунд\n\n"
                "❓ " + context.user_data['quiz_data']['question'] + "\n"
                "🏷️ " + context.user_data['quiz_hashtag'] + "\n\n"
                "✅ Подтверждаешь?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                "❌ Не понял формат времени.\n\n"
                "Примеры:\n"
                "`20:33` — сегодня в 20:33\n"
                "`15.07 20:33` — 15 июля в 20:33\n"
                "`15.07.2026 20:33` — 15 июля 2026 в 20:33"
            )
        return
    
    # --- Обычный текст (не викторина) ---
    await update.message.reply_text("✅ Текст сохранён!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # --- ШАГ 2: Выбор хэштега ---
    if data.startswith("hashtag_"):
        hashtag = data.replace("hashtag_", "")
        
        if hashtag == "custom":
            await query.edit_message_text("✏️ Напиши свой хэштег (например, #МойХэштег)")
            context.user_data['step'] = 'waiting_for_custom_hashtag'
            return
        
        context.user_data['quiz_hashtag'] = hashtag
        context.user_data['step'] = 'waiting_for_image'
        
        await query.edit_message_text(
            f"✅ Хэштег: {hashtag}\n\n"
            "🖼️ Отправь картинку для поста.\n\n"
            "После картинки укажи время публикации (например, 20:33)"
        )
        return
    
    # --- ШАГ 3: Приём картинки ---
    if data == "image_received":
        context.user_data['step'] = 'waiting_for_time'
        await query.edit_message_text(
            "🖼️ Картинка сохранена!\n\n"
            "📅 **Укажи время публикации** (МСК):\n"
            "Например: `20:33` или `15.07 20:33`"
        )
        return
    
    # --- ШАГ 5: Подтверждение публикации ---
    if data == "confirm_publish":
        quiz_data = context.user_data.get('quiz_data')
        hashtag = context.user_data.get('quiz_hashtag')
        file_id = context.user_data.get('file_id')
        publish_time = context.user_data.get('publish_time')
        
        if not quiz_data or not hashtag or not file_id or not publish_time:
            await query.edit_message_text("❌ Ошибка. Начни заново через /quiz")
            context.user_data.clear()
            return
        
        # Запускаем таймер
        thread = threading.Thread(
            target=schedule_publish,
            args=[CHANNEL_ID, file_id, quiz_data, hashtag, publish_time]
        )
        thread.daemon = True
        thread.start()
        
        delay = int((publish_time - datetime.now()).total_seconds())
        msk_time = (publish_time + timedelta(hours=3)).strftime('%d.%m.%Y в %H:%M')
        
        await query.edit_message_text(
            f"✅ Викторина запланирована на **{msk_time}** МСК!\n\n"
            f"⏳ Осталось: {delay} секунд\n\n"
            "В указанное время она автоматически появится в канале. 🚀"
        )
        
        context.user_data.clear()
        return
    
    if data == "cancel_publish":
        await query.edit_message_text("❌ Публикация отменена.")
        context.user_data.clear()
        return

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
        "🖼️ Отправь картинку для поста.\n\n"
        "После картинки укажи время публикации (например, 20:33)"
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('step') != 'waiting_for_image':
        return
    
    if not update.message.photo:
        await update.message.reply_text("❌ Отправь именно картинку")
        return
    
    photo = update.message.photo[-1]
    context.user_data['file_id'] = photo.file_id
    context.user_data['step'] = 'waiting_for_time'
    
    quiz_data = context.user_data.get('quiz_data')
    hashtag = context.user_data.get('quiz_hashtag')
    
    await update.message.reply_text(
        f"🖼️ Картинка сохранена!\n\n"
        f"❓ {quiz_data['question']}\n"
        f"🏷️ {hashtag}\n\n"
        "📅 **Укажи время публикации** (МСК):\n"
        "Например: `20:33` или `15.07 20:33`"
    )

# --- ЗАПУСК ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", start_quiz))
    
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^#'), handle_custom_hashtag))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Бот запущен!")
    print(f"📅 Текущее время (МСК): {(datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')}")
    app.run_polling()

if __name__ == "__main__":
    main()
