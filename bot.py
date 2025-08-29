import os
import json
import requests
from datetime import datetime
from deep_translator import GoogleTranslator
import feedparser

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")
BOT_COMMAND = os.getenv("BOT_COMMAND", "/start")
KEYWORDS_INPUT = os.getenv("KEYWORDS", "")

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
    if NEWSAPI_KEY and keywords:
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

# --- Отправка в Telegram ---
def send_message(chat_id, text, parse_mode='Markdown', disable_preview=False):
    if not chat_id:
        print("❌ chat_id не задан")
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": not disable_preview
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print(f"✅ Сообщение отправлено в {chat_id}")
        else:
            print(f"❌ Ошибка отправки: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")

# --- Основная функция ---
def main():
    print("🚀 Бот запущен (режим GitHub Actions)")
    seen_urls = load_cache()

    if BOT_COMMAND == "/start":
        msg = (
            "Привет! Я бот для поиска новостей.\n"
            "Доступные команды:\n"
            "🔍 /search — найти новости по ключевым словам\n"
            "📋 /help — помощь"
        )
        if ADMIN_ID:
            send_message(ADMIN_ID, msg)

    elif BOT_COMMAND == "/search":
        if not KEYWORDS_INPUT.strip():
            if ADMIN_ID:
                send_message(ADMIN_ID, "❌ Не указаны ключевые слова для поиска.")
            return

        keywords = [kw.strip().lower() for kw in KEYWORDS_INPUT.split(',') if kw.strip()]
        print(f"🔍 Поиск по: {keywords}")

        raw_articles = search_news(keywords)
        print(f"Получено статей: {len(raw_articles)}")

        if not raw_articles:
            if ADMIN_ID:
                send_message(ADMIN_ID, "❌ Новости не найдены.")
            return

        articles = [a for a in raw_articles if a.get('url') not in seen_urls]
        if not articles:
            if ADMIN_ID:
                send_message(ADMIN_ID, "📭 Новых новостей по вашим словам нет.")
            return

        msg = f"📬 *Новости по запросу:* `{', '.join(keywords)}`\n\n"
        for art in articles[:10]:
            title_ru = translate_text(art['title'])
            source = art.get('source', 'Неизвестно')
            msg += f"📌 *{title_ru}*\n🌐 {source}\n🔗 {art['url']}\n\n"

        if ADMIN_ID:
            send_message(ADMIN_ID, msg, disable_preview=False)

        # Обновляем кеш
        for art in articles:
            url = art.get('url')
            if url:
                seen_urls.add(url)
        save_cache(seen_urls)

    elif BOT_COMMAND == "/help":
        help_msg = (
            "📌 *Помощь*\n\n"
            "Доступные команды:\n"
            "🔸 /start — главное меню\n"
            "🔸 /search — найти новости\n"
            "🔸 /help — эта справка\n\n"
            "Чтобы искать, запустите workflow и укажите:\n"
            "  - command: `/search`\n"
            "  - keywords: `робототехника, AI, 3D печать`"
        )
        if ADMIN_ID:
            send_message(ADMIN_ID, help_msg, parse_mode='Markdown')

    else:
        if ADMIN_ID:
            send_message(ADMIN_ID, f"❌ Неизвестная команда: {BOT_COMMAND}")

    print("✅ Работа завершена.")

# --- Запуск ---
if __name__ == "__main__":
    main()
