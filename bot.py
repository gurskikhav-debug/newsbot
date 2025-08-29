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

# --- Ключевые слова (технические темы) ---
KEYWORDS_EN = [
    'metallurgy', 'ferrous metallurgy', 'non-ferrous metallurgy',
    'steel production', 'metal processing', 'additive manufacturing',
    '3D printing metal', 'rare earth metals', 'refractory metals',
    'tungsten', 'molybdenum', 'niobium', 'tantalum', 'titanium', 'vanadium',
    'metal alloys', 'steel alloys', 'titanium alloys', 'superalloys',
    'material properties', 'thermal conductivity', 'mechanical strength',
    'AI in industry', 'industrial automation', 'robotic systems',
    'green hydrogen', 'battery technology', 'energy storage',
    'technical specifications', 'engineering design', 'R&D innovation'
]

KEYWORDS_RU = [
    'металлургия', 'черная металлургия', 'цветная металлургия',
    'производство стали', 'обработка металлов', 'сталь', 'металл',
    'аддитивные технологии', '3D печать металлом', 'редкоземельные металлы',
    'тугоплавкие металлы', 'вольфрам', 'молибден', 'ниобий', 'тантал', 'титан',
    'ванадий', 'сплавы металлов', 'стальные сплавы', 'титановые сплавы',
    'суперсплавы', 'свойства материалов', 'теплопроводность', 'прочность',
    'механические свойства', 'ИИ в промышленности', 'автоматизация',
    'роботизированные системы', 'зелёный водород', 'технология аккумуляторов',
    'накопление энергии', 'технические характеристики', 'инженерный дизайн',
    'исследования и разработки'
]

# --- Проверенные технические источники ---
TECHNICAL_SOURCES_EN = [
    'engineering.com', 'ieee.org', 'sciencedirect.com', 'springer.com',
    'nature.com', 'researchgate.net', 'arxiv.org', 'phys.org',
    'machinedesign.com', 'designnews.com', 'sae.org'
]

TECHNICAL_SOURCES_RU = [
    'habr.com', 'nplus1.ru', 'scientificrussia.com', 'vtor-ch.ru',
    'cherepovetsmet.ru', 'metalinfo.ru', 'engineering-spb.ru'
]

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

# --- Поиск новостей за 3 дня ---
def search_news():
    articles = []

    # 1. NewsAPI — с фильтром по дате и группировкой запросов
    if NEWSAPI_KEY:
        from_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')

        # Группы запросов (чтобы не превысить 500 символов)
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
                            'published': item.get('publishedAt', 'Неизвестно'),
                            'lang': 'en'
                        })
                else:
                    print(f"NewsAPI error {r.status_code}: {r.text}")
            except Exception as e:
                print(f"NewsAPI ошибка: {e}")

    # 2. RSS из технических источников
    try:
        feeds = {
            'habr': 'https://habr.com/ru/rss/technology/',
            'nplus1': 'https://nplus1.ru/rss',
            'engineering': 'https://www.engineering.com/rss'
        }
        for name, feed_url in feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.title.lower()
                    if any(kw.lower() in title for kw in ['metal', 'tech', 'ai', 'alloy', 'engineering']):
                        lang = 'ru' if 'habr' in name or 'nplus1' in name else 'en'
                        articles.append({
                            'title': entry.title,
                            'url': entry.link,
                            'source': name,
                            'published': entry.get('published', 'Неизвестно'),
                            'lang': lang
                        })
            except Exception as e:
                print(f"Ошибка RSS {name}: {e}")
    except Exception as e:
        print(f"Ошибка парсинга RSS: {e}")

    return articles

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
            if any(kw.lower() in title for kw in KEYWORDS_RU + KEYWORDS_EN):
                filtered_articles.append(art)

        print(f"После фильтрации: {len(filtered_articles)}")

        # Сортируем по приоритету источников
        def source_priority(article):
            source = article['source'].lower()
            if any(s in source for s in TECHNICAL_SOURCES_EN + TECHNICAL_SOURCES_RU):
                return 0
            return 1

        filtered_articles.sort(key=source_priority)

        # Убираем дубли
        articles = [a for a in filtered_articles if a.get('url') not in seen_urls]

        # Баланс: 50% RU, 50% EN
        ru_articles = [a for a in articles if a.get('lang') == 'ru']
        en_articles = [a for a in articles if a.get('lang') == 'en']

        # Целевые количества
        target_count = 10
        max_total = 20

        # Докачиваем до 10, если не хватает
        selected_ru = ru_articles[:target_count]
        selected_en = en_articles[:target_count]

        while len(selected_ru) + len(selected_en) < target_count and (len(ru_articles) > len(selected_ru) or len(en_articles) > len(selected_en)):
            if len(ru_articles) > len(selected_ru):
                selected_ru.append(ru_articles[len(selected_ru)])
            if len(en_articles) > len(selected_en) and len(selected_ru) + len(selected_en) < target_count:
                selected_en.append(en_articles[len(selected_en)])

        # Объединяем и ограничиваем 20
        selected = (selected_ru + selected_en)[:max_total]

        print(f"Отправляем: {len(selected)} новостей (50% RU, 50% EN)")

        # --- ВСЕГДА отправляем список источников ---
        sources_msg = "📋 *Используемые источники:*\n\n"
        sources_msg += "*🇷🇺 Русскоязычные:*\n"
        for src in TECHNICAL_SOURCES_RU:
            sources_msg += f"• `{src}`\n"
        sources_msg += "\n*🌍 Англоязычные:*\n"
        for src in TECHNICAL_SOURCES_EN:
            sources_msg += f"• `{src}`\n"

        if ADMIN_ID:
            try:
                admin_id_int = int(ADMIN_ID)
                send_message(admin_id_int, sources_msg, disable_preview=False)
            except ValueError:
                print(f"❌ ADMIN_ID '{ADMIN_ID}' не является числом")

        # --- Отправляем новости, если есть ---
        if selected:
            batch_size = 5
            msg = "📬 *Ежедневный дайджест (технические источники)*\n\n"
            for i, art in enumerate(selected, 1):
                title_ru = translate_text(art['title'])
                source = art.get('source', 'Неизвестно')
                msg += f"📌 *{title_ru}*\n🌐 {source}\n🔗 {art['url']}\n\n"

                if i % batch_size == 0 or i == len(selected):
                    if ADMIN_ID:
                        try:
                            admin_id_int = int(ADMIN_ID)
                            send_message(admin_id_int, msg, disable_preview=False)
                        except ValueError:
                            print(f"❌ ADMIN_ID '{ADMIN_ID}' не является числом")
                    msg = ""
                    if i != len(selected):
                        msg = "\n"

            # Обновляем кеш
            for art in selected:
                url = art.get('url')
                if url:
                    seen_urls.add(url)
            save_cache(seen_urls)

        else:
            # Даже если новостей нет, сообщаем об этом
            if ADMIN_ID:
                no_news_msg = "📭 *Новых новостей по вашим темам пока нет.*\n"
                no_news_msg += "Следующий поиск — завтра в 18:00."
                send_message(int(ADMIN_ID), no_news_msg, disable_preview=False)

        print("✅ Рассылка завершена.")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:500]}"
        print(f"🔴 Ошибка: {error_msg}")
        if ADMIN_ID and TOKEN:
            send_message(ADMIN_ID, f"❌ Ошибка: `{error_msg}`")

# --- Запуск ---
if __name__ == "__main__":
    main()
