import os
import json
import requests
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import feedparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# --- Состояния ---
AWAITING_KEYWORDS = "awaiting_keywords"

# --- Кеш ---
CACHE_FILE = "cache/news_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except Exception as e:
            print(f"Ошибка чтения кеша: {e}")
    return set()

def save_cache(cache_set):
    os.makedirs("cache", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(cache_set), f, ensure_ascii=False, indent=2)

# --- Перевод ---
def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ru').translate(text)
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        return text

# --- Поиск новостей ---
def search_news(keywords):
    articles = []

    # 1. NewsAPI
    if NEWSAPI_KEY:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': ' OR '.join(keywords),
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 20,
                'apiKey': NEWSAPI_KEY
            }
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                for item in data.get('articles', []):
                    articles.append({
                        'title': item['title'],
                        'url': item['url'],
                        'source': item['source']['name'],
                        'published': item.get('publishedAt', 'Неизвестно')
                    })
            else:
                print(f"NewsAPI error {r.status_code}: {r.text}")
        except Exception as e:
            print(f"NewsAPI ошибка: {e}")

    # 2. RSS из Китая
    try:
        feeds = {
            'xinhua': 'http://www.xinhuanet.com/rss/world.xml',
            'sina': 'https://rss.sina.com.cn/news/china.xml',
            'sohu': 'http://rss.news.sohu.com/rss2/news.xml'
        }
        for name, feed_url in feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.title.lower()
                    if any(kw.lower() in title for kw in keywords):
                        articles.append({
                            'title': entry.title,
                            'url': entry.link,
                            'source': name,
                            'published': entry.get('published', 'Неизвестно')
                        })
            except Exception as e:
                print(f"Ошибка RSS {name}: {e}")
    except Exception as e:
        print(f"Ошибка парсинга RSS: {e}")

    # 3. Технические сайты
    try:
        tech_feeds = {
            'habr': 'https://habr.com/ru/rss/technology/',
            'techcrunch': 'https://techcrunch.com/feed/',
            'wired': 'https://www.wired.com/feed/rss'
        }
        for name, feed_url in tech_feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.title.lower()
                    if any(kw.lower() in title for kw in keywords):
                        articles.append({
                            'title': entry.title,
                            'url': entry.link,
                            'source': name,
                            'published': entry.get('published', 'Неизвестно')
                        })
            except Exception as e:
                print(f"Ошибка RSS {name}: {e}")
    except Exception as e:
        print(f"Ошибка технических RSS: {e}")

    return articles

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Найти новости", callback_data='manual_search')],
        [InlineKeyboardButton("📋 Помощь", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот для поиска новостей.\nВыберите действие:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'manual_search':
        await query.edit_message_text("Введите **ключевые слова** для поиска.\nНапример: `робототехника, 3D печать`")
        context.user_data['state'] = AWAITING_KEYWORDS

    elif query.data == 'help':
        await query.edit_message_text(
            "Используйте:\n"
            "🔍 Найти новости — ищите по теме\n"
            "Все новости с переводом на русский.\n"
            "Поиск ведётся по всем доступным источникам."
        )

async def handle_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != AWAITING_KEYWORDS:
        return

    keywords_input = update.message.text.strip()
    if not keywords_input:
        await update.message.reply_text("Введите хотя бы одно слово.")
        return

    keywords = [kw.strip().lower() for kw in keywords_input.split(',') if kw.strip()]
    await update.message.reply_text(f"🔍 Ищу новости по: *{', '.join(keywords)}*...", parse_mode='Markdown')

    # Поиск
    raw_articles = search_news(keywords)
    print(f"Получено статей: {len(raw_articles)}")

    if not raw_articles:
        await update.message.reply_text("❌ Новости не найдены.")
        context.user_data['state'] = None
        return

    # Убираем дубли
    seen_urls = load_cache()
    articles = [a for a in raw_articles if a.get('url') not in seen_urls]

    if not articles:
        await update.message.reply_text("Новости уже были показаны ранее.")
        context.user_data['state'] = None
        return

    # Показываем первые 10
    for art in articles[:10]:
        title_ru = translate_text(art['title'])
        source = art.get('source', 'Неизвестно')
        msg = f"📌 *{title_ru}*\n🌐 {source}\n🔗 {art['url']}"
        await update.message.reply_text(msg, parse_mode='Markdown', disable_web_page_preview=False)

    # Обновляем кеш
    for art in articles:
        url = art.get('url')
        if url:
            seen_urls.add(url)
    save_cache(seen_urls)

    context.user_data['state'] = None

# --- Запуск ---
if __name__ == "__main__":
    print("🚀 Бот запущен в режиме Telegram polling")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keywords))

    application.run_polling()
