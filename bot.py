import os
import json
import requests
from datetime import datetime
from deep_translator import GoogleTranslator
import feedparser
from fpdf import FPDF
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- Настройки ---
TOKEN = os.getenv("TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# --- Состояния ---
AWAITING_KEYWORDS = "awaiting_keywords"

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

# --- Поиск новостей ---
def search_news(keywords):
    articles = []

    # 1. NewsAPI
    if NEWSAPI_KEY:
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
            if r.status_code == 200:
                data = r.json()
                articles.extend(data.get('articles', []))
            else:
                print(f"NewsAPI error {r.status_code}: {r.text}")
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
                if not feed.entries:
                    print(f"⚠️ RSS {name} пустой")
                else:
                    print(f"✅ {name}: {len(feed.entries)} статей")
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
                print(f"❌ Ошибка RSS {name}: {e}")
    except Exception as e:
        print(f"Ошибка парсинга RSS: {e}")

    return articles

# --- Создание PDF ---
def create_pdf(articles, filename="digest.pdf"):
    try:
        font_path = "DejaVuSans.ttf"
        if not os.path.exists(font_path):
            print("Шрифт DejaVuSans.ttf не найден")
            return None

        pdf = FPDF()
        pdf.add_font('DejaVu', '', font_path, uni=True)
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
    except Exception as e:
        print(f"Ошибка создания PDF: {e}")
        return None

# --- Отправка в Telegram ---
async def send_message(chat_id, text, parse_mode='Markdown', disable_preview=False):
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

# --- Отправка ошибок админу ---
async def send_error(msg):
    if ADMIN_ID and TOKEN:
        await send_message(ADMIN_ID, f"❌ Ошибка бота:\n\n`{msg}`")

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
        await query.edit_message_text("У вас пока нет активных подписок.")

    elif query.data == 'help':
        await query.edit_message_text(
            "Используйте:\n"
            "🔍 Поиск новостей — ищите по теме\n"
            "📋 Мои подписки — управление рассылкой\n"
            "Все новости с переводом на русский."
        )

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
    print(f"Получено статей: {len(raw_articles)}")

    if not raw_articles:
        await update.message.reply_text("❌ Новости не найдены.")
        context.user_data['state'] = None
        return

    # Убираем дубли
    seen_urls = load_cache()
    articles = [a for a in raw_articles if a.get('link') not in seen_urls]

    if not articles:
        await update.message.reply_text("Новости уже были показаны ранее.")
        context.user_data['state'] = None
        return

    # Показываем первые 5
    for art in articles[:5]:
        title_ru = translate_text(art['title'])
        source = art.get('source', 'Неизвестно')
        msg = f"📌 *{title_ru}*\n🌐 {source}\n🔗 {art['link']}"
        await update.message.reply_text(msg, parse_mode='Markdown', disable_web_page_preview=False)

    # Создаём PDF
    pdf_path = create_pdf(articles, "digest.pdf")
    if pdf_path and os.path.exists(pdf_path):
        await update.message.reply_document(
            document=open(pdf_path, 'rb'),
            caption="📄 PDF-дайджест новостей"
        )
        os.remove(pdf_path)
    else:
        await update.message.reply_text("⚠️ Не удалось создать PDF.")

    # Обновляем кеш
    for art in articles:
        url = art.get('link')
        if url:
            seen_urls.add(url)
    save_cache(seen_urls)

    context.user_data['state'] = None

# --- Запуск в GitHub Actions ---
def main():
    print("🚀 Бот запущен (режим GitHub Actions)")
    try:
        seen_urls = load_cache()
        keywords = ['технологии', 'космос', 'AI', '科技', 'technology']
        print(f"🔍 Ключевые слова: {keywords}")
        raw_articles = search_news(keywords)
        print(f"Получено статей: {len(raw_articles)}")

        if not raw_articles:
            print("❌ Новости не найдены — возможно, ошибка в API или RSS")
            return

        new_articles = [a for a in raw_articles if a.get('link') not in seen_urls]
        print(f"✅ Новых: {len(new_articles)}")

        # Обновляем кеш
        for art in new_articles:
            url = art.get('link')
            if url:
                seen_urls.add(url)
        save_cache(seen_urls)

        print("✅ Кеш обновлён.")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:500]}"
        print(f"🔴 Ошибка: {error_msg}")
        if ADMIN_ID and TOKEN:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": ADMIN_ID, "text": f"❌ Ошибка: `{error_msg}`"}
            )

# --- Запуск ---
if __name__ == "__main__":
    if os.getenv("GITHUB_ACTIONS"):
        main()
    else:
        print("Запуск в режиме polling не поддерживается напрямую")