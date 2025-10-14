import asyncio
from datetime import datetime
from crawl2schema.crawler.http import AsyncHTTPCrawler
from crawl2schema.crawler.schema import HTTPCrawlerSchema

# -----------------------------
# Helper formatters
# -----------------------------
def textcleaner(text: str) -> str:
    """Strip extra whitespace from text."""
    return text.strip()

def numberformatter(text: str) -> int:
    """Convert view counts like '2.5K' into integers."""
    if "K" in text:
        # Remove dots, 'K', and append '00' to simulate thousands
        text = text.replace(".", "").replace("K", "") + "00"
    return int(text)

# -----------------------------
# Crawler schema
# -----------------------------
schema: HTTPCrawlerSchema = {
    "base_selector": "div.cursor-pointer",
    "fields": [
        {"name": "name", "selector": "h3", "postformatter": textcleaner},
        {"name": "module", "selector": "a.bg-blue-600", "postformatter": textcleaner},
        {"name": "categories", "selector": "a.bg-blue-50", "type": "list", "preformatter": textcleaner},
        {"name": "views", "selector": "span.text-gray-600", "type": "number", "preformatter": numberformatter},
        {"name": "datetime", "selector": "time", "attribute": "datetime",
         "postformatter": lambda iso: datetime.fromisoformat(iso)},
    ],
}

# -----------------------------
# Models to scrape
# -----------------------------
MODELS = [
    'gpt 4o', 'gpt', 'midjourney', 'claude opus 4', 'o3', 'sora',
    'gpt, claude, gemini', 'midjourney v7', 'claude', 'gemini 2.5',
    'midjourney video', 'claude sonnet 4', 'veo 3', 'cursor',
    'grok 3', 'hailuo 02', 'gpt 4o, suno', 'suno v4', 'claude code',
    'gpt 4', 'midjourney v5', 'GPT-5', 'grok 3 & Others', 'suno 3.5',
    'gpt 4.1', 'kling', 'kling 1.6', 'kling 2.1', 'veo3', 'sesame'
]

BASE_URL = "https://www.godtierprompts.com/model"
semaphore = asyncio.Semaphore(5)

# -----------------------------
# Async fetch function
# -----------------------------
async def sem_fetch_model(model: str) -> list[dict]:
    """Fetch model page and extract data using the defined schema."""
    # Clean model name to URL slug
    model_slug = model.strip().replace(".", "").replace(",", "").replace(" ", "-").replace("&", "").lower()
    async with semaphore:
        async with AsyncHTTPCrawler() as crawler:
            url = f"{BASE_URL}/{model_slug}"
            return await crawler.fetch(url, schema=schema)

# -----------------------------
# Main entry
# -----------------------------
async def main():
    # Create tasks for all models
    tasks = [sem_fetch_model(model) for model in MODELS]

    # Await all tasks
    results = await asyncio.gather(*tasks)

    # Flatten the list of lists
    flattened = [item for batch in results for item in batch]

    # Output results
    for item in flattened:
        print(item)

    print(f"\nTotal prompts scraped: {len(flattened)}")

# -----------------------------
# Run script
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())