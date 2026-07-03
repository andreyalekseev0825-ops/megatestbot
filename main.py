import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- КОНФИГ ---
BOT_TOKEN = "8798378718:AAEmRvVmnWBKCDu_sHQY8bvVhclnMwUmnFM"
DB_NAME = 'posts.db'

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            source TEXT,
            date TIMESTAMP
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_text ON posts(text)')
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

def save_post(text, source=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO posts (text, source, date)
            VALUES (?, ?, ?)
        ''', (text, source, datetime.now()))
        conn.commit()
        conn.close()
        print(f"✅ Сохранён текст: {text[:50]}...")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def search_posts(keyword):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            SELECT text, source, date FROM posts
            WHERE text LIKE ?
            ORDER BY date DESC
        ''', (f'%{keyword}%',))
        rows = c.fetchall()
        conn.close()
        print(f"🔍 Найдено записей по запросу '{keyword}': {len(rows)}")
        return rows
    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")
        return []

def get_all_posts():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT text, source, date FROM posts ORDER BY date DESC')
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ Ошибка получения всех постов: {e}")
        return []

def get_stats():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM posts')
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"❌ Ошибка статистики: {e}")
        return 0

# --- ОБРАБОТЧИКИ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для хранения текстов.\n\n"
        "📩 **Просто отправь мне текст** — я сохраню его в базу.\n\n"
        "🔍 `/find <слово>` — найти все посты с этим словом.\n"
        "📚 `/all` — показать все сохранённые посты.\n"
        "📊 `/stats` — сколько всего постов в базе."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or update.message.caption or ""
    if not text:
        await update.message.reply_text("❌ Отправь мне текст для сохранения.")
        return

    if save_post(text):
        await update.message.reply_text("✅ Текст сохранён в базу!")
    else:
        await update.message.reply_text("❌ Ошибка при сохранении текста.")

async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Укажи слово для поиска. Пример: `/find Чебурашка`")
        return

    keyword = " ".join(context.args)
    await update.message.reply_text(f"🔍 Ищу посты со словом: **{keyword}**...")

    results = search_posts(keyword)
    
    if not results:
        await update.message.reply_text(f"📭 Ничего не найдено по запросу: {keyword}")
        return

    reply = f"🔍 **Найдено постов: {len(results)}**\n\n"
    for i, (text, source, date) in enumerate(results[:10], 1):
        preview = text[:100] + "..." if len(text) > 100 else text
        date_str = date.strftime("%d.%m.%Y %H:%M") if date else "неизвестно"
        reply += f"{i}. {preview}\n   📅 {date_str}\n\n"

    if len(results) > 10:
        reply += f"\n... и ещё {len(results) - 10} постов."

    await update.message.reply_text(reply)

async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    posts = get_all_posts()
    if not posts:
        await update.message.reply_text("📭 В базе пока нет постов.")
        return

    reply = "📚 **Все сохранённые посты:**\n\n"
    for i, (text, source, date) in enumerate(posts[:20], 1):
        preview = text[:100] + "..." if len(text) > 100 else text
        date_str = date.strftime("%d.%m.%Y %H:%M") if date else "неизвестно"
        reply += f"{i}. {preview}\n   📅 {date_str}\n\n"

    if len(posts) > 20:
        reply += f"\n... и ещё {len(posts) - 20} постов."

    await update.message.reply_text(reply)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = get_stats()
    await update.message.reply_text(f"📊 **Всего постов в базе:** {count}")

# --- ЗАПУСК ---
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("all", show_all))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен! Сохраняет тексты и ищет по ключевым словам.")
    app.run_polling()

if __name__ == "__main__":
    main()
