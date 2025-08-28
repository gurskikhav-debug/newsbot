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
    'производство стали', 'обработка металлов', 'аддитивные технологии',
    '3D печать металлом', 'редкоземельные металлы', 'тугоплавкие металлы',
    'вольфрам', 'молибден', 'ниобий', 'тантал', 'титан', 'ванадий',
    'сплавы металлов', 'стальные сплавы', 'титановые сплавы', 'суперсплавы',
    'свойства материалов', 'теплопроводность', 'прочность', 'механические свойства',
    'ИИ в промышленности', 'автоматизация', 'роботизированные системы',
    'зелёный водород', 'технология аккумуляторов', 'накопление энергии',
    'технические характеристики', 'инженерный дизайн', 'исследования и разработки'
]

# --- Приоритетные источники (технические) ---
TECHNICAL_SOURCES_EN = [
    'engineering.com', 'ieee.org', 'sciencedirect.com', 'springer.com',
    'nature.com', 'researchgate.net', 'arxiv.org', 'phys
