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
    for i, doc in enumerate(docs, 1):
        title = doc.get("title", "").strip()
        url = doc.get("url") or doc.get("source_url", "")
        summary = doc.get("summary", "").strip()
        if title and url:
            short_summary = summary[:100] if summary else ""
            lines.append(f"{i}. {title} | {short_summary} | {url}")

    return "\n".join(lines)


def generate_digest_with_ai(articles_text, total_count):
    client = OpenAI(api_key=OPENAI_API_KEY)
    today = datetime.now().strftime("%d %B %Y")

    prompt = f"""Ты переводишь список статей в дайджест на русском языке.

Входящий список содержит РОВНО {total_count} статей пронумерованных от 1 до {total_count}.
Ты ОБЯЗАН включить все {total_count} статей в ответ — ни одну не пропускай.

Список статей:
{articles_text}

Инструкции:
1. Переведи заголовок каждой статьи на русский (кратко, 1 строка)
2. Сгруппируй по категориям: AI & Tech / Бизнес / Наука / Австрия и Европа / Другое
3. Каждая строка: - описание → url
4. URL пиши как есть, без скобок

Начни ответ с:
Дайджест {today}
Статей: {total_count}"""

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
    digest = generate_digest_with_ai(articles_text, len(docs))

    print("Sending to Telegram...")
    send_to_telegram(digest)
    print("Done!")


if __name__ == "__main__":
    main()
