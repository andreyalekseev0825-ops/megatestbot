import sqlite3
import os
import random
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- КОНФИГ ---
BOT_TOKEN = "8798378718:AAEmRvVmnWBKCDu_sHQY8bvVhclnMwUmnFM"
DB_NAME = 'posts.db'
QUIZZES_DB = 'quizzes.db'
CHANNEL_ID = "@your_channel"  # ЗАМЕНИ НА СВОЙ КАНАЛ

# Список доступных хэштегов
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

# --- БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def init_quizzes_db():
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options TEXT,
            correct_answer TEXT,
            hashtag TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Базы данных готовы")

def save_quiz(question, options, correct_answer, hashtag=None):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO quizzes (question, options, correct_answer, hashtag, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (question, options, correct_answer, hashtag, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"✅ Викторина сохранена: {question[:30]}...")

def get_all_quizzes():
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('SELECT id, question, options, correct_answer, hashtag FROM quizzes ORDER BY date DESC')
    rows = c.fetchall()
    conn.close()
    return rows

def get_random_quiz():
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('SELECT question, options, correct_answer, hashtag FROM quizzes ORDER BY RANDOM() LIMIT 1')
    row = c.fetchone()
    conn.close()
    return row

# --- ПАРСИНГ ВИКТОРИНЫ ---
def parse_quiz(text):
    """
    Парсит текст викторины.
    
    Формат:
    Вопрос?
    Вариант 1
    Вариант 2*
    Вариант 3
    Вариант 4
    
    * — правильный ответ
    """
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    if len(lines) < 3:
        return None
    
    question = lines[0]
    options = []
    correct_answer = None
    
    for line in lines[1:]:
        # Убираем префиксы (А), 1., и т.д.)
        clean_line = re.sub(r'^[А-Яа-яA-Za-z0-9][\)\.]\s*', '', line)
        
        if clean_line.endswith('*'):
            correct_answer = clean_line[:-1].strip()
            options.append(correct_answer)
        else:
            options.append(clean_line)
    
    if not correct_answer and options:
        correct_answer = options[0]
    
    return {
        "question": question,
        "options": options,
        "correct_answer": correct_answer
    }

# --- СОСТОЯНИЯ ДЛЯ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот для викторин\n\n"
        "📝 **Как создать викторину:**\n"
        "1. Напиши `/quiz`\n"
        "2. Отправь вопрос и варианты:\n"
        "   `Вопрос?`\n"
        "   `Вариант 1`\n"
        "   `Вариант 2*` ← * это правильный ответ\n"
        "   `Вариант 3`\n"
        "   `Вариант 4`\n\n"
        "3. Выбери хэштег из предложенных\n"
        "4. Отправь картинку для поста\n"
        "5. Бот опубликует в канал!\n\n"
        "📩 **Просто отправь текст** — сохраню в базу\n"
        "🎲 `/random` — случайная викторина\n"
        "📚 `/all` — все викторины"
    )

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /quiz — начать создание викторины"""
    context.user_data['step'] = 'waiting_for_quiz_text'
    await update.message.reply_text(
        "📝 Отправь вопрос и варианты ответов.\n\n"
        "Формат:\n"
        "`Вопрос?`\n"
        "`Вариант 1`\n"
        "`Вариант 2*` ← * правильный ответ\n"
        "`Вариант 3`\n"
        "`Вариант 4`"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        await update.message.reply_text("❌ Отправь мне текст")
        return
    
    step = context.user_data.get('step')
    
    # --- РЕЖИМ СОЗДАНИЯ ВИКТОРИНЫ ---
    if step == 'waiting_for_quiz_text':
        parsed = parse_quiz(text)
        
        if parsed and len(parsed['options']) >= 2:
            context.user_data['quiz_data'] = parsed
            context.user_data['step'] = 'waiting_for_hashtag'
            
            # Показываем кнопки с хэштегами
            keyboard = []
            for hashtag in HASHTAGS:
                keyboard.append([InlineKeyboardButton(hashtag, callback_data=f"hashtag_{hashtag}")])
            keyboard.append([InlineKeyboardButton("✏️ Свой хэштег", callback_data="hashtag_custom")])
            
            await update.message.reply_text(
                "🏷️ **Выбери хэштег для викторины:**",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось распознать викторину.\n\n"
                "Формат:\n"
                "`Вопрос?`\n"
                "`Вариант 1`\n"
                "`Вариант 2*` ← * правильный ответ\n"
                "`Вариант 3`\n"
                "`Вариант 4`"
            )
        return
    
    # --- ОБЫЧНЫЙ ТЕКСТ (сохраняем в базу) ---
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO posts (text, date) VALUES (?, ?)', 
              (text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Текст сохранён в базу!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("hashtag_"):
        hashtag = data.replace("hashtag_", "")
        
        if hashtag == "custom":
            await query.edit_message_text("✏️ Напиши свой хэштег (например, #МойХэштег)")
            context.user_data['step'] = 'waiting_for_custom_hashtag'
            return
        
        context.user_data['quiz_hashtag'] = hashtag
        context.user_data['step'] = 'waiting_for_image'
        
        await query.edit_message_text(
            f"✅ Хэштег выбран: {hashtag}\n\n"
            "🖼️ Теперь **отправь картинку** для поста.\n"
            "Это будет обложка викторины."
        )

async def handle_custom_hashtag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает кастомный хэштег"""
    if context.user_data.get('step') != 'waiting_for_custom_hashtag':
        return
    
    text = update.message.text.strip()
    if not text.startswith('#'):
        text = '#' + text
    
    context.user_data['quiz_hashtag'] = text
    context.user_data['step'] = 'waiting_for_image'
    
    await update.message.reply_text(
        f"✅ Хэштег сохранён: {text}\n\n"
        "🖼️ Теперь **отправь картинку** для поста.\n"
        "Это будет обложка викторины."
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает картинку для викторины"""
    if context.user_data.get('step') != 'waiting_for_image':
        await update.message.reply_text("ℹ️ Сейчас я не жду картинку. Сначала создай викторину через /quiz")
        return
    
    if not update.message.photo:
        await update.message.reply_text("❌ Отправь именно картинку (фото)")
        return
    
    quiz_data = context.user_data.get('quiz_data')
    hashtag = context.user_data.get('quiz_hashtag')
    
    if not quiz_data or not hashtag:
        await update.message.reply_text("❌ Что-то пошло не так. Попробуй /quiz заново.")
        context.user_data.clear()
        return
    
    # Сохраняем викторину в базу
    save_quiz(
        quiz_data['question'],
        ", ".join(quiz_data['options']),
        quiz_data['correct_answer'],
        hashtag
    )
    
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    await update.message.reply_text("📤 Публикую в канал...")
    
    try:
        caption = f"🎯 ВИКТОРИНА\n{hashtag}\n\nТрясЛо №993 | Скинуть что-нибудь в предложку"
        
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=file_id,
            caption=caption
        )
        
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(quiz_data['options'])])
        quiz_message = f"❓ {quiz_data['question']}\n\n{options_text}"
        
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=quiz_message
        )
        
        await update.message.reply_text("✅ Викторина опубликована в канале!")
        context.user_data.clear()
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при публикации: {e}")

async def random_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quiz = get_random_quiz()
    if not quiz:
        await update.message.reply_text("📭 В базе пока нет викторин")
        return
    
    question, options, correct_answer, hashtag = quiz
    options_list = options.split(", ") if options else []
    
    reply = f"🎲 **Случайная викторина:**\n\n"
    reply += f"❓ {question}\n\n"
    for i, opt in enumerate(options_list, 1):
        reply += f"{i}. {opt}\n"
    reply += f"\n✅ Правильный ответ: {correct_answer}"
    reply += f"\n🏷️ {hashtag}" if hashtag else ""
    
    await update.message.reply_text(reply)

async def all_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = get_all_quizzes()
    if not quizzes:
        await update.message.reply_text("📭 В базе пока нет викторин")
        return
    
    reply = "📚 **Все викторины:**\n\n"
    for i, (id_, question, options, correct, hashtag) in enumerate(quizzes[:10], 1):
        reply += f"{i}. {question[:50]}...\n"
        reply += f"   🏷️ {hashtag}\n" if hashtag else ""
    
    await update.message.reply_text(reply)

# --- ЗАПУСК ---
def main():
    init_db()
    init_quizzes_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CommandHandler("random", random_quiz))
    app.add_handler(CommandHandler("all", all_quizzes))
    
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^#'), handle_custom_hashtag))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
