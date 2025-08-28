import os
import json
import requests
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import feedparser

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

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

# --- Ключевые слова (оптимизированные) ---
KEYWORDS_EN = [
    'metallurgy', 'ferrous metallurgy', 'non-ferrous metallurgy',
    'steel production', 'metal processing', 'additive manufacturing',
    '3D printing metal', 'rare earth metals', 'refractory metals',
    'tungsten', 'molybdenum', 'titanium', 'nickel', 'aluminum',
    'copper', 'lithium', 'cobalt', 'industrial technology',
    'market analysis metals', 'steel market', 'rare earth market',
    'mining', 'industrial innovation', 'digitalization industry',
    'AI in industry', 'robotization of industry'
]

KEYWORDS_RU = [
    'металлургия', 'черная металлургия', 'цветная металлургия',
    'производство стали', 'обработка металлов', 'аддитивные технологии',
    '3D печать металлом', 'редкоземельные металлы', 'тугоплавкие металлы',
    'вольфрам', 'молибден', 'титан', 'никель', 'алюминий',
    'медь', 'литий', 'кобальт', 'промышленные технологии',
    'анализ рынка металлов', 'рынок стали', 'рынок РЗМ',
    'горное дело', 'промышленные инновации', 'цифровизация промышленности',
    'ИИ в промышленности', 'роботизация промышленности'
]

ALL_KEYWORDS = KEYWORDS_RU + KEYWORDS_EN

# --- Поиск новостей за последние 3 дня ---
def search_news():
    articles = []

    # 1. NewsAPI — с фильтром по дате
    if NEWSAPI_KEY:
        # Дата 3 дня назад
        from_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')

        # Группируем ключевые слова
        queries = [
            ' OR '.join(KEYWORDS_EN[:8]),
            ' OR '.join(KEYWORDS_EN[8:16]),
            ' OR '.join(KEYWORDS_EN[16:])
        ]

        for query in queries:
            try:
                url = "https://newsapi.org/v2/everything"
                params = {
                    'q': query,
                    'from': from_date,
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
                    print(f"NewsAPI error {r.status_code}: {r.text} (query: {query[:50]}...)")
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
                    if any(kw.lower() in title for kw in ['metal', 'steel', 'technology', 'industry']):
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
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview
    }
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

# --- Основная функция ---
def main():
    print("🚀 Бот запущен (режим GitHub Actions)")
    try:
        seen_urls = load_cache()
        raw_articles = search_news()
        print(f"Получено статей: {len(raw_articles)}")

        # Фильтруем по ключевым словам
        filtered_articles = []
        for art in raw_articles:
            title = art['title'].lower()
            if any(kw.lower() in title for kw in ALL_KEYWORDS):
                filtered_articles.append(art)

        print(f"После фильтрации: {len(filtered_articles)}")

        # Убираем дубли
        articles = [a for a in filtered_articles if a.get('url') not in seen_urls]

        # Ограничиваем 10–20 новостями
        if len(articles) < 10:
            selected = articles  # меньше 10 — отправляем все
        else:
            selected = articles[:20]  # максимум 20

        print(f"Отправляем: {len(selected)} новостей")

        if not selected:
            print("Нет новых новостей для отправки.")
            return

        # Формируем сообщение
        msg = "📬 *Ежедневный дайджест*\n\n"
        for art in selected:
            title_ru = translate_text(art['title'])
            source = art.get('source', 'Неизвестно')
            msg += f"📌 *{title_ru}*\n🌐 {source}\n🔗 {art['url']}\n\n"

        # Отправляем админу
        if ADMIN_ID:
            send_message(ADMIN_ID, msg, disable_preview=True)

        # Обновляем кеш
        for art in selected:
            url = art.get('url')
            if url:
                seen_urls.add(url)
        save_cache(seen_urls)

        print("✅ Рассылка завершена.")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:500]}"
        print(f"🔴 Ошибка: {error_msg}")
        if ADMIN_ID:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": ADMIN_ID, "text": f"❌ Ошибка: `{error_msg}`"}
            )

# --- Запуск ---
if __name__ == "__main__":
    main()