import re
import sqlite3
import json
import random
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- КОНФИГ ---
BOT_TOKEN = "8798378718:AAGRxt_IwUR0m8a2M97l-5TPn8PhWpcNL9s"
DB_NAME = 'quiz_data.db'
LEARN_DB_NAME = 'learned_quizzes.db'
CHANNEL_ID = "@trassa993"
IMAGES_FOLDER = "images/"

# --- БАЗА ДЛЯ ВОПРОСОВ (инфо-канал) ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            questions TEXT,
            anchors TEXT,
            hashtags TEXT,
            date TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(text, questions, anchors, hashtags=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO posts (text, questions, anchors, hashtags, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (text, json.dumps(questions, ensure_ascii=False), 
          json.dumps(anchors, ensure_ascii=False),
          json.dumps(hashtags, ensure_ascii=False) if hashtags else None,
          datetime.now()))
    conn.commit()
    conn.close()

def get_all_questions_with_hashtags():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT questions, hashtags FROM posts ORDER BY date DESC')
    rows = c.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        questions = json.loads(row[0])
        hashtags = json.loads(row[1]) if row[1] else []
        for q in questions:
            result.append({"question": q, "hashtags": hashtags})
    return result

def get_all_questions():
    """Просто список всех вопросов (без хэштегов)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT questions FROM posts ORDER BY date DESC')
    rows = c.fetchall()
    conn.close()
    
    all_q = []
    for row in rows:
        all_q.extend(json.loads(row[0]))
    return all_q

# --- БАЗА ДЛЯ ВЫУЧЕННЫХ КВИЗОВ ---
def init_learn_db():
    conn = sqlite3.connect(LEARN_DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS learned_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            correct_answer TEXT,
            wrong_answers TEXT,
            source TEXT,
            hashtags TEXT,
            date TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_learned_quiz(question, correct_answer, wrong_answers, source, hashtags=None):
    conn = sqlite3.connect(LEARN_DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO learned_quizzes (question, correct_answer, wrong_answers, source, hashtags, date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (question, correct_answer, json.dumps(wrong_answers, ensure_ascii=False),
          source, json.dumps(hashtags, ensure_ascii=False) if hashtags else None,
          datetime.now()))
    conn.commit()
    conn.close()

def get_learned_quizzes():
    conn = sqlite3.connect(LEARN_DB_NAME)
    c = conn.cursor()
    c.execute('SELECT question, correct_answer, wrong_answers FROM learned_quizzes ORDER BY date DESC')
    rows = c.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            "question": row[0],
            "correct_answer": row[1],
            "wrong_answers": json.loads(row[2]) if row[2] else []
        })
    return result

# --- ЛОГИКА ВОПРОСОВ ---
def extract_questions(text, anchors=None, fallback_mode="character"):
    if anchors is None:
        anchors = []
    
    text = text or ""
    hashtags = re.findall(r'#\w+', text)
    
    # Уровень 0: Вопросы рядом с якорями
    anchor_questions = []
    for anchor in anchors:
        pattern = r'[^.!?]*' + re.escape(anchor) + r'[^.!?]*\?'
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        anchor_questions.extend([m.strip() for m in matches if len(m.strip()) > 5])
    
    if anchor_questions:
        return list(dict.fromkeys(anchor_questions))[:5], hashtags
    
    # Уровень 1: Обычные вопросы
    question_patterns = [
        r'[А-Яа-яA-Za-z0-9 ,\-\(\)"]+\?',
        r'(Кто|Что|Где|Когда|Куда|Откуда|Почему|Зачем|Как|Сколько|Какие?|Чей)\s+[^.!?]+\?',
    ]
    
    found = []
    for pattern in question_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        found.extend([m.strip() for m in matches if len(m.strip()) > 5])
    
    if found:
        return list(dict.fromkeys(found))[:5], hashtags
    
    # Уровень 2: Тупой вопрос
    return [generate_dumb_question(text, fallback_mode, anchors)], hashtags

def generate_dumb_question(text, mode="character", anchors=None):
    anchors = anchors or []
    
    for anchor in anchors:
        if re.search(r'[А-ЯЁ][а-яё]+', anchor):
            return f"Как зовут персонажа {anchor}?"
        elif re.search(r'\d+', anchor):
            return f"Сколько было {anchor}?"
    
    names = re.findall(r'\b([А-ЯЁ][а-яё]+)\b', text)
    numbers = re.findall(r'\b(\d+)\b', text)
    
    if mode == "character" and names:
        return f"Как зовут персонажа {names[0]}?"
    elif mode == "number" and numbers:
        return f"Сколько было {numbers[0]}?"
    else:
        return "О чём этот текст?"

# --- ПАРСИНГ ГОТОВЫХ КВИЗОВ ---
def parse_quiz(text):
    lines = text.strip().split('\n')
    
    question = None
    options = []
    correct_answer = None
    
    for line in lines:
        if '?' in line and not question:
            question = line.strip()
            break
    
    if not question:
        return None
    
    option_patterns = [
        r'[А-Я]\)\s*(.+)',
        r'[А-Я]\.\s*(.+)',
        r'\d+\)\s*(.+)',
        r'\d+\.\s*(.+)',
    ]
    
    for line in lines:
        for pattern in option_patterns:
            match = re.match(pattern, line.strip())
            if match:
                options.append(match.group(1).strip())
                break
    
    if options:
        correct_answer = options[0]
    
    return {
        "question": question,
        "options": options,
        "correct_answer": correct_answer
    }

# --- ПОИСК КАРТИНКИ ---
def find_image(hashtags):
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        return None
    
    for hashtag in hashtags:
        clean_tag = hashtag.replace('#', '').strip()
        for file in os.listdir(IMAGES_FOLDER):
            name, ext = os.path.splitext(file)
            if name.lower() == clean_tag.lower() and ext.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                return os.path.join(IMAGES_FOLDER, file)
    
    return None

# --- ОБРАБОТЧИКИ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для викторин.\n\n"
        "📚 **Режимы работы:**\n"
        "1️⃣ **Инфо-канал** (команда `/mode info`)\n"
        "   → Отправляй текст из инфо-канала, я вытащу вопросы.\n"
        "2️⃣ **Обучение** (команда `/mode learn`)\n"
        "   → Отправляй готовые квизы, я запомню их.\n\n"
        "🎲 `/random` — предложит случайный вопрос с картинкой.\n"
        "📚 `/all` — все вопросы из инфо-канала.\n"
        "📖 `/learned` — все выученные квизы."
    )

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Укажи режим: `/mode info` или `/mode learn`")
        return
    
    mode = context.args[0].lower()
    if mode in ['info', 'learn']:
        context.user_data['mode'] = mode
        await update.message.reply_text(f"✅ Режим переключён на: **{mode}**")
    else:
        await update.message.reply_text("❌ Доступные режимы: `info` или `learn`")

async def set_anchors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        context.user_data['anchors'] = context.args
        await update.message.reply_text(f"✅ Якоря сохранены: {', '.join(context.args)}")
    else:
        await update.message.reply_text("❌ Напиши якоря через пробел, например: `/anchors #фильм Чебурашка`")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Берём текст из любого сообщения (копипаст или пересылка)
    text = update.message.text or update.message.caption or ""
    
    if not text:
        await update.message.reply_text("❌ Отправь мне текст с вопросами (можно скопировать из поста).")
        return
    
    mode = context.user_data.get('mode', 'info')
    
    if mode == 'info':
        anchors = context.user_data.get('anchors', [])
        await update.message.reply_text("🔄 Обрабатываю текст...")
        
        questions, hashtags = extract_questions(text, anchors)
        save_to_db(text, questions, anchors, hashtags)
        
        reply = f"✅ Найдено вопросов: {len(questions)}\n\n"
        for i, q in enumerate(questions, 1):
            reply += f"{i}. {q}\n"
        
        if hashtags:
            reply += f"\n🏷️ Хэштеги: {', '.join(hashtags)}"
        
        await update.message.reply_text(reply)
        context.user_data['anchors'] = []
    
    elif mode == 'learn':
        await update.message.reply_text("🧠 Учусь на тексте...")
        
        quiz_data = parse_quiz(text)
        if quiz_data and quiz_data['question']:
            hashtags = re.findall(r'#\w+', text)
            save_learned_quiz(
                quiz_data['question'],
                quiz_data['correct_answer'],
                quiz_data['options'],
                "скопированный текст",
                hashtags
            )
            
            reply = f"✅ Запомнил вопрос:\n\n{quiz_data['question']}"
            if quiz_data['options']:
                reply += f"\n\n📝 Варианты:\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(quiz_data['options'])])
            if quiz_data['correct_answer']:
                reply += f"\n\n✅ Правильный ответ: {quiz_data['correct_answer']}"
            
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text("❌ Не удалось распознать квиз. Убедись, что есть вопрос и варианты ответов.")

async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все сохранённые вопросы из инфо-канала"""
    questions = get_all_questions()
    
    if not questions:
        await update.message.reply_text("📭 Пока нет сохранённых вопросов.")
        return
    
    reply = "📚 **Все вопросы из инфо-канала:**\n\n"
    for i, q in enumerate(questions[:20], 1):  # показываем последние 20
        reply += f"{i}. {q}\n"
    
    if len(questions) > 20:
        reply += f"\n... и ещё {len(questions) - 20} вопросов"
    
    await update.message.reply_text(reply)

async def show_learned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все выученные квизы"""
    quizzes = get_learned_quizzes()
    if not quizzes:
        await update.message.reply_text("📭 Пока нет выученных квизов.")
        return
    
    reply = "🧠 **Выученные квизы:**\n\n"
    for i, q in enumerate(quizzes[:10], 1):
        reply += f"{i}. {q['question']}\n"
        if q.get('correct_answer'):
            reply += f"   ✅ {q['correct_answer']}\n"
    
    if len(quizzes) > 10:
        reply += f"\n... и ещё {len(quizzes) - 10} квизов"
    
    await update.message.reply_text(reply)

async def random_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предлагает случайный вопрос из инфо-базы"""
    questions = get_all_questions_with_hashtags()
    if not questions:
        await update.message.reply_text("❌ В базе нет вопросов. Сначала отправь мне посты в режиме info!")
        return
    
    quiz = random.choice(questions)
    question = quiz['question']
    hashtags = quiz['hashtags']
    
    image_path = find_image(hashtags) if hashtags else None
    
    if image_path:
        with open(image_path, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"🎲 **Случайный вопрос:**\n\n{question}\n\n🏷️ {', '.join(hashtags) if hashtags else 'без хэштегов'}"
            )
    else:
        await update.message.reply_text(f"🎲 **Случайный вопрос:**\n\n{question}")
    
    keyboard = [
        [InlineKeyboardButton("✅ Опубликовать в канал", callback_data=f"post_{question}")],
        [InlineKeyboardButton("🔄 Другой вопрос", callback_data="random")]
    ]
    await update.message.reply_text(
        "Что делаем?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "random":
        await random_quiz(update, context)
    
    elif data.startswith("post_"):
        question = data.replace("post_", "")
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=question)
            await query.edit_message_text("✅ Квиз опубликован в канале!")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")

# --- ЗАПУСК ---
def main():
    init_db()
    init_learn_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mode", set_mode))
    app.add_handler(CommandHandler("anchors", set_anchors))
    app.add_handler(CommandHandler("random", random_quiz))
    app.add_handler(CommandHandler("all", show_all))
    app.add_handler(CommandHandler("learned", show_learned))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Бот запущен! Нажми Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
