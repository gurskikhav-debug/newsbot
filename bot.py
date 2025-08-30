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
KEYWORDS_INPUT = os.getenv("KEYWORDS", "технологии, изобретения, AI")  # Из workflow

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

# --- Ключевые слова для технических признаков ---
TECH_INDICATORS = [
    'характеристики', 'свойства', 'применение', 'используется в', 'технология', 'изобретение',
    'новинка', 'разработка', 'физическое явление', 'эффект', 'механизм', 'работа', 'принцип',
    'улучшение', 'совершенствование', 'производительность', 'эффективность', 'инновация',
    'влияние на рынок', 'рыночный потенциал', 'экономия', 'автоматизация', 'робот',
    'material properties', 'technical specifications', 'application in engineering',
    'physical phenomenon', 'innovation', 'market impact', 'improvement', 'efficiency'
]

# --- Извлечение текста со страницы ---
def extract_text_from_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        r = requests.get(url, timeout=15, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return text.lower()
    except Exception as e:
        print(f"❌ Ошибка при парсинге {url}: {e}")
        return ""

# --- Проверка, содержит ли статья признаки технической информации ---
def is_technical_article(text):
    return any(indicator in text for indicator in [w.lower() for w in TECH_INDICATORS])

# --- Поиск новостей за 7 дней ---
def search_news(keywords):
    articles = []

    # 1. NewsAPI — за 7 дней
    if NEWSAPI_KEY and keywords:
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': ' OR '.join(keywords),
                'from': from_date,
                'sortBy': 'publishedAt',
                'pageSize': 50,
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

    # 2. RSS — научные и технические источники
    try:
        feeds = {
            'habr': 'https://habr.com/ru/rss/technology/',
            'nplus1': 'https://nplus1.ru/rss',
            'engineering': 'https://www.engineering.com/rss',
            'techcrunch': 'https://techcrunch.com/feed/',
            'wired': 'https://www.wired.com/feed/rss',
            'xinhua': 'http://www.xinhuanet.com/rss/world.xml',
            'sina': 'https://rss.sina.com.cn/news/china.xml'
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

    # 3. YouTube (через RSS)
    try:
        yt_rss = f"https://www.youtube.com/feeds/videos.xml?user=TechInsider"
        feed = feedparser.parse(yt_rss)
        for entry in feed.entries:
            title = entry.title.lower()
            if any(kw.lower() in title for kw in keywords):
                desc = entry.description.lower()
                if is_technical_article(desc):
                    articles.append({
                        'title': entry.title,
                        'url': entry.link,
                        'source': 'YouTube',
                        'published': entry.get('published', 'Неизвестно')
                    })
    except Exception as e:
        print(f"Ошибка YouTube: {e}")

    # 4. Дзен, Telegram, Instagram — через RSS или API (упрощённо)
    try:
        zen_feeds = [
            'https://zen.yandex.ru/rss/technologies',
            'https://zen.yandex.ru/rss/science'
        ]
        for feed_url in zen_feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.title.lower()
                    if any(kw.lower() in title for kw in keywords):
                        articles.append({
                            'title': entry.title,
                            'url': entry.link,
                            'source': 'Дзен',
                            'published': entry.get('published', 'Неизвестно')
                        })
            except Exception as e:
                print(f"Ошибка Дзен: {e}")
    except Exception as e:
        print(f"Ошибка Дзен: {e}")

    return articles

# --- Отправка в Telegram ---
def send_message(chat_id, text, parse_mode='HTML', disable_preview=False):
    if not chat_id:
        print("❌ chat_id не задан")
        return
    try:
        # Экранирование для HTML
        text = text.replace('<', '<').replace('>', '>')
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

    seen_urls = load_cache()
    raw_articles = search_news(keywords)
    print(f"Получено статей: {len(raw_articles)}")

    if not raw_articles:
        print("❌ Новости не найдены.")
        if ADMIN_ID:
            send_message(ADMIN_ID, "❌ Новости по заданным словам не найдены.")
        return

    # Фильтруем по содержимому и техническим признакам
    filtered_articles = []
    for art in raw_articles:
        text = extract_text_from_url(art['url'])
        if any(kw.lower() in text for kw in keywords) and is_technical_article(text):
            filtered_articles.append(art)

    print(f"После фильтрации по техническим признакам: {len(filtered_articles)}")

    # Убираем дубли
    articles = [a for a in filtered_articles if a.get('url') not in seen_urls]

    # Ограничиваем 20 новостями
    selected = articles[:20]
    print(f"Отправляем: {len(selected)} новостей")

    if not selected:
        print("Нет подходящих новостей.")
        if ADMIN_ID:
            send_message(ADMIN_ID, "📭 Нет технических новостей по вашим словам.")
        return

    # Формируем сообщение
    msg = f"<b>🔧 Технические новости за неделю по запросу:</b> <code>{', '.join(keywords)}</code>\n\n"
    for art in selected:
        title_ru = translate_text(art['title'])
        source = art.get('source', 'Неизвестно')
        msg += f"📌 <b>{title_ru}</b>\n"
        msg += f"🌐 {source}\n"
        msg += f"🔗 <a href='{art['url']}'>Ссылка</a>\n\n"

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
