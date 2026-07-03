import sqlite3
import os
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

def backup_db():
    """Создаёт копию базы данных"""
    if os.path.exists(DB_NAME):
        # Создаём копию с временной меткой
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        import shutil
        shutil.copy2(DB_NAME, backup_name)
        return backup_name
    return None

def restore_db(file_path):
    """Восстанавливает базу из загруженного файла"""
    try:
        # Проверяем, что файл существует и это база данных
        if os.path.exists(file_path) and file_path.endswith('.db'):
            # Перемещаем файл на место основной базы
            import shutil
            shutil.copy2(file_path, DB_NAME)
            return True
    except Exception as e:
        print(f"❌ Ошибка восстановления: {e}")
    return False

# --- ОБРАБОТЧИКИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот для хранения и поиска текстов\n\n"
        "📩 Отправь текст — сохраню\n"
        "🔍 /find слово — поиск постов\n"
        "📚 /all — все посты\n"
        "📊 /stats — статистика\n"
        "💾 /backup — скачать бэкап базы\n"
        "📂 /restore — восстановить базу (отправь файл .db)"
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
    
    for i, (text, date_obj) in enumerate(results[:5], 1):
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

async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создаёт бэкап базы и отправляет файл"""
    await update.message.reply_text("💾 Создаю бэкап базы данных...")
    
    backup_file = backup_db()
    if backup_file and os.path.exists(backup_file):
        try:
            # Отправляем файл
            with open(backup_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=f"posts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                    caption="✅ Бэкап базы данных создан!"
                )
            # Удаляем временный файл после отправки
            os.remove(backup_file)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при отправке бэкапа: {e}")
    else:
        await update.message.reply_text("❌ База данных не найдена или пуста")

async def restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает базу из отправленного файла"""
    # Проверяем, есть ли в сообщении документ
    if not update.message.document:
        await update.message.reply_text(
            "❌ Отправь файл базы данных (.db) командой /restore\n\n"
            "Пример: отправь файл posts_backup_20260101_120000.db"
        )
        return
    
    document = update.message.document
    
    # Проверяем расширение файла
    if not document.file_name.endswith('.db'):
        await update.message.reply_text("❌ Файл должен иметь расширение .db")
        return
    
    # Проверяем размер файла (не больше 20 МБ)
    if document.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ Файл слишком большой (максимум 20 МБ)")
        return
    
    await update.message.reply_text("📥 Скачиваю файл базы данных...")
    
    try:
        # Скачиваем файл
        file = await context.bot.get_file(document.file_id)
        file_path = f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        await file.download_to_drive(file_path)
        
        await update.message.reply_text("🔄 Восстанавливаю базу данных...")
        
        # Восстанавливаем базу
        if restore_db(file_path):
            # Удаляем временный файл
            os.remove(file_path)
            await update.message.reply_text("✅ База данных успешно восстановлена!")
            
            # Показываем статистику после восстановления
            posts = get_all()
            await update.message.reply_text(f"📊 Всего постов в базе: {len(posts)}")
        else:
            await update.message.reply_text("❌ Ошибка при восстановлении базы данных")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# --- ЗАПУСК ---
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find))
    app.add_handler(CommandHandler("all", all_posts))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("restore", restore))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save))
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
