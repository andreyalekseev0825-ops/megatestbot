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
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База готова")

def save_post(text):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO posts (text, date) VALUES (?, ?)', 
              (text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"✅ Сохранено: {text[:30]}...")

def search_posts(word):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT text, date FROM posts WHERE text LIKE ? ORDER BY date DESC', 
              (f'%{word}%',))
    rows = c.fetchall()
    conn.close()
    
    result = []
    for text, date_str in rows:
        try:
            date_obj = datetime.fromisoformat(date_str) if date_str else None
        except:
            date_obj = None
        result.append((text, date_obj))
    return result

def get_all():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT text, date FROM posts ORDER BY date DESC')
    rows = c.fetchall()
    conn.close()
    
    result = []
    for text, date_str in rows:
        try:
            date_obj = datetime.fromisoformat(date_str) if date_str else None
        except:
            date_obj = None
        result.append((text, date_obj))
    return result

# --- ОБРАБОТЧИКИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот для хранения и поиска текстов\n\n"
        "📩 Отправь текст — сохраню\n"
        "🔍 /find слово — поиск постов\n"
        "📚 /all — все посты\n"
        "📊 /stats — статистика"
    )

async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        await update.message.reply_text("❌ Отправь мне текст")
        return
    save_post(text)
    await update.message.reply_text("✅ Сохранено!")

async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Напиши: /find слово")
        return
    
    word = " ".join(context.args)
    await update.message.reply_text(f"🔍 Ищу: {word}")
    
    results = search_posts(word)
    if not results:
        await update.message.reply_text(f"❌ Ничего не найдено: {word}")
        return
    
    await update.message.reply_text(f"🔍 **Найдено постов: {len(results)}**")
    
    # Показываем каждый пост отдельно (максимум 5)
    for i, (text, date_obj) in enumerate(results[:5], 1):
        if date_obj:
            date_str = date_obj.strftime("%d.%m.%Y %H:%M")
        else:
            date_str = "???"
        
        header = f"📄 **Пост #{i}** (от {date_str}):\n\n"
        full_text = header + text
        
        # Если текст длинный — разбиваем на части
        if len(full_text) > 4000:
            for chunk in [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(full_text)
    
    if len(results) > 5:
        await update.message.reply_text(f"... и ещё {len(results) - 5} постов. Используй /find с другим словом.")

async def all_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    posts = get_all()
    if not posts:
        await update.message.reply_text("📭 Нет постов")
        return
    
    await update.message.reply_text(f"📚 **Всего постов: {len(posts)}**")
    
    for i, (text, date_obj) in enumerate(posts[:5], 1):
        if date_obj:
            date_str = date_obj.strftime("%d.%m.%Y %H:%M")
        else:
            date_str = "???"
        
        header = f"📄 **Пост #{i}** (от {date_str}):\n\n"
        full_text = header + text
        
        if len(full_text) > 4000:
            for chunk in [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(full_text)
    
    if len(posts) > 5:
        await update.message.reply_text(f"... и ещё {len(posts) - 5} постов. Используй /find для поиска.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    posts = get_all()
    await update.message.reply_text(f"📊 **Всего постов в базе: {len(posts)}**")

# --- ЗАПУСК ---
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find))
    app.add_handler(CommandHandler("all", all_posts))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save))
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
