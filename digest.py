import os
import requests
from datetime import datetime, timedelta, timezone
from openai import OpenAI

# --- Конфиг ---
READWISE_TOKEN = os.environ["READWISE_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def fetch_readwise_documents():
    """Забирает все документы за последние 24 часа через пагинацию"""
    updated_after = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    all_docs = []
    next_cursor = None

    while True:
        params = {"updatedAfter": updated_after}
        if next_cursor:
            params["pageCursor"] = next_cursor

        response = requests.get(
            "https://readwise.io/api/v3/list/",
            headers={"Authorization": f"Token {READWISE_TOKEN}"},
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        all_docs.extend(data.get("results", []))
        next_cursor = data.get("nextPageCursor")

        if not next_cursor:
            break

    return all_docs


def build_digest(docs):
    """Формирует текст для OpenAI"""
    if not docs:
        return None

    lines = []
    for doc in docs:
        title = doc.get("title", "")
        summary = doc.get("summary", "")
        url = doc.get("url") or doc.get("source_url", "")
        if title and url:
            lines.append(f"- {title} | {summary} | {url}")

    return "\n".join(lines)


def generate_digest_with_ai(articles_text):
    """Отправляет в OpenAI и получает дайджест"""
    client = OpenAI(api_key=OPENAI_API_KEY)

    today = datetime.now().strftime("%d %B %Y")

    prompt = f"""Ты составляешь ежедневный дайджест новостей на русском языке.

Вот список статей за последние 24 часа:

{articles_text}

Для КАЖДОЙ статьи напиши одну строку: краткое описание на русском что в ней интересного + ссылка.
Сгруппируй по темам (AI & Tech / Бизнес / Наука / Австрия & Европа).
Если статья не подходит ни под одну из четырёх категорий — добавь её в категорию 🌍 Другое.

Формат строго такой:

📰 Дайджест {today}

🤖 AI & Tech
• [краткое описание] → [url]

💼 Бизнес
• [краткое описание] → [url]

🔬 Наука
• [краткое описание] → [url]

🇪🇺 Австрия & Европа
• [краткое описание] → [url]

Если в какой-то категории нет статей — пропусти её. Только дайджест, без лишних слов."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )

    return response.choices[0].message.content


def send_to_telegram(text):
    """Отправляет сообщение в Telegram"""
    # Telegram ограничивает сообщения 4096 символами
    # Если длиннее — разбиваем на части
    max_length = 4000
    chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]

    for chunk in chunks:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()


def main():
    print("Fetching documents from Readwise...")
    docs = fetch_readwise_documents()
    print(f"Found {len(docs)} documents")

    if not docs:
        print("No documents found, skipping digest")
        return

    articles_text = build_digest(docs)
    print("Generating digest with AI...")
    digest = generate_digest_with_ai(articles_text)

    print("Sending to Telegram...")
    send_to_telegram(digest)
    print("Done!")


if __name__ == "__main__":
    main()
