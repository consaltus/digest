import os
import requests
from datetime import datetime, timedelta, timezone
from openai import OpenAI

READWISE_TOKEN = os.environ["READWISE_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def fetch_readwise_documents():
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


def build_articles_text(docs):
    if not docs:
        return None

    lines = []
    for doc in docs:
        title = doc.get("title", "").strip()
        url = doc.get("url") or doc.get("source_url", "")
        summary = doc.get("summary", "").strip()
        if title and url:
            short_summary = summary[:100] if summary else ""
            lines.append(f"{title} | {short_summary} | {url}")

    return "\n".join(lines)


def generate_digest_with_ai(articles_text):
    client = OpenAI(api_key=OPENAI_API_KEY)
    today = datetime.now().strftime("%d %B %Y")

    prompt = f"""Ты составляешь ежедневный дайджест новостей на русском языке.

Вот список статей за последние 24 часа:

{articles_text}

Для КАЖДОЙ статьи напиши одну строку: краткое описание на русском + ссылка.
Используй ВСЕ статьи из списка без исключений.
Сгруппируй по темам.

Формат строго такой (простой текст, без markdown):

Дайджест {today}

AI & Tech
- краткое описание → url

Бизнес
- краткое описание → url

Наука
- краткое описание → url

Австрия и Европа
- краткое описание → url

Другое
- краткое описание → url

Если категория пустая - не включай её.
Пиши url как есть, без скобок и markdown."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
    )

    return response.choices[0].message.content


def send_to_telegram(text):
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

    articles_text = build_articles_text(docs)
    print(f"Articles text length: {len(articles_text)} chars")
    print("Generating digest with AI...")
    digest = generate_digest_with_ai(articles_text)

    print("Sending to Telegram...")
    send_to_telegram(digest)
    print("Done!")


if __name__ == "__main__":
    main()
