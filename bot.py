import os
import json
import requests
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import feedparser
from bs4 import BeautifulSoup

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")
KEYWORDS_INPUT = os.getenv("KEYWORDS", "технологии, космос, AI")  # Из workflow

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

# --- Извлечение текста со страницы ---
def extract_text_from_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        r = requests.get(url, timeout=10, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')

        # Удаляем ненужное
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()

        text = soup.get_text(separator=' ', strip=True)
        return text.lower()
    except Exception as e:
        print(f"❌ Ошибка при парсинге {url}: {e}")
        return ""

# --- Проверка, содержит ли статья ключевые слова в тексте ---
def contains_keywords_in_text(url, keywords):
    text = extract_text_from_url(url)
    return any(kw.lower() in text for kw in keywords)

# --- Поиск новостей ---
def search_news(keywords):
    articles = []

    # 1. NewsAPI
    if NEWSAPI_KEY and keywords:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': ' OR '.join(keywords),
                'sortBy': 'publishedAt',
                'pageSize': 50,
                'apiKey': NEWSAPI_KEY
            }
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                for item in data.get('articles', []):
                    # Проверяем содержимое страницы
                    if contains_keywords_in_text(item['url'], keywords):
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

    # 2. RSS — технические и научные источники
    try:
        feeds = {
            'habr': 'https://habr.com/ru/rss/technology/',
            'nplus1': 'https://nplus1.ru/rss',
            'engineering': 'https://www.engineering.com/rss',
            'techcrunch': 'https://techcrunch.com/feed/',
            'wired': 'https://www.wired.com/feed/rss'
        }
        for name, feed_url in feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.title.lower()
                    if any(kw.lower() in title for kw in keywords):
                        # Проверяем содержимое статьи
                        if contains_keywords_in_text(entry.link, keywords):
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

    # Парсим ключевые слова
    keywords = [kw.strip() for kw in KEYWORDS_INPUT.split(',') if kw.strip()]
    print(f"🔍 Поиск по: {keywords}")

    if not keywords:
        print("❌ Нет ключевых слов для поиска")
        if ADMIN_ID:
            send_message(ADMIN_ID, "❌ Не указаны ключевые слова для поиска.")
        return

    # Статус поиска
    status_msg = "🔍 *Запуск поиска по содержимому сайтов...*\n\n"
    status_msg += "🌐 Источники:\n"
    status_msg += "• NewsAPI\n"
    status_msg += "• Habr, N+1, Engineering.com\n"
    status_msg += "• TechCrunch, Wired\n"
    status_msg += "🔍 Темы: `" + ', '.join(keywords) + "`\n"
    status_msg += "⏳ Поиск может занять 1-2 минуты..."

    if ADMIN_ID:
        send_message(ADMIN_ID, status_msg, disable_preview=False)

    seen_urls = load_cache()
    raw_articles = search_news(keywords)
    print(f"Получено статей: {len(raw_articles)}")

    if not raw_articles:
        print("❌ Новости не найдены.")
        if ADMIN_ID:
            send_message(ADMIN_ID, "❌ Новости по заданным словам не найдены.")
        return

    # Убираем дубли
    articles = [a for a in raw_articles if a.get('url') not in seen_urls]

    if not articles:
        print("Новости уже были показаны ранее.")
        if ADMIN_ID:
            send_message(ADMIN_ID, "📭 Новых новостей по вашим словам нет.")
        return

    # Ограничиваем 20 новостями
    selected = articles[:20]
    print(f"Отправляем: {len(selected)} новостей")

    # Формируем сообщение
    msg = f"🌐 *Новости по запросу:* `{', '.join(keywords)}`\n\n"
    for art in selected:
        title_ru = translate_text(art['title'])
        source = art.get('source', 'Неизвестно')
        msg += f"📌 *{title_ru}*\n🌐 {source}\n🔗 {art['url']}\n\n"

    # Отправляем
    if ADMIN_ID:
        send_message(ADMIN_ID, msg, disable_preview=False)

    # Обновляем кеш
    for art in selected:
        url = art.get('url')
        if url:
            seen_urls.add(url)
    save_cache(seen_urls)

    print("✅ Рассылка завершена.")

# --- Запуск ---
if __name__ == "__main__":
    main()
