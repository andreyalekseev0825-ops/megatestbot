import time
import re
import requests
import threading
import sqlite3
import shutil
import os
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, PollAnswerHandler


# --- КОНФИГИ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@trassa993"
SUGGESTION_LINK = "https://t.me/trassa993?direct"
QUIZZES_DB = 'quizzes.db'
BASE_QUIZZES_DB = 'basequizzes.db'
# --- ID ПОЛЬЗОВАТЕЛЯ ДЛЯ НАПОМИНАНИЙ ---
MEME_ADMIN_ID = "6607609864"  # ЗАМЕНИ НА РЕАЛЬНЫЙ CHAT_ID

HASHTAGS = [
    "#Новое_поколение", "#Игра_бога", "#Идеальный_мир", "#Голос_времени",
    "#Тринадцать_огней", "#Последняя_реальность", "#Сердце_вселенной",
    "#Точка_невозврата", "#Мастерская_47", "#внесезонов"
]
# --- РЕДКОСТИ И НАГРАДЫ ---
RARITY_REWARDS = {
    "common": 1,
    "uncommon": 2,
    "rare": 3,
    "epic": 5,
    "legendary": 10
}

RARITY_EMOJIS = {
    "common": "⬜ Обычный",
    "uncommon": "🟩 Необычный",
    "rare": "🟦 Редкий",
    "epic": "🟪 Эпический",
    "legendary": "🟧 Легендарный"
}

RARITY_EMOJI_ONLY = {
    "common": "⬜",
    "uncommon": "🟩",
    "rare": "🟦",
    "epic": "🟪",
    "legendary": "🟧"
}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    # История викторин
    c.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options TEXT,
            correct_option_id INTEGER,
            hashtag TEXT,
            date TEXT
        )
    ''')
    # Запланированные викторины
    c.execute('''
        CREATE TABLE IF NOT EXISTS scheduled (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            username TEXT,
            question TEXT,
            options TEXT,
            correct_option_id INTEGER,
            hashtag TEXT,
            file_id TEXT,
            publish_time TEXT
        )
    ''')
    # Мемы
    c.execute('''
        CREATE TABLE IF NOT EXISTS memes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            username TEXT,
            file_id TEXT,
            file_type TEXT,
            hashtag TEXT,
            post_text TEXT, 
            publish_time TEXT
        )
    ''')
    
    # --- НОВАЯ ТАБЛИЦА ДЛЯ СТАТИСТИКИ (перенеси СЮДА!) ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS quiz_stats (
            chat_id TEXT PRIMARY KEY,
            score INTEGER DEFAULT 0,
            today_plays INTEGER DEFAULT 0,
            last_play_date TEXT
        )
    ''')

    # --- КАКИЕ ВОПРОСЫ ПОЛЬЗОВАТЕЛЬ УЖЕ ПРОХОДИЛ ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_questions (
            chat_id TEXT,
            question_id INTEGER,
            date TEXT,
            PRIMARY KEY (chat_id, question_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ База данных готова")





# --- ФУНКЦИИ ДЛЯ ВИКТОРИН ---
def save_scheduled(chat_id, username, question, options, correct_option_id, hashtag, file_id, publish_time):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO scheduled (chat_id, username, question, options, correct_option_id, hashtag, file_id, publish_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (chat_id, username, question, options, correct_option_id, hashtag, file_id, publish_time.isoformat()))
    conn.commit()
    conn.close()

def get_due_quizzes():
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('''
        SELECT id, chat_id, question, options, correct_option_id, hashtag, file_id, publish_time
        FROM scheduled WHERE publish_time <= ?
    ''', (now,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_scheduled(quiz_id):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('DELETE FROM scheduled WHERE id = ?', (quiz_id,))
    conn.commit()
    conn.close()

def get_user_scheduled(chat_id):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        SELECT id, question, publish_time FROM scheduled WHERE chat_id = ? ORDER BY publish_time
    ''', (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_scheduled_by_chat_id(chat_id):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        SELECT id, username, question, publish_time FROM scheduled WHERE chat_id = ? ORDER BY publish_time
    ''', (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_scheduled_by_username(username):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        SELECT id, chat_id, username, question, publish_time FROM scheduled WHERE username = ? ORDER BY publish_time
    ''', (username,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_user_scheduled(chat_id, quiz_id=None):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    if quiz_id:
        c.execute('DELETE FROM scheduled WHERE chat_id = ? AND id = ?', (chat_id, quiz_id))
    else:
        c.execute('DELETE FROM scheduled WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()

# --- ФУНКЦИИ ДЛЯ МЕМОВ ---
# --- ФУНКЦИИ ДЛЯ МЕМОВ ---
def save_meme(chat_id, username, file_id, file_type, hashtag, post_text, publish_time):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO memes (chat_id, username, file_id, file_type, hashtag, post_text, publish_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (chat_id, username, file_id, file_type, hashtag, post_text, publish_time.isoformat()))
    conn.commit()
    conn.close()

def get_due_memes():
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('''
        SELECT id, chat_id, file_id, file_type, hashtag, publish_time
        FROM memes WHERE publish_time <= ?
    ''', (now,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_meme(meme_id):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('DELETE FROM memes WHERE id = ?', (meme_id,))
    conn.commit()
    conn.close()

def get_user_memes(chat_id):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        SELECT id, file_type, hashtag, publish_time FROM memes WHERE chat_id = ? ORDER BY publish_time
    ''', (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_user_memes(chat_id, meme_id=None):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    if meme_id:
        c.execute('DELETE FROM memes WHERE chat_id = ? AND id = ?', (chat_id, meme_id))
    else:
        c.execute('DELETE FROM memes WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()

def mark_question_as_played(chat_id, question_id):
    """Отмечает, что пользователь прошёл этот вопрос сегодня"""
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO user_questions (chat_id, question_id, date)
        VALUES (?, ?, ?)
    ''', (chat_id, question_id, datetime.now().date().isoformat()))
    conn.commit()
    conn.close()

def get_played_question_ids(chat_id):
    """Возвращает ID вопросов, которые пользователь уже проходил сегодня"""
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute('''
        SELECT question_id FROM user_questions
        WHERE chat_id = ? AND date = ?
    ''', (chat_id, today))
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def clear_old_user_questions():
    """Очищает записи старше 7 дней (чтобы база не раздувалась)"""
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()
    c.execute('DELETE FROM user_questions WHERE date < ?', (week_ago,))
    conn.commit()
    conn.close()

# --- НАПОМИНАЛКА ---
def get_today_memes_by_time(chat_id, target_hour, target_minute):
    """Проверяет, запланирован ли мем на конкретное время сегодня (UTC)"""
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    
    # Ищем по UTC (без сдвигов)
    now_utc = datetime.now()
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_end = now_utc.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

    print(f"🔍 ИЩУ В БД: chat_id={chat_id}, time={target_hour:02d}:{target_minute:02d} UTC")
    print(f"📅 today_start={today_start}, today_end={today_end}")
    
    c.execute('''
        SELECT id FROM memes 
        WHERE chat_id = ? 
        AND publish_time >= ? 
        AND publish_time <= ?
        AND publish_time LIKE ?
    ''', (chat_id, today_start, today_end, f'%{target_hour:02d}:{target_minute:02d}%'))
    rows = c.fetchall()
    conn.close()
    return rows

def send_reminder(bot_token, chat_id, time_str):
    """Отправляет напоминание пользователю"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        text = f"⚠️ **Напоминание!**\n\nТы ещё не запланировал мем!\n\n🖼️ Используй `/meme` чтобы создать и запланировать мем."
        requests.post(url, data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })
        print(f"✅ Напоминание отправлено на {time_str}")
    except Exception as e:
        print(f"❌ Ошибка отправки напоминания: {e}")
# --- ОТДЕЛЬНЫЙ ПОТОК ДЛЯ НАПОМИНАНИЙ ---
def reminder_loop():
    """Отдельный поток для напоминаний о мемах (по времени UTC+2)"""
    while True:
        try:
            now_utc = datetime.now()
            
            # --- ТВОЁ ВРЕМЯ (UTC+2) ---
            now_user = now_utc + timedelta(hours=2)
            current_hour = now_user.hour
            current_minute = now_user.minute
            today_str = now_user.strftime('%Y-%m-%d')

              # --- ОТЛАДКА: ВСЁ ПИШЕТ В ЛОГИ ---
            print(f"🔄 Проверка: {current_hour:02d}:{current_minute:02d}")
            
            # --- НАПОМИНАЛКИ (ПО ТВОЕМУ ВРЕМЕНИ UTC+2) ---
            reminder_times = [
                {"hour": 16, "minute": 30, "start_remind": 16, "start_minute": 5},  # 17:30 по твоему времени
                {"hour": 17, "minute": 30, "start_remind": 17, "start_minute": 5}, 
                {"hour": 18, "minute": 30, "start_remind": 18, "start_minute": 5}, # 18:30 по твоему времени
                # 19:30 по твоему времени
            ]
            
            for rt in reminder_times:
                # Проверяем, что сейчас время для напоминания (по твоему времени)
                print(f"🔍 Проверка условия: {current_hour} == {rt['start_remind']} and {rt['start_minute']} <= {current_minute} <= {rt['start_minute'] + 20}")
                if current_hour == rt["start_remind"] and rt["start_minute"] <= current_minute <= rt["start_minute"] + 20:
                    
                    # --- ПЕРЕВОДИМ ТВОЁ ВРЕМЯ В UTC (ДЛЯ ПОИСКА В БД) ---
                    # Твоё 17:30 → UTC 15:30 (вычитаем 2 часа)
                    utc_hour = (rt["hour"] - 2) % 24
                    utc_minute = rt["minute"]
                    
                    # Проверяем, есть ли уже мем на это время сегодня
                    existing = get_today_memes_by_time(MEME_ADMIN_ID, utc_hour, utc_minute)
                    print(f"📊 Найдено мемов в БД: {len(existing)}")
                    if not existing:
                        if current_minute % 5 == 0:
                            send_reminder(
                                BOT_TOKEN, 
                                MEME_ADMIN_ID, 
                                f"{rt['hour']:02d}:{rt['minute']:02d} (по твоему времени)"
                            )
                            print(f"⏰ Напоминание отправлено на {rt['hour']:02d}:{rt['minute']:02d}")
            
        except Exception as e:
            print(f"❌ Ошибка в напоминалке: {e}")
        
        time.sleep(60)

# --- ФОНОВЫЙ ПОТОК ---
def scheduler_loop():
    while True:
        try:
            # --- ПРОВЕРКА ВИКТОРИН ---
            due = get_due_quizzes()
            for row in due:
                quiz_id, chat_id, question, options, correct_option_id, hashtag, file_id, publish_time = row
                options_list = options.split('|||') if options else []
                
                try:
                    caption = f"Викторина\n{hashtag}\n\n<a href=\"{SUGGESTION_LINK}\">ТрясЛо №993 | Скинуть что-нибудь в предложку</a>"
                    
                    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                    requests.post(url_photo, data={
                        "chat_id": CHANNEL_ID,
                        "photo": file_id,
                        "caption": caption,
                        "parse_mode": "HTML"
                    })
                    
                    url_poll = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
                    resp = requests.post(url_poll, json={
                        "chat_id": CHANNEL_ID,
                        "question": question,
                        "options": options_list,
                        "type": "quiz",
                        "correct_option_id": correct_option_id,
                        "is_anonymous": True
                    })
                    
                    if resp.json().get('ok'):
                        print(f"✅ Опубликовано: {question[:30]}...")
                    else:
                        print(f"❌ Ошибка: {resp.json()}")
                    
                    delete_scheduled(quiz_id)
                    
                except Exception as e:
                    print(f"❌ Ошибка публикации: {e}")
            
            # --- ПРОВЕРКА МЕМОВ ---
            due_memes = get_due_memes()
            for row in due_memes:
                meme_id, chat_id, file_id, file_type, hashtag, publish_time = row
                try:
                    caption = f"Мем\n{hashtag}\n\n<a href=\"{SUGGESTION_LINK}\">ТрясЛо №993 | Скинуть что-нибудь в предложку</a>"
                    
                    if file_type == 'photo':
                        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                        requests.post(url, data={
                            "chat_id": CHANNEL_ID,
                            "photo": file_id,
                            "caption": caption,
                            "parse_mode": "HTML"
                        })
                    else:
                        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
                        requests.post(url, data={
                            "chat_id": CHANNEL_ID,
                            "video": file_id,
                            "caption": caption,
                            "parse_mode": "HTML"
                        })
                    
                    print(f"✅ Мем опубликован: {hashtag}")
                    delete_meme(meme_id)
                    
                except Exception as e:
                    print(f"❌ Ошибка публикации мема: {e}")
                    
        except Exception as e:
            print(f"❌ Ошибка в планировщике: {e}")
        
        time.sleep(10)

# --- ПАРСИНГИ ---
def parse_datetime(text):
    now = datetime.now()
    
    # --- ТОЛЬКО ВРЕМЯ (20:33) ---
    match = re.search(r'(\d{1,2}):(\d{2})', text)
    if match and not re.search(r'\d{1,2}\.\d{1,2}', text):
        hour, minute = int(match.group(1)), int(match.group(2))
        dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if dt < now:
            dt = dt + timedelta(days=1)
        dt = dt - timedelta(hours=3)
        return dt
    
    # --- ДАТА + ВРЕМЯ (08.07 20:33) ---
    match = re.search(r'(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})', text)
    if match:
        day, month, hour, minute = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
        dt = datetime(now.year, month, day, hour, minute)
        # Если дата уже прошла в этом году — добавляем год
        if dt < now:
            # Проверяем, не сегодня ли это (тогда добавляем день)
            if dt.date() == now.date():
                dt = dt + timedelta(days=1)
            else:
                dt = dt.replace(year=now.year + 1)
        dt = dt - timedelta(hours=3)
        return dt
    
    # --- ДАТА + ВРЕМЯ С ГОДОМ (08.07.2026 20:33) ---
    match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})', text)
    if match:
        day, month, year, hour, minute = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4)), int(match.group(5))
        dt = datetime(year, month, day, hour, minute)
        dt = dt - timedelta(hours=3)
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

def init_base_db():
    conn = sqlite3.connect(BASE_QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS base_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options TEXT,
            correct_option_id INTEGER,
            rarity TEXT DEFAULT 'common',
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База базовых вопросов готова")

def save_base_quiz(question, options, correct_option_id):
    # Определяем редкость
    rarity_roll = random.random()
    
    if rarity_roll < 0.60:
        rarity = "common"
    elif rarity_roll < 0.85:
        rarity = "uncommon"
    elif rarity_roll < 0.95:
        rarity = "rare"
    elif rarity_roll < 0.99:
        rarity = "epic"
    else:
        rarity = "legendary"
    
    conn = sqlite3.connect(BASE_QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO base_quizzes (question, options, correct_option_id, rarity, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (question, options, correct_option_id, rarity, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    print(f"✅ Базовый вопрос сохранён: {question[:30]}... ({rarity})")
    return rarity

def backup_base_quizzes():
    if os.path.exists(BASE_QUIZZES_DB):
        backup_name = f"base_quizzes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(BASE_QUIZZES_DB, backup_name)
        return backup_name
    return None

def backup_quizzes():
    if os.path.exists(QUIZZES_DB):
        backup_name = f"quizzes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(QUIZZES_DB, backup_name)
        return backup_name
    return None

# --- ФУНКЦИИ ДЛЯ СТАТИСТИКИ КВИЗ-ИГРЫ ---
def get_user_stats(chat_id):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('SELECT score, today_plays, last_play_date FROM quiz_stats WHERE chat_id = ?', (chat_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"score": row[0], "today_plays": row[1], "last_play_date": row[2]}
    return {"score": 0, "today_plays": 0, "last_play_date": None}

def update_user_stats(chat_id, score, today_plays, last_play_date):
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO quiz_stats (chat_id, score, today_plays, last_play_date)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            score = excluded.score,
            today_plays = excluded.today_plays,
            last_play_date = excluded.last_play_date
    ''', (chat_id, score, today_plays, last_play_date))
    conn.commit()
    conn.close()

# --- ОБРАБОТЧИКИ ВИКТОРИН ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот для викторин и мемов\n\n"
        "📝 /quiz — создать викторину\n"
        "🖼️ /meme — создать мем\n"
        "📋 /my — мои запланированные викторины\n"
        "📋 /mymemes — мои запланированные мемы\n"
        "🗑️ /cancel_all — отменить все викторины\n"
        "🗑️ /cancelallmemes — отменить все мемы\n"
        "🔍 /view @username — посмотреть викторины другого пользователя\n"
        "🆔 /id — показать свой ID"
    )

async def my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    scheduled = get_user_scheduled(chat_id)
    if not scheduled:
        await update.message.reply_text("📭 У тебя нет запланированных викторин.")
        return
    reply = "📋 **Твои запланированные викторины:**\n\n"
    for idx, (quiz_id, question, publish_time) in enumerate(scheduled, 1):
        dt = datetime.fromisoformat(publish_time) + timedelta(hours=3)
        reply += f"{idx}. {question[:40]}... → {dt.strftime('%d.%m %H:%M')}\n"
        reply += f"   🆔 {quiz_id} | /cancel {quiz_id}\n\n"
    await update.message.reply_text(reply)

async def cancel_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("❌ Укажи ID: `/cancel 123`")
        return
    try:
        quiz_id = int(context.args[0])
        delete_user_scheduled(chat_id, quiz_id)
        await update.message.reply_text(f"✅ Викторина #{quiz_id} отменена.")
    except:
        await update.message.reply_text("❌ Ошибка. ID должен быть числом.")

async def cancel_quiz_by_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    try:
        number = int(update.message.text.split('_')[1])
    except:
        await update.message.reply_text("❌ Использование: `/cancel_1`, `/cancel_2`...")
        return
    scheduled = get_user_scheduled(chat_id)
    if not scheduled:
        await update.message.reply_text("📭 Нет викторин.")
        return
    if number < 1 or number > len(scheduled):
        await update.message.reply_text(f"❌ Викторины #{number} нет. Всего {len(scheduled)}.")
        return
    quiz_id = scheduled[number - 1][0]
    delete_user_scheduled(chat_id, quiz_id)
    await update.message.reply_text(f"✅ Викторина #{number} отменена.")

async def cancel_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    delete_user_scheduled(chat_id)
    await update.message.reply_text("✅ Все викторины отменены.")

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step'] = 'waiting_for_quiz_text'
    await update.message.reply_text(
        "📝 Отправь в формате:\n"
        "`Вопрос (Вариант 1; Вариант 2*; Вариант 3; Вариант 4)`\n"
        "Где * — правильный ответ"
    )

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "без юзернейма"
    await update.message.reply_text(f"🆔 **Твой ID:** `{user_id}`\n👤 **Юзернейм:** @{username}")

async def view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Укажи: `/view @username` или `/view 123456789`")
        return
    target = context.args[0]
    if target.startswith('@'):
        username = target[1:]
        scheduled = get_user_scheduled_by_username(username)
        if not scheduled:
            await update.message.reply_text(f"📭 У @{username} нет викторин.")
            return
        chat_id = scheduled[0][1]
        reply = f"📋 **Викторины @{username}** (`{chat_id}`):\n\n"
        for idx, (quiz_id, _, question, publish_time) in enumerate(scheduled, 1):
            dt = datetime.fromisoformat(publish_time) + timedelta(hours=3)
            reply += f"{idx}. {question[:50]}... → {dt.strftime('%d.%m %H:%M')}\n"
            reply += f"   🆔 {quiz_id}\n\n"
        await update.message.reply_text(reply)
        return
    if target.isdigit():
        scheduled = get_user_scheduled_by_chat_id(target)
        if not scheduled:
            await update.message.reply_text(f"📭 У `{target}` нет викторин.")
            return
        username = scheduled[0][1] if scheduled else "без_юзернейма"
        reply = f"📋 **Викторины @{username}** (`{target}`):\n\n"
        for idx, (quiz_id, _, question, publish_time) in enumerate(scheduled, 1):
            dt = datetime.fromisoformat(publish_time) + timedelta(hours=3)
            reply += f"{idx}. {question[:50]}... → {dt.strftime('%d.%m %H:%M')}\n"
            reply += f"   🆔 {quiz_id}\n\n"
        await update.message.reply_text(reply)
        return
    await update.message.reply_text("❌ Неправильный формат.")

# --- ОБРАБОТЧИКИ МЕМОВ ---
async def start_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step'] = 'waiting_for_meme_media'
    await update.message.reply_text(
        "🖼️ Отправь картинку или видео для мема.\n\n"
        "После загрузки выбери действие."
    )

async def handle_meme_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('step') != 'waiting_for_meme_media':
        return
    
    file_id = None
    file_type = None
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = 'photo'
    elif update.message.video:
        file_id = update.message.video.file_id
        file_type = 'video'
    else:
        await update.message.reply_text("❌ Отправь картинку или видео.")
        return
    
    context.user_data['meme_file_id'] = file_id
    context.user_data['meme_file_type'] = file_type
    context.user_data['step'] = 'waiting_for_meme_hashtag'
    
    keyboard = [
        [InlineKeyboardButton("#мемло", callback_data="meme_h_memlo")],
        [InlineKeyboardButton("#линчфд", callback_data="meme_h_newgen")],
        [InlineKeyboardButton("#МШфд", callback_data="meme_h_igra")],
        [InlineKeyboardButton("#неошафд", callback_data="meme_h_ideal")],
        [InlineKeyboardButton("✏️ Свой", callback_data="meme_h_custom")],
    ]
    
    await update.message.reply_text(
        "🏷️ Выбери основной хэштег для мема:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def meme_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "meme_publish_now":
        file_id = context.user_data.get('meme_file_id')
        file_type = context.user_data.get('meme_file_type')
        hashtag = context.user_data.get('meme_hashtag', '#мемло')
        post_text = context.user_data.get('meme_post_text')

        if not file_id:
            await query.edit_message_text("❌ Ошибка. Начни заново через /meme")
            context.user_data.clear()
            return

        await query.edit_message_text("📤 Публикую мем сейчас...")

        try:
            caption = f"Мем\n{hashtag}"
            if post_text:
                caption += f"\n\n{post_text}"
            caption += f"\n\n<a href=\"{SUGGESTION_LINK}\">ТрясЛо №993 | Скинуть что-нибудь в предложку</a>"

            if file_type == 'photo':
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                requests.post(url, data={
                    "chat_id": CHANNEL_ID,
                    "photo": file_id,
                    "caption": caption,
                    "parse_mode": "HTML"
                })
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
                requests.post(url, data={
                    "chat_id": CHANNEL_ID,
                    "video": file_id,
                    "caption": caption,
                    "parse_mode": "HTML"
                })

            await query.edit_message_text(
                f"✅ Мем ОПУБЛИКОВАН!\n\n"
                f"🏷️ {hashtag}\n"
                f"📝 {post_text if post_text else 'Без текста'}"
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")

        context.user_data.clear()
        return

    if data == "meme_schedule":
        context.user_data['step'] = 'waiting_for_meme_time'
        await query.edit_message_text("📅 **Укажи время публикации** (МСК):\nНапример: `20:33`")
        return

    if data == "meme_cancel":
        await query.edit_message_text("❌ Отменено.")
        context.user_data.clear()
        return

async def handle_meme_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('step') != 'waiting_for_meme_time':
        return
    dt = parse_datetime(update.message.text)
    if dt is None:
        await update.message.reply_text("❌ Не понял формат. Пример: `20:33`")
        return
    now = datetime.now()
    if dt < now:
        await update.message.reply_text("❌ Время уже прошло!")
        return
    chat_id = str(update.effective_user.id)
    username = update.effective_user.username or "без_юзернейма"
    file_id = context.user_data.get('meme_file_id')
    file_type = context.user_data.get('meme_file_type')
    hashtag = context.user_data.get('meme_hashtag', '#мемло')
    post_text = context.user_data.get('meme_post_text')
    save_meme(chat_id, username, file_id, file_type, hashtag, post_text, dt)
    print(f"✅ МЕМ СОХРАНЁН В БД: {dt.isoformat()}, chat_id: {chat_id}")
    msk_time = (dt + timedelta(hours=3)).strftime('%d.%m.%Y в %H:%M')
    delay = int((dt - now).total_seconds())
    await update.message.reply_text(
        f"✅ Мем запланирован на **{msk_time}** МСК!\n"
        f"⏳ Осталось: {delay} сек\n"
        f"🏷️ {hashtag}\n"
        f"📝 {post_text if post_text else 'Без текста'}"
    )
    context.user_data.clear()
    
async def my_memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    memes = get_user_memes(chat_id)
    if not memes:
        await update.message.reply_text("📭 У тебя нет запланированных мемов.")
        return
    reply = "📋 **Твои запланированные мемы:**\n\n"
    for idx, (meme_id, file_type, hashtag, publish_time) in enumerate(memes, 1):
        dt = datetime.fromisoformat(publish_time) + timedelta(hours=3)
        reply += f"{idx}. {file_type} | {hashtag} → {dt.strftime('%d.%m %H:%M')}\n"
        reply += f"   🆔 {meme_id} | /cancelmeme {meme_id}\n\n"
    await update.message.reply_text(reply)

async def cancel_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("❌ Укажи ID: `/cancelmeme 123`")
        return
    try:
        meme_id = int(context.args[0])
        delete_user_memes(chat_id, meme_id)
        await update.message.reply_text(f"✅ Мем #{meme_id} отменён.")
    except:
        await update.message.reply_text("❌ Ошибка.")

async def cancel_meme_by_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    try:
        number = int(update.message.text.split('_')[1])
    except:
        await update.message.reply_text("❌ Использование: `/cancelmeme_1`, `/cancelmeme_2`...")
        return
    memes = get_user_memes(chat_id)
    if not memes:
        await update.message.reply_text("📭 Нет мемов.")
        return
    if number < 1 or number > len(memes):
        await update.message.reply_text(f"❌ Мема #{number} нет. Всего {len(memes)}.")
        return
    meme_id = memes[number - 1][0]
    delete_user_memes(chat_id, meme_id)
    await update.message.reply_text(f"✅ Мем #{number} отменён.")

async def cancel_all_memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    delete_user_memes(chat_id)
    await update.message.reply_text("✅ Все мемы отменены.")

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    chat_id = str(poll_answer.user.id)
    
    quiz_data = context.user_data.get('quiz_question')
    if not quiz_data:
        return
    
    reward = quiz_data.get('reward', 1)
    rarity = quiz_data.get('rarity', 'common')
    
    if poll_answer.option_ids[0] == quiz_data['correct_option_id']:
        stats = get_user_stats(chat_id)
        stats["score"] += reward
        update_user_stats(chat_id, stats["score"], stats["today_plays"], datetime.now().date().isoformat())
        
        emoji = RARITY_EMOJI_ONLY.get(rarity, '')
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Правильно! +{reward} балл{'' if reward == 1 else 'а'} {emoji}"
        )
    else:
        stats = get_user_stats(chat_id)
        stats["score"] -= 1
        update_user_stats(chat_id, stats["score"], stats["today_plays"], datetime.now().date().isoformat())
        await context.bot.send_message(chat_id=chat_id, text="❌ Неправильно! –1 балл")
        
    # --- ОТМЕЧАЕМ ВОПРОС КАК ПРОЙДЕННЫЙ ---
    mark_question_as_played(chat_id, quiz_data.get('question_id'))
    
    context.user_data.pop('quiz_question', None)

# --- БЭКАПЫ ---
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💾 Создаю бэкап...")
    try:
        backup_file = backup_quizzes()
        if not backup_file:
            await update.message.reply_text("❌ База не найдена.")
            return
        with open(backup_file, 'rb') as f:
            await update.message.reply_document(document=f, filename=os.path.basename(backup_file), caption="✅ Бэкап создан!")
        os.remove(backup_file)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def base_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step'] = 'waiting_for_base_quiz_text'
    await update.message.reply_text(
        "📝 Отправь вопрос в формате:\n"
        "`Вопрос (Вариант 1; Вариант 2*; Вариант 3; Вариант 4)`"
    )

async def backup_base_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💾 Создаю бэкап базы вопросов...")
    try:
        backup_file = backup_base_quizzes()
        if not backup_file:
            await update.message.reply_text("❌ База не найдена.")
            return
        with open(backup_file, 'rb') as f:
            await update.message.reply_document(document=f, filename=os.path.basename(backup_file), caption="✅ Бэкап создан!")
        os.remove(backup_file)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# --- ОСНОВНОЙ ОБРАБОТЧИК ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    print(f"📩 Текст: {text}")
    print(f"📍 Шаг: {context.user_data.get('step')}")
    if not text:
        await update.message.reply_text("❌ Отправь текст")
        return
    
    step = context.user_data.get('step')
    
    # --- БАЗОВЫЙ ВОПРОС ---
    if step == 'waiting_for_base_quiz_text':
        parsed = parse_quiz(text)
        if parsed and len(parsed['options']) >= 2:
            save_base_quiz(parsed['question'], '|||'.join(parsed['options']), parsed['correct_option_id'])
            await update.message.reply_text(f"✅ Вопрос сохранён!\n❓ {parsed['question']}")
        else:
            await update.message.reply_text("❌ Неправильный формат.\nНужно: `Вопрос (А; Б*; В; Г)`")
        context.user_data['step'] = None
        return
    
    # --- ТЕКСТ ДЛЯ МЕМА ---
    if step == 'waiting_for_meme_post_text':
        context.user_data['meme_post_text'] = text
        context.user_data['step'] = 'waiting_for_meme_hashtag'
        
        keyboard = [
            [InlineKeyboardButton("✅ Добавить #ФлудНаПМ", callback_data="meme_hashtag_add")],
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="meme_hashtag_skip")]
        ]
        
        await update.message.reply_text(
            f"✅ Текст сохранён:\n\n{text}\n\n"
            "📝 Добавить хэштег #ФлудНаПМ?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # --- ВРЕМЯ ДЛЯ МЕМА ---
    if step == 'waiting_for_meme_time':
        await handle_meme_time(update, context)
        return

    # --- СВОЙ ХЭШТЕГ ДЛЯ МЕМА ---
    if step == 'waiting_for_meme_custom_hashtag':
        text = text.strip()
        if not text.startswith('#'):
            text = '#' + text
        context.user_data['meme_hashtag'] = text
        context.user_data['step'] = 'waiting_for_meme_text'
    
        keyboard = [
            [InlineKeyboardButton("✅ Добавить текст", callback_data="meme_text_yes")],
            [InlineKeyboardButton("⏭️ Без текста", callback_data="meme_text_no")]
        ]
    
        await update.message.reply_text(
            f"✅ Хэштег: {text}\n\n📝 Добавить текст к мему?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
      
    # --- ТЕКСТ ВИКТОРИНЫ ---
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
                f"❓ {parsed['question']}\n"
                f"✅ Правильный ответ: {parsed['options'][parsed['correct_option_id']]}\n\n"
                "🏷️ Выбери хэштег:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ Неправильный формат. Пример: `Вопрос (А; Б*; В; Г)`")
        return
    
    # --- ВРЕМЯ ДЛЯ ВИКТОРИНЫ ---
    if step == 'waiting_for_time':
        dt = parse_datetime(text)
        if dt is None:
            await update.message.reply_text("❌ Не понял формат. Пример: `20:33` или `08.07 20:33`")
            return
        
        now = datetime.now()
        if dt < now:
            await update.message.reply_text("❌ Время уже прошло! Укажи будущее время.")
            return
        
        context.user_data['publish_time'] = dt
        context.user_data['step'] = 'waiting_for_confirmation'
        
        delay = int((dt - now).total_seconds())
        msk_time = (dt + timedelta(hours=3)).strftime('%d.%m.%Y в %H:%M')
        
        keyboard = [
            [InlineKeyboardButton("✅ Запланировать", callback_data="confirm_publish")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_publish")]
        ]
        
        await update.message.reply_text(
            f"📅 **Публикация:** {msk_time} МСК\n"
            f"⏳ **Осталось:** {delay} сек\n\n"
            f"❓ {context.user_data['quiz_data']['question']}\n"
            f"🏷️ {context.user_data['quiz_hashtag']}\n\n"
            "✅ Подтверждаешь?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # --- СВОЙ ХЭШТЕГ ---
    if step == 'waiting_for_custom_hashtag':
        text = text.strip()
        if not text.startswith('#'):
            text = '#' + text
        context.user_data['quiz_hashtag'] = text
        context.user_data['step'] = 'waiting_for_image'
        
        await update.message.reply_text(
            f"✅ Хэштег: {text}\n\n"
            "🖼️ Отправь картинку для поста.\n\n"
            "После картинки выбери действие."
        )
        return
    
    # --- ЛЮБОЙ ДРУГОЙ ТЕКСТ ---
    await update.message.reply_text(
        "❓ Я не понял.\n\n"
        "Команды:\n"
        "/quiz — викторина\n"
        "/meme — мем\n"
        "/my — мои викторины\n"
        "/mymemes — мои мемы\n"
        "/cancel_all — отменить все викторины\n"
        "/cancelallmemes — отменить все мемы\n"
        "/id — мой ID\n"
        "/view @username — викторины пользователя"
    )
# --- КНОПКИ ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    print(f"🔘 Нажата кнопка: {data}")
    
    
    # --- КНОПКИ МЕМА ---
    if data in ["meme_publish_now", "meme_schedule", "meme_cancel"]:
        await meme_button_callback(update, context)
        return
    
    # --- ВЫБОР ХЭШТЕГА (ДЛЯ ВИКТОРИНЫ) ---
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
            "После картинки выбери действие."
        )
        return

    # --- ВЫБОР ХЭШТЕГА ДЛЯ МЕМА ---
    # --- ВЫБОР ХЭШТЕГА ДЛЯ МЕМА ---
    if data.startswith("meme_h_"):
        hashtag = data.replace("meme_h_", "")
     
        if hashtag == "custom":
            context.user_data['step'] = 'waiting_for_meme_custom_hashtag'
            await query.edit_message_text("✏️ Напиши свой хэштег (например, #МойХэштег)")
            return
    
    # Сохраняем основной хэштег
        hashtag_map = {
            "memlo": "#мемло",
            "newgen": "#линчфд",
            "igra": "#МШфд",
            "ideal": "#неошафд",
        }
        context.user_data['meme_hashtag'] = hashtag_map.get(hashtag, "#" + hashtag)
    
        await query.edit_message_text(f"✅ Основной хэштег: {context.user_data['meme_hashtag']}")
    
         # --- СПРАШИВАЕМ ПРО #ФлудНаПМ ---
        context.user_data['step'] = 'waiting_for_meme_flud'
        keyboard = [
            [InlineKeyboardButton("✅ Добавить #ФлудНаПМ", callback_data="meme_flud_yes")],
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="meme_flud_no")]
        ]
        await query.message.reply_text(
            "📝 Добавить хэштег #ФлудНаПМ?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    # --- ДОБАВИТЬ #ФлудНаПМ ---
    if data == "meme_flud_yes":
        context.user_data['meme_flud'] = "#ФлудНаПМ"
        await query.edit_message_text("✅ Хэштег #ФлудНаПМ добавлен!")
        context.user_data['step'] = 'waiting_for_meme_text'
    
        keyboard = [
            [InlineKeyboardButton("✅ Добавить текст", callback_data="meme_text_yes")],
            [InlineKeyboardButton("⏭️ Без текста", callback_data="meme_text_no")]
        ]
        await query.message.reply_text(
            "📝 Добавить текст к мему?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "meme_flud_no":
        context.user_data['meme_flud'] = None
        await query.edit_message_text("⏭️ #ФлудНаПМ пропущен.")
        context.user_data['step'] = 'waiting_for_meme_text'
    
        keyboard = [
            [InlineKeyboardButton("✅ Добавить текст", callback_data="meme_text_yes")],
            [InlineKeyboardButton("⏭️ Без текста", callback_data="meme_text_no")]
        ]
        await query.message.reply_text(
            "📝 Добавить текст к мему?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return


    
    # --- ТЕКСТ ДЛЯ МЕМА ---
    # --- ТЕКСТ ДЛЯ МЕМА ---
    if data == "meme_text_yes":
        context.user_data['step'] = 'waiting_for_meme_post_text'
        await query.edit_message_text(
            "📝 Напиши текст для мема.\n\n"
            "Он будет подписью к картинке/видео."
        )
        return

    if data == "meme_text_no":
        context.user_data['meme_post_text'] = None
        context.user_data['step'] = 'waiting_for_meme_action'
        
        keyboard = [
            [InlineKeyboardButton("✅ Опубликовать сейчас", callback_data="meme_publish_now")],
            [InlineKeyboardButton("⏰ Запланировать на время", callback_data="meme_schedule")],
            [InlineKeyboardButton("❌ Отмена", callback_data="meme_cancel")]
        ]
        
        await query.edit_message_text(
            "⏭️ Без текста.\n\nЧто делаем с мемом?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # --- ЗАПЛАНИРОВАТЬ (ДЛЯ ВИКТОРИНЫ) ---
    if data == "schedule":
        context.user_data['step'] = 'waiting_for_time'
        await query.edit_message_text("📅 **Укажи время публикации** (МСК):\nНапример: `20:33`")
        return
    
    # --- ПОДТВЕРЖДЕНИЕ ПУБЛИКАЦИИ (ДЛЯ ВИКТОРИНЫ) ---
    if data == "confirm_publish":
        chat_id = str(update.effective_user.id)
        username = update.effective_user.username or "без_юзернейма"
        quiz_data = context.user_data.get('quiz_data')
        hashtag = context.user_data.get('quiz_hashtag')
        file_id = context.user_data.get('file_id')
        publish_time = context.user_data.get('publish_time')
        
        if not quiz_data or not hashtag or not file_id or not publish_time:
            await query.edit_message_text("❌ Ошибка. Начни заново через /quiz")
            context.user_data.clear()
            return
        
        save_scheduled(
            chat_id,
            username,
            quiz_data['question'],
            '|||'.join(quiz_data['options']),
            quiz_data['correct_option_id'],
            hashtag,
            file_id,
            publish_time
        )
        
        msk_time = (publish_time + timedelta(hours=3)).strftime('%d.%m.%Y в %H:%M')
        delay = int((publish_time - datetime.now()).total_seconds())
        
        await query.edit_message_text(
            f"✅ Викторина запланирована на **{msk_time}** МСК!\n"
            f"⏳ Осталось: {delay} сек\n"
            f"🏷️ {hashtag}\n"
            "📋 /my — посмотреть все"
        )
        context.user_data.clear()
        return
    
    # --- МОМЕНТАЛЬНАЯ ПУБЛИКАЦИЯ (ДЛЯ ВИКТОРИНЫ) ---
    if data == "publish_now":
        quiz_data = context.user_data.get('quiz_data')
        hashtag = context.user_data.get('quiz_hashtag')
        file_id = context.user_data.get('file_id')
        
        if not quiz_data or not hashtag or not file_id:
            await query.edit_message_text("❌ Ошибка. Начни заново через /quiz")
            context.user_data.clear()
            return
        
        await query.edit_message_text("📤 Публикую викторину сейчас...")
        
        try:
            caption = f"Викторина\n{hashtag}\n\n<a href=\"{SUGGESTION_LINK}\">ТрясЛо №993 | Скинуть что-нибудь в предложку</a>"
            
            url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            requests.post(url_photo, data={
                "chat_id": CHANNEL_ID,
                "photo": file_id,
                "caption": caption,
                "parse_mode": "HTML"
            })
            
            url_poll = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
            resp = requests.post(url_poll, json={
                "chat_id": CHANNEL_ID,
                "question": quiz_data['question'],
                "options": quiz_data['options'],
                "type": "quiz",
                "correct_option_id": quiz_data['correct_option_id'],
                "is_anonymous": True
            })
            
            if resp.json().get('ok'):
                conn = sqlite3.connect(QUIZZES_DB)
                c = conn.cursor()
                c.execute('''
                    INSERT INTO quizzes (question, options, correct_option_id, hashtag, date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (quiz_data['question'], '|||'.join(quiz_data['options']), quiz_data['correct_option_id'], hashtag, datetime.now().isoformat()))
                conn.commit()
                conn.close()
                
                await query.edit_message_text(
                    f"✅ Викторина ОПУБЛИКОВАНА!\n\n"
                    f"❓ {quiz_data['question']}\n"
                    f"🏷️ {hashtag}"
                )
            else:
                await query.edit_message_text(f"❌ Ошибка: {resp.json()}")
                
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")
        
        context.user_data.clear()
        return
    
    # --- ОТМЕНА ---
    if data == "cancel_publish":
        await query.edit_message_text("❌ Отменено.")
        context.user_data.clear()
        return
    
    await query.edit_message_text("❌ Неизвестная команда.")

# --- КАРТИНКА ДЛЯ ВИКТОРИНЫ ---
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('step') != 'waiting_for_image':
        return
    if not update.message.photo:
        await update.message.reply_text("❌ Отправь именно картинку")
        return
    
    photo = update.message.photo[-1]
    context.user_data['file_id'] = photo.file_id
    
    # Получаем данные
    hashtag = context.user_data.get('quiz_hashtag')
    quiz_data = context.user_data.get('quiz_data')
    
    # Формируем подпись БЕЗ текста
    caption = f"Викторина\n{hashtag}\n\n<a href=\"{SUGGESTION_LINK}\">ТрясЛо №993 | Скинуть что-нибудь в предложку</a>"
    context.user_data['caption'] = caption
    
    keyboard = [
        [InlineKeyboardButton("✅ Опубликовать сейчас", callback_data="publish_now")],
        [InlineKeyboardButton("⏰ Запланировать на время", callback_data="schedule")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_publish")]
    ]
    
    await update.message.reply_text(
        f"🖼️ Картинка сохранена!\n\n"
        f"❓ {quiz_data['question'] if quiz_data else '?'}\n"
        f"🏷️ {hashtag}\n\n"
        "Что делаем?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает фото и видео для викторин и мемов"""
    step = context.user_data.get('step')
    
    # Если ждём картинку для викторины
    if step == 'waiting_for_image':
        if not update.message.photo:
            await update.message.reply_text("❌ Для викторины нужна именно картинка (фото).")
            return
        await handle_image(update, context)
        return
    
    # Если ждём медиа для мема
    if step == 'waiting_for_meme_media':
        if not update.message.photo and not update.message.video:
            await update.message.reply_text("❌ Для мема нужна картинка или видео.")
            return
        await handle_meme_media(update, context)
        return
    
    # Если ничего не ждём
    await update.message.reply_text("❌ Я не жду медиа. Используй /quiz или /meme чтобы начать.")

async def show_memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все мемы в БД"""
    conn = sqlite3.connect(QUIZZES_DB)
    c = conn.cursor()
    c.execute('SELECT id, chat_id, publish_time, hashtag FROM memes ORDER BY id DESC LIMIT 10')
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("📭 В БД нет мемов.")
        return
    
    reply = "📋 **Последние 10 мемов в БД:**\n\n"
    for row in rows:
        reply += f"🆔 {row[0]}\n"
        reply += f"📅 {row[2]}\n"
        reply += f"🏷️ {row[3]}\n"
        reply += f"👤 {row[1]}\n\n"
    
    await update.message.reply_text(reply)

async def testrem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет, видит ли бот мемы на 15:30 UTC"""
    hour = 17
    minute = 40
    await update.message.reply_text(f"🔍 Проверяю мемы на {hour:02d}:{minute:02d} UTC...")
    
    existing = get_today_memes_by_time(MEME_ADMIN_ID, hour, minute)
    
    if existing:
        await update.message.reply_text(f"✅ НАЙДЕНО {len(existing)} МЕМОВ! Напоминалка НЕ должна прийти.")
    else:
        await update.message.reply_text("❌ МЕМОВ НЕ НАЙДЕНО. Напоминалка ПРИДЁТ.")

async def quiz_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    today = datetime.now().date().isoformat()
    
    stats = get_user_stats(chat_id)
    
    if stats["last_play_date"] != today:
        stats["today_plays"] = 0
        stats["last_play_date"] = today
        update_user_stats(chat_id, stats["score"], 0, today)
    
    if stats["today_plays"] >= 5:
        await update.message.reply_text("❌ Ты уже прошёл 5 викторин сегодня! Возвращайся завтра.")
        return
    
    # --- ПОЛУЧАЕМ ID ВОПРОСОВ, КОТОРЫЕ УЖЕ ПРОЙДЕНЫ ---
    played_ids = get_played_question_ids(chat_id)
    
    conn = sqlite3.connect(BASE_QUIZZES_DB)
    c = conn.cursor()
    
    if played_ids:
        placeholders = ','.join(['?'] * len(played_ids))
        c.execute(f'''
            SELECT id, question, options, correct_option_id, rarity FROM base_quizzes
            WHERE id NOT IN ({placeholders})
            ORDER BY RANDOM() LIMIT 1
        ''', played_ids)
    else:
        c.execute('SELECT id, question, options, correct_option_id, rarity FROM base_quizzes ORDER BY RANDOM() LIMIT 1')
    
    row = c.fetchone()
    conn.close()
    
    if not row:
        await update.message.reply_text("📭 В базе нет новых вопросов! Ты уже прошёл все. Возвращайся завтра или добавь новые через /basequiz")
        return
    
    question_id, question, options_raw, correct_option_id, rarity = row
    options = options_raw.split('|||') if options_raw else []
    
    reward = RARITY_REWARDS.get(rarity, 1)
    
    context.user_data['quiz_question'] = {
        "question_id": question_id,
        "question": question,
        "options": options,
        "correct_option_id": correct_option_id,
        "reward": reward,
        "rarity": rarity
    }
    
    await update.message.reply_poll(
        question=f"{RARITY_EMOJIS.get(rarity, '')}\n\n{question}",
        options=options,
        type="quiz",
        correct_option_id=correct_option_id,
        is_anonymous=False
    )
    
    stats["today_plays"] += 1
    update_user_stats(chat_id, stats["score"], stats["today_plays"], today)


async def quiz_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    stats = get_user_stats(chat_id)
    today = datetime.now().date().isoformat()
    
    if stats["last_play_date"] != today:
        remaining = 5
    else:
        remaining = 5 - stats["today_plays"]
    
    # Считаем количество вопросов по редкости
    conn = sqlite3.connect(BASE_QUIZZES_DB)
    c = conn.cursor()
    c.execute('''
        SELECT rarity, COUNT(*) FROM base_quizzes GROUP BY rarity
    ''')
    rarity_counts = dict(c.fetchall())
    conn.close()
    
    rarity_text = "\n".join([
        f"{RARITY_EMOJI_ONLY.get(r, '')} {r}: {rarity_counts.get(r, 0)}" 
        for r in ["common", "uncommon", "rare", "epic", "legendary"]
    ])
    
    await update.message.reply_text(
        f"📊 **Твоя статистика:**\n"
        f"🏆 Баллы: {stats['score']}\n"
        f"🎮 Осталось попыток сегодня: {remaining}/5\n"
        f"📅 Обновлено: {stats['last_play_date'] if stats['last_play_date'] else '—'}\n\n"
        f"📚 **Вопросы в базе:**\n{rarity_text}"
    )

async def restore_base_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /restorebase — загрузить бэкап базы вопросов"""

     # --- ПРИНУДИТЕЛЬНЫЙ ОТВЕТ ДЛЯ ОТЛАДКИ ---
    context.user_data['waiting_for_restore'] = True
    print("🔥 restore_base_command вызвана!")
    await update.message.reply_text("🔥 Команда /restorebase получена!")
    
    # Проверяем, есть ли в сообщении документ
    if not update.message.document:
        await update.message.reply_text(
            "❌ Отправь файл базы данных (.db) командой /restorebase\n\n"
            "Пример: отправь файл base_quizzes_backup_20260101_120000.db"
        )
        return
    
    document = update.message.document
    
    # Проверяем расширение
    if not document.file_name.endswith('.db'):
        await update.message.reply_text("❌ Файл должен иметь расширение .db")
        return
    
    # Проверяем размер (максимум 50 МБ)
    if document.file_size > 50 * 1024 * 1024:
        await update.message.reply_text("❌ Файл слишком большой (максимум 50 МБ)")
        return
    
    await update.message.reply_text("📥 Загружаю файл базы вопросов...")
    
    try:
        # Скачиваем файл
        file = await context.bot.get_file(document.file_id)
        file_path = f"restore_base_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        await file.download_to_drive(file_path)
        
        await update.message.reply_text("🔄 Восстанавливаю базу вопросов...")
        
        # Проверяем, что файл — это SQLite база
        try:
            conn = sqlite3.connect(file_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='base_quizzes'")
            if not c.fetchone():
                await update.message.reply_text("❌ Файл не содержит таблицу base_quizzes")
                os.remove(file_path)
                return
            conn.close()
        except:
            await update.message.reply_text("❌ Файл повреждён или это не SQLite база")
            os.remove(file_path)
            return
        
        # Останавливаем бота на секунду, чтобы закрыть соединения
        # Просто заменяем файл
        shutil.copy2(file_path, BASE_QUIZZES_DB)
        
        # Удаляем временный файл
        os.remove(file_path)
        
        # Проверяем, сколько записей загружено
        conn = sqlite3.connect(BASE_QUIZZES_DB)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM base_quizzes')
        count = c.fetchone()[0]
        conn.close()
        
        await update.message.reply_text(
            f"✅ База вопросов успешно восстановлена!\n\n"
            f"📊 Загружено вопросов: {count}\n"
            f"📁 Файл: {document.file_name}\n\n"
            "Теперь можно использовать /basequiz для добавления новых вопросов."
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при восстановлении: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает загруженные документы (файлы)"""
    document = update.message.document
    
    # Проверяем, есть ли в контексте ожидание восстановления
    if context.user_data.get('waiting_for_restore'):
        await restore_base_command(update, context)
        return

    if context.user_data.get('waiting_for_import'):
        await import_quizzes_command(update, context)
        return

    # Если ничего не ждём
    await update.message.reply_text("📄 Файл получен. Используй /restorebase чтобы восстановить базу.")

async def import_quizzes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /import_quizzes — загрузить бэкап и импортировать вопросы в base_quizzes"""

    # --- УСТАНАВЛИВАЕМ ФЛАГ ---
    context.user_data['waiting_for_import'] = True
    await update.message.reply_text("🔥 Команда /import_quizzes получена! Отправь файл .db")

    
    # Проверяем, есть ли файл
    if not update.message.document:
        await update.message.reply_text(
            "❌ Отправь файл quizzes_backup_*.db командой /import_quizzes"
        )
        return
    
    document = update.message.document
    if not document.file_name.endswith('.db'):
        await update.message.reply_text("❌ Файл должен иметь расширение .db")
        return
    
    await update.message.reply_text("📥 Загружаю файл...")
    
    try:
        # Скачиваем файл
        file = await context.bot.get_file(document.file_id)
        file_path = f"import_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        await file.download_to_drive(file_path)
        
        await update.message.reply_text("🔍 Ищу вопросы в файле...")
        
        # Подключаемся к загруженной базе
        conn_import = sqlite3.connect(file_path)
        c_import = conn_import.cursor()
        
        # Проверяем, есть ли таблицы
        tables = []
        c_import.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('scheduled', 'quizzes')")
        tables = [row[0] for row in c_import.fetchall()]
        
        if not tables:
            await update.message.reply_text("❌ В файле нет таблиц scheduled или quizzes")
            conn_import.close()
            os.remove(file_path)
            return
        
        # Подключаемся к основной базе
        conn_main = sqlite3.connect(BASE_QUIZZES_DB)
        c_main = conn_main.cursor()
        
        # Получаем существующие вопросы (чтобы не было дубликатов)
        c_main.execute('SELECT question FROM base_quizzes')
        existing_questions = {row[0] for row in c_main.fetchall()}
        
        imported_count = 0
        skipped_count = 0
        
        # Импортируем из scheduled
        if 'scheduled' in tables:
            c_import.execute('SELECT question, options, correct_option_id FROM scheduled')
            for row in c_import.fetchall():
                question, options, correct_option_id = row
                if question not in existing_questions:
                    c_main.execute('''
                        INSERT INTO base_quizzes (question, options, correct_option_id, date)
                        VALUES (?, ?, ?, ?)
                    ''', (question, options, correct_option_id, datetime.now().isoformat()))
                    imported_count += 1
                    existing_questions.add(question)
                else:
                    skipped_count += 1
        
        # Импортируем из quizzes (история)
        if 'quizzes' in tables:
            c_import.execute('SELECT question, options, correct_option_id FROM quizzes')
            for row in c_import.fetchall():
                question, options, correct_option_id = row
                if question not in existing_questions:
                    c_main.execute('''
                        INSERT INTO base_quizzes (question, options, correct_option_id, date)
                        VALUES (?, ?, ?, ?)
                    ''', (question, options, correct_option_id, datetime.now().isoformat()))
                    imported_count += 1
                    existing_questions.add(question)
                else:
                    skipped_count += 1
        
        conn_main.commit()
        conn_main.close()
        conn_import.close()
        
        # Удаляем временный файл
        os.remove(file_path)
        
        # Проверяем итоговое количество
        conn = sqlite3.connect(BASE_QUIZZES_DB)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM base_quizzes')
        total = c.fetchone()[0]
        conn.close()
        
        await update.message.reply_text(
            f"✅ Импорт завершён!\n\n"
            f"📥 Импортировано новых вопросов: {imported_count}\n"
            f"⏭️ Пропущено дубликатов: {skipped_count}\n"
            f"📊 Всего вопросов в базе: {total}\n\n"
            "Теперь эти вопросы доступны в /quizgame!"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)

async def reset_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает счётчик викторин на сегодня (для тестирования)"""
    chat_id = str(update.effective_user.id)
    
    # Проверяем, есть ли запись
    stats = get_user_stats(chat_id)
    if stats["last_play_date"] == datetime.now().date().isoformat():
        # Если сегодня уже играл — сбрасываем
        update_user_stats(chat_id, stats["score"], 0, datetime.now().date().isoformat())
        await update.message.reply_text(
            f"🔄 Счётчик сброшен!\n\n"
            f"📊 Твоя статистика:\n"
            f"🏆 Баллы: {stats['score']}\n"
            f"🎮 Попыток сегодня: 0/5"
        )
    else:
        await update.message.reply_text(
            f"📊 Ты ещё не играл сегодня.\n"
            f"🎮 Доступно: 5/5 попыток\n"
            f"🏆 Баллы: {stats['score']}"
        )

async def check_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет структуру загруженной базы"""
    
    # Проверяем, есть ли файл в сообщении
    if not update.message.document:
        await update.message.reply_text(
            "❌ Отправь файл .db командой /checkdb\n\n"
            "Пример: /checkdb (с прикреплённым файлом)"
        )
        return
    
    document = update.message.document
    if not document.file_name.endswith('.db'):
        await update.message.reply_text("❌ Файл должен иметь расширение .db")
        return
    
    await update.message.reply_text("📥 Проверяю файл...")
    
    try:
        file = await context.bot.get_file(document.file_id)
        file_path = f"check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        await file.download_to_drive(file_path)
        
        conn = sqlite3.connect(file_path)
        c = conn.cursor()
        
        # Получаем все таблицы
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in c.fetchall()]
        
        reply = "📋 **Таблицы в файле:**\n"
        for t in tables:
            reply += f"• {t}\n"
        
        # Проверяем структуру scheduled и quizzes
        for table in ['scheduled', 'quizzes']:
            if table in tables:
                c.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in c.fetchall()]
                reply += f"\n📌 **{table}:** колонки: {', '.join(columns)}\n"
                
                # Считаем записи
                c.execute(f"SELECT COUNT(*) FROM {table}")
                count = c.fetchone()[0]
                reply += f"   Записей: {count}\n"
        
        conn.close()
        os.remove(file_path)
        
        await update.message.reply_text(reply)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)


        
# --- ЗАПУСК ---
def main():
    init_db()
    init_base_db()
    
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    print("🔄 Планировщик запущен")

    reminder_thread = threading.Thread(target=reminder_loop, daemon=True)
    reminder_thread.start()
    print("⏰ Напоминалка запущена")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CommandHandler("meme", start_meme))
    app.add_handler(CommandHandler("my", my_quizzes))
    app.add_handler(CommandHandler("mymemes", my_memes))
    app.add_handler(CommandHandler("cancel_all", cancel_all))
    app.add_handler(CommandHandler("cancelallmemes", cancel_all_memes))
    app.add_handler(CommandHandler("cancel", cancel_quiz))
    app.add_handler(CommandHandler("cancel", cancel_quiz_by_number))
    app.add_handler(CommandHandler("cancelmeme", cancel_meme))
    app.add_handler(CommandHandler("cancelmeme", cancel_meme_by_number))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("view", view_command))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("basequiz", base_quiz_command))
    app.add_handler(CommandHandler("backupbase", backup_base_command))
    app.add_handler(CommandHandler("testrem", testrem))
    app.add_handler(CommandHandler("quizgame", quiz_game))
    app.add_handler(CommandHandler("quizstats", quiz_stats))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(CommandHandler("restorebase", restore_base_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CommandHandler("import_quizzes", import_quizzes_command))
    app.add_handler(CommandHandler("reset_quiz", reset_quiz))
    app.add_handler(CommandHandler("checkdb", check_db))
    
      # --- МЕДИА (фото и видео) - ТОЛЬКО ОДИН! ---
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    
    # --- ТЕКСТ (только ОДИН!) ---
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("showmemes", show_memes))
  
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
