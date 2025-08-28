import os
import json
import requests
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import feedparser

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")  # Должен быть числом

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

# --- Ключевые слова ---
KEYWORDS_EN = [
    'metallurgy', 'ferrous', 'non-ferrous', 'steel', 'metal processing',
    'additive manufacturing', '3D printing', 'AM', 'rapid prototyping',
    'artificial intelligence', 'AI', 'machine learning', 'neural network',
    'robotics', 'robot', 'robots', 'robotic', 'automation', 'autonomous',
    'green energy', 'renewable energy', 'solar', 'wind', 'hydrogen', 'battery',
    'new technologies', 'emerging tech', 'innovation',
    'fun tech', 'gaming tech', 'entertainment technology', 'hobby tech'
]

KEYWORDS_RU = [
    'металлургия', 'черная металлургия', 'цветная металлургия',
    'производство стали', 'обработка металлов', 'сталь', 'металл',
    'аддитивные технологии', '3D печать', '3D-печать', 'аддитив',
    'искусственный интеллект', 'ИИ', 'машинное обучение', 'нейросеть',
    'робототехника', 'робот', 'роботы', 'роботиза', 'автоматизация',
    'зелёная энергетика', 'возобновляемая энергия', 'солнечная', 'ветровая',
    'водород', 'батареи', 'аккумуляторы',
    'новые технологии', 'инновации', 'прорывные технологии',
    'технологии для удовольствия', 'игровые технологии', 'развлечения',
    'техника для хобби', 'fun tech'
]

# --- Поиск новостей за 3 дня ---
def search_news():
    articles = []

    if NEWSAPI_KEY:
        from_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')

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
                    print(f"NewsAPI error {r.status_code}: {r.text}")
            except Exception as e:
                print(f"NewsAPI ошибка: {e}")

    # RSS
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
                    if any(kw.lower() in title for kw in ['metal', 'tech', 'ai', 'robot', 'energy']):
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
    try:
        seen_urls = load_cache()
        raw_articles = search_news()
        print(f"Получено статей: {len(raw_articles)}")

        # Фильтруем
        filtered_articles = []
        for art in raw_articles:
            title = art['title'].lower()
            if any(kw.lower() in title for kw in KEYWORDS_RU + KEYWORDS_EN):
                filtered_articles.append(art)

        print(f"После фильтрации: {len(filtered_articles)}")

        # Убираем дубли
        articles = [a for a in filtered_articles if a.get('url') not in seen_urls]

        # Ограничиваем 10–20
        if len(articles) < 10:
            selected = articles
        else:
            selected = articles[:20]

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
            try:
                admin_id_int = int(ADMIN_ID)  # Убедимся, что это число
                send_message(admin_id_int, msg, disable_preview=False)
            except ValueError:
                print(f"❌ ADMIN_ID '{ADMIN_ID}' не является числом")
        else:
            print("❌ ADMIN_ID не задан")

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
        if ADMIN_ID and TOKEN:
            send_message(ADMIN_ID, f"❌ Ошибка: `{error_msg}`")

# --- Запуск ---
if __name__ == "__main__":
    main()
