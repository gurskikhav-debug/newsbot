import os
import json
import requests
from datetime import datetime
from googletrans import Translator
import feedparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# --- Состояния ---
AWAITING_KEYWORDS = "awaiting_keywords"

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

CACHE_FILE = "cache/news_cache.json"
translator = Translator()

# --- Кеш ---
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_cache(cache_set):
    os.makedirs("cache", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(cache_set), f, ensure_ascii=False, indent=2)

# --- Перевод ---
def translate_text(text):
    try:
        return translator.translate(text, dest='ru').text
    except:
        return text

# --- Поиск новостей ---
def search_news(keywords):
    articles = []

    # 1. NewsAPI
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': ' OR '.join(keywords),
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 10,
            'apiKey': NEWSAPI_KEY
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        articles.extend(data.get('articles', []))
    except Exception as e:
        print(f"NewsAPI error: {e}")

    # 2. RSS Китай
    try:
        feeds = {
            'xinhua': 'http://www.xinhuanet.com/rss/world.xml',
            'sina': 'https://rss.sina.com.cn/news/china.xml',
            'sohu': 'http://rss.news.sohu.com/rss2/news.xml'
        }
        for name, feed_url in feeds.items():
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.title.lower()
                if any(kw.lower() in title for kw in keywords):
                    articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'source': name,
                        'published': entry.get('published', 'Неизвестно')
                    })
    except Exception as e:
        print(f"RSS error: {e}")

    return articles

# --- Создание PDF ---
def create_pdf(articles, filename="digest.pdf"):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.add_page()
    pdf.set_font('DejaVu', size=14)
    pdf.cell(0, 10, '📰 Новостной дайджест', ln=True, align='C')

    pdf.set_font('DejaVu', size=12)
    for art in articles:
        title_ru = translate_text(art['title'])
        pdf.cell(0, 8, f"• {title_ru}", ln=True)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 8, f"  Источник: {art['source']}", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, f"  Ссылка: {art['link']}", ln=True)
        pdf.ln(4)

    pdf.output(filename)
    return filename

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск новостей", callback_data='manual_search')],
        [InlineKeyboardButton("📋 Мои подписки", callback_data='mysubs')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот для поиска новостей.\nВыберите действие:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'manual_search':
        await query.edit_message_text("Введите **ключевые слова** для поиска.\nНапример: `космос, NASA`")
        context.user_data['state'] = AWAITING_KEYWORDS

    elif query.data == 'mysubs':
        await query.edit_message_text("У вас пока нет подписок.")

    elif query.data == 'help':
        await query.edit_message_text("Используйте кнопки ниже для поиска новостей.")

async def handle_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != AWAITING_KEYWORDS:
        return

    keywords_input = update.message.text.strip()
    if not keywords_input:
        await update.message.reply_text("Введите хотя бы одно слово.")
        return

    keywords = [kw.strip().lower() for kw in keywords_input.split(',') if kw.strip()]
    await update.message.reply_text(f"🔍 Ищу новости по: *{', '.join(keywords)}*...", parse_mode='Markdown')

    # Поиск
    raw_articles = search_news(keywords)
    if not raw_articles:
        await update.message.reply_text("❌ Новости не найдены.")
        context.user_data['state'] = None
        return

    # Ограничиваем 10 статей
    articles = raw_articles[:10]

    # Переводим и показываем
    for art in articles[:5]:
        title_ru = translate_text(art['title'])
        msg = f"📌 *{title_ru}*\n🌐 {art['source']}\n🔗 {art['link']}"
        await update.message.reply_text(msg, parse_mode='Markdown', disable_web_page_preview=False)

    # Создаём PDF
    try:
        pdf_path = create_pdf(articles, "digest.pdf")
        await update.message.reply_document(document=open(pdf_path, 'rb'), caption="📄 Вот ваш PDF-дайджест!")
        os.remove(pdf_path)  # удаляем после отправки
    except Exception as e:
        await update.message.reply_text(f"Ошибка генерации PDF: {e}")

    context.user_data['state'] = None

# --- Основная функция для GitHub Actions ---
def main_github():
    print("Запуск по расписанию...")
    seen = load_cache()
    keywords = ['технологии', 'технологии']  # можно брать из БД
    articles = search_news(keywords)
    new_articles = [a for a in articles if a['link'] not in seen]

    for art in new_articles[:3]:
        title_ru = translate_text(art['title'])
        print(f"Новость: {title_ru} → {art['link']}")

    # Обновляем кеш
    for a in new_articles:
        seen.add(a['link'])
    save_cache(seen)

if __name__ == "__main__":
    # Режим для GitHub Actions
    if os.getenv("GITHUB_ACTIONS"):
        main_github()
    else:
        # Режим для постоянной работы (не используется)
        pass