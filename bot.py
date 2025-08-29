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

# --- Ключевые слова ---
KEYWORDS_EN = ['technology', 'AI', 'robotics', '3D printing', 'green energy']
KEYWORDS_RU = ['технологии', 'ИИ', 'робототехника', '3D печать', 'зелёная энергетика']
ALL_KEYWORDS = [kw.lower() for kw in KEYWORDS_EN + KEYWORDS_RU]

# --- Поиск новостей ---
def search_news():
    articles = []

    # 1. NewsAPI
    if NEWSAPI_KEY:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': ' OR '.join(KEYWORDS_EN),
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

    # 2. RSS — временно отключены (не работают)
    # feeds = { ... }

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
    
    # Отправляем статус поиска
    status_msg = "🔍 *Поиск новостей запущен...*\n"
    status_msg += "• Источник: NewsAPI (международные новости)\n"
    status_msg += "• Темы: технологии, ИИ, робототехника, 3D печать, зелёная энергетика\n"
    status_msg += "• Язык: английский + русский\n"
    status_msg += "• Фильтр дублей: включён\n"
    
    if ADMIN_ID:
        send_message(ADMIN_ID, status_msg, disable_preview=False)

    seen_urls = load_cache()
    raw_articles = search_news()
    print(f"Получено статей: {len(raw_articles)}")

    if not raw_articles:
        error_msg = "❌ Новости не найдены.\n"
        error_msg += "Возможные причины:\n"
        error_msg += "• Нет активных новостей по теме\n"
        error_msg += "• Ошибка подключения к NewsAPI\n"
        error_msg += "• Ключевые слова слишком узкие"
        if ADMIN_ID:
            send_message(ADMIN_ID, error_msg)
        return

    # Фильтруем по ключевым словам
    filtered_articles = []
    for art in raw_articles:
        title = art['title'].lower()
        if any(kw in title for kw in ALL_KEYWORDS):
            filtered_articles.append(art)

    print(f"После фильтрации: {len(filtered_articles)}")

    # Убираем дубли
    articles = [a for a in filtered_articles if a.get('url') not in seen_urls]

    if not articles:
        no_new_msg = "📭 Новых новостей по вашим темам нет.\n"
        no_new_msg += "Все найденные уже были показаны ранее."
        if ADMIN_ID:
            send_message(ADMIN_ID, no_new_msg)
        return

    # Отправляем первые 10
    msg = "📬 *Ежедневный дайджест*\n\n"
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

    print("✅ Рассылка завершена.")

# --- Запуск ---
if __name__ == "__main__":
    main()
