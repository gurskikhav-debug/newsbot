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

# --- Ключевые слова (без морфологии — точные формы) ---
KEYWORDS_EN = [
    'metallurgy', 'ferrous metallurgy', 'non-ferrous metallurgy',
    'steel production', 'metal processing', 'additive manufacturing',
    '3D printing', '3D printing metal', 'AM', 'rapid prototyping',
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

# --- Поиск новостей за последние 3 дня ---
def search_news():
    articles = []

    # 1. NewsAPI — с фильтром по дате и группировкой запросов
    if NEWSAPI_KEY:
        from_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')

        # Группы ключевых слов (чтобы не превысить 500 символов)
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
                   
