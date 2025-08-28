import os
import json
import requests
from datetime import datetime
from deep_translator import GoogleTranslator
import feedparser

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")  # Ваш Telegram ID

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

# --- Ключевые слова (на русском и английском) ---
KEYWORDS_RU = [
    'черная металлургия', 'цветная металлургия', 'промышленные технологии',
    'обработка металлов', 'новые технологии', 'аналитика металлургии',
    'обзоры рынка', 'производство металлов', 'производство стали',
    'порошковая металлургия', 'аддитивные технологии', '3D-печать металлом',
    'редкоземельные металлы', 'РЗМ -рынок', 'тугоплавкие металлы',
    'вольфрам', 'молибден', 'ниобий', 'тантал', 'титан', 'ванадий',
    'сплавы металлов', 'стальные сплавы', 'титановые сплавы',
    'жаропрочные сплавы', 'суперсплавы', 'анализ рынка', 'цены на металлы',
    'рынок стали', 'рынок РЗМ', 'импорт металлов', 'экспорт металлов',
    'тенденции металлургии', 'прогнозы металлургии', 'промышленные обзоры',
    'металлургическое оборудование', 'печи металлургические',
    'роботизация металлургии', 'цифровизация металлургии',
    'инновации металлообработка', 'плазменная резка', 'микролегирование',
    'неразрушающий контроль', 'гафний', 'про роботов', 'золото',
    'серебро', 'медь', 'никель', 'алюминий', 'литий', 'кобальт',
    'аналитика -металлургия', 'новости -промышленность', 'энергетика',
    'угольная промышленность', 'горное дело', 'геология', 'месторождения',
    'инвестиции', 'проекты', 'ESG', 'нефтегаз', 'рудники',
    'инфраструктура', 'транспорт', 'порт', 'танкеры', 'сухогрузы',
    'цифровизация', 'ИИ', 'искусственный интеллект',
    'влияние технологий на будущее', 'технологии для удовольствия',
    'специальная металлургия'
]

KEYWORDS_EN = [
    'ferrous metallurgy', 'non-ferrous metallurgy', 'industrial technologies',
    'metal processing', 'new technologies', 'metallurgy analytics',
    'market reviews', 'metal production', 'steel production',
    'powder metallurgy', 'additive manufacturing', 'metal 3D printing',
    'rare earth metals', 'RE market', 'refractory metals',
    'tungsten', 'molybdenum', 'niobium', 'tantalum', 'titanium', 'vanadium',
    'metal alloys', 'steel alloys', 'titanium alloys',
    'heat-resistant alloys', 'superalloys', 'market analysis', 'metal prices',
    'steel market', 'rare earth market', 'metal import', 'metal export',
    'metallurgy trends', 'metallurgy forecasts', 'industrial reviews',
    'metallurgical equipment', 'metallurgical furnaces',
    'robotization of metallurgy', 'digitalization of metallurgy',
    'innovations in metalworking', 'plasma cutting', 'microalloying',
    'non-destructive testing', 'hafnium', 'about robots', 'gold',
    'silver', 'copper', 'nickel', 'aluminum', 'lithium', 'cobalt',
    'analytics - metallurgy', 'news - industry', 'energy',
    'coal industry', 'mining', 'geology', 'deposits',
    'investments', 'projects', 'ESG', 'oil and gas', 'mines',
    'infrastructure', 'transport', 'port', 'tankers', 'bulk carriers',
    'digitalization', 'AI', 'artificial intelligence',
    'impact of technology on the future', 'technologies for fun',
    'special metallurgy'
]

ALL_KEYWORDS = KEYWORDS_RU + KEYWORDS_EN

# --- Поиск новостей ---
def search_news():
    articles = []

    # 1. NewsAPI (на английском)
    if NEWSAPI_KEY:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': ' OR '.join(KEYWORDS_EN),
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 100,
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

    # 2. RSS из Китая (на китайском, но по теме)
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
                    if any(kw.lower() in title for kw in ['metal', 'technology', 'industry', 'steel', 'mining']):
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