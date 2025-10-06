# Crawl2Schema

[![Python Tests](https://github.com/cvcvka5/crawl2schema/actions/workflows/python-tests.yml/badge.svg)](https://github.com/cvcvka5/crawl2schema/actions/workflows/python-tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Crawl2Schema** is a Python web crawler built to extract structured data from websites using **schemas**. It’s designed to turn chaotic web pages into clean, reusable data—fast. One man, one vision, building a tool that’s about to become essential for anyone doing serious web scraping.

---

## Features

* **Schema-driven scraping:** Define exactly what you want to extract with CSS selectors, types, and formatter functions.
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

## Usage Example

```python
from crawl2schema.crawler.http import SyncHTTPCrawler

crawler = SyncHTTPCrawler()

schema = {
    "base_selector": "div.product",
    "fields": [
        {"name": "name", "selector": "h3 > a", "type": "text", "formatter": lambda x: x.strip().title()},
        {"name": "price", "selector": ".price", "type": "number"},
        {"name": "href", "selector": "h3 > a", "type": "text", "attribute": "href"},
        {"name": "short_description", "selector": ".short-description", "type": "text", "formatter": lambda x: x[:50].strip()}
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

**Example output:**

```json
[
    {
        "name": "Product One",
        "price": 29.99,
        "href": "/products/1",
        "short_description": "This is a short description of product one."
    },
    {
        "name": "Product Two",
        "price": 39,
        "href": "/products/2",
        "short_description": "This is a short description of product two."
    }
]
```

---

## Advanced Example: Nested Schema & Pagination

```python
from crawl2schema.crawler.http import SyncHTTPCrawler

crawler = SyncHTTPCrawler()

product_schema = {
    "base_selector": "script#reviews-data",
    "fields": [
        {"name": "reviews", "type": "json", "selector": "*"}
    ]
}

main_schema = {
    "base_selector": "div.product",
    "fields": [
        {"name": "name", "selector": "h3 > a", "type": "text"},
        {"name": "price", "selector": ".price", "type": "number"},
        {"name": "href", "selector": "h3 > a", "type": "text", "attribute": "href", "follow_schema": product_schema},
    ],
    "pagination": {"start_page": 1, "end_page": 3, "page_placeholder": "{page}"}
}

data = crawler.fetch("https://web-scraping.dev/products?page={page}", main_schema)

print(f"Total products fetched: {len(data)}")
print(data[0])  # first product with nested reviews
```

---

## Running Tests

```bash
python -m pytest -v
```

---

## Roadmap

Crawl2Schema is just getting started. Here’s where it’s headed:

* [ ] **Async crawling** with `aiohttp` for massive scraping tasks.
* [ ] **Dynamic pagination** (next buttons, infinite scroll).
* [ ] **Custom output** (JSON, CSV, SQLite, Pandas DataFrames).
* [ ] **Retry & error handling** with exponential backoff.
* [ ] **Rate limiting & throttling** to avoid bans.
* [ ] **Browser crawling** for JS-heavy websites using Playwright/Selenium.
* [ ] **Schema validation** and pre-processing hooks.

---

## License

MIT License © 2025
