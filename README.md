<p align="center" style="user-select: none;">
    <img src="banner.svg" width="75%">
    <br>
    Turn the web into structured data — effortlessly.
    <br>
    <img src="https://github.com/cvcvka5/crawl2schema/actions/workflows/python-tests.yml/badge.svg" alt="Python Tests" />
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
    <br>
    <br>
    <strong>Crawl2Schema</strong> is a Python web crawler built to extract structured data from websites using <strong>schemas</strong>. It’s designed to turn chaotic web pages into clean, reusable data—fast. One man, one vision, building a tool that’s about to become essential for anyone doing serious web scraping.
</p>

---

## Features

* **Schema-driven scraping:** Define exactly what you want to extract with CSS selectors, types, postformatter/preformatter functions.
* **Synchronous crawling:** Reliable, simple, and lightweight for most use cases.
* **Paginated crawling:** Automatically iterate through multiple pages with flexible start/end settings.
* **Nested data support:** Follow links and extract deeper content using nested schemas.
* **Structured output:** Returns data as clean lists of dictionaries.
* **Custom formatting:** Apply transformations to your data on the fly.

---

## Installation

```bash
git clone https://github.com/cvcvka5/crawl2schema.git
cd crawl2schema
pip install -r requirements.txt
```

---

## Synchronous Usage Example

```python
from crawl2schema.crawler.http import SyncHTTPCrawler

crawler = SyncHTTPCrawler()

schema = {
    "base_selector": "div.product",
    "fields": [
        {"name": "name", "selector": "h3 > a", "type": "text", "postformatter": lambda x: x.strip().title()},
        {"name": "price", "selector": ".price", "type": "number"},
        {"name": "href", "selector": "h3 > a", "type": "text", "attribute": "href"},
        {"name": "short_description", "selector": ".short-description", "type": "text", "postformatter": lambda x: x[:50].strip()}
    ]
}

results = crawler.fetch(
    url="https://web-scraping.dev/products",
    schema=schema,
    headers={"User-Agent": "Mozilla/5.0"},
)

for product in results:
    print(product)
```

---

## Asynchronous Usage Example

### Basic Async Crawl

```python
import asyncio
from crawl2schema.crawler.http import AsyncHTTPCrawler

async def main():
    crawler = AsyncHTTPCrawler()

    schema = {
        "base_selector": "div.product",
        "fields": [
            {"name": "name", "selector": "h3 > a", "type": "text"},
            {"name": "price", "selector": ".price", "type": "number"},
        ]
    }

    data = await crawler.fetch("https://web-scraping.dev/products", schema=schema)
    print(data)

asyncio.run(main())
```

### Advanced Async: Concurrent & Paginated

```python
import asyncio
from crawl2schema.crawler.http import AsyncHTTPCrawler

async def main():
    crawler = AsyncHTTPCrawler()

    schema = {
        "base_selector": "div.product",
        "fields": [
            {"name": "name", "selector": "h3 > a", "type": "text"},
            {"name": "price", "selector": ".price", "type": "number"},
        ]
    }

    # Its cleaner to generate the urls yourself instead of using the 'pagination' key in schema.
    # The 'pagination' key exists only so URL pagination is more schematic durin sync crawling.
    urls = [f"https://web-scraping.dev/products?page={i}" for i in range(1, 4)]

    semaphore = asyncio.Semaphore(2)  # Limit concurrent requests

    async def sem_fetch(url):
        async with semaphore:
            return await crawler.fetch(url, schema=schema)

    tasks = [sem_fetch(url) for url in urls]
    results = await asyncio.gather(*tasks)

    total = sum(len(r) for r in results)
    print(f"Total products fetched: {total}")

asyncio.run(main())
```

---

## Running Tests

```bash
python -m pytest -v
```

---

## License

MIT License © 2025
