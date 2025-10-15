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

## Synchronous HTTP Usage Example
### Basic
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

### Advanced: URL-Following & Pagination

```python
from crawl2schema.crawler.http import SyncHTTPCrawler

crawler = SyncHTTPCrawler()

# Schema for the product page (nested URL following)
product_schema = {
    "base_selector": "body",
    "fields": [
        {"name": "reviews", "type": "json", "selector": "script#reviews-data"},
        {"name": "suggested", "type": "list", "selector": "div.similar-products > a.product-preview", "list_subfields": [
            {"name": "name", "type": "text", "selector": "h3"},
            {"name": "price", "type": "number", "selector": "div.price"},
            {"name": "image", "type": "text", "attribute": "src", "selector": "img"},
        ]}
    ]
}

# Main schema for product listings
main_schema = {
    "base_selector": "div.product",
    "fields": [
        {"name": "name", "selector": "h3 > a", "type": "text", "postformatter": lambda x: x.strip().title()},
        {"name": "price", "selector": ".price", "type": "number"},
        {"name": "href", "selector": "h3 > a", "type": "text", "attribute": "href",
         "url_follow_schema": product_schema},  # follow link to fetch nested data
        {"name": "short_description", "selector": ".short-description", "type": "text",
         "postformatter": lambda x: x[:50].strip()}
    ],
    # Pagination: automatically generate URLs
    "url_pagination": {
        "page_placeholder": "{page}",
        "start_page": 1,
        "end_page": 3
    }
}

# Fetch data from paginated product listings
results = crawler.fetch(
    url="https://web-scraping.dev/products?page={page}",
    schema=main_schema,
    headers={"User-Agent": "Mozilla/5.0"},
)

print(f"Total products fetched: {len(results)}\n")

# Print first product including nested reviews
from pprint import pprint
pprint(results[0])
```

---

## Asynchronous HTTP Usage Example
### Basic

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

### Advanced: Concurrency & Pagination

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

## Sync Browser Usage Example
### Basic
```python
from crawl2schema.crawler.browser import SyncBrowserCrawler
from crawl2schema.crawler.schema import BrowserCrawlerSchema
from pprint import pprint
import re

def clean_text(text):
    return text.replace("\n", " ").strip()

def price_to_number(text):
    text = clean_text(text)
    return re.sub(".*€", "", text.replace(",", "."))

def rating_to_number(text):
    text = clean_text(text)

    return re.match(r"^(\d\.\d{1,2}) stars$", text).group(1)

crawler = SyncBrowserCrawler(headless=True)
schema: BrowserCrawlerSchema = {
    'base_selector': "div.grid-product__content",
    "fields": [
        { "name": "title", "type": "text", "selector": "div.grid-product__title", "postformatter": clean_text },
        { "name": "price", "type": "number", "selector": "div.grid-product__price", "preformatter": price_to_number },
        { "name": "sold-out", "selector": "div.grid-product__tag--sold-out", "type": "undefined", "default": False, "preformatter": bool },
        { "name": "rating", "selector": "span.jdgm-prev-badge__stars", "attribute": "aria-label", "type": "number", "preformatter": rating_to_number },
        { "name": "img", "selector": "img", "attribute": "src", "type": "text", "postformatter": lambda txt: txt.strip("//").strip() },
        { "name": "href", "selector": "a", "attribute": "href", "type": "text" }
    ]
}

url = "https://www.hhcfriends.eu/collections/buy-10-oh-thc-vapes"
data = crawler.fetch(url, schema=schema)
```

### Advanced: Pagionation with Button Clicking
```python
from crawl2schema.crawler.browser import SyncBrowserCrawler
from crawl2schema.crawler.schema import BrowserCrawlerSchema

crawler = SyncBrowserCrawler(headless=False)
schema: BrowserCrawlerSchema = {
    "base_selector": "div.review",
    "fields": [
        { "name": "text", "selector": "p", "type": "text", "preformatter": lambda text: text.replace("\n", "").strip() },
        { "name": "date", "selector": "span[data-testid='review-date']", "type": "text" },
        { "name": "rating", "selector": "span[data-testid='review-stars'] > svg", "type": "list", "list_formatter": len }
    ],
    "button_pagination": {
        "button_selector": "button#page-load-more",
        "stop_condition": "no-button",
        "retry_limit": 3,
        "retry_scroll_distance": -100,
        "retry_delay": 2,
        "cycle_delay": 1,
        "scroll_distance": 9999
    }
}

url = "https://web-scraping.dev/reviews"
data = crawler.fetch(url, schema=schema, wait_until="networkidle")
```

### Advanced: Pagination with Conditional Infinite Scrolling
```python
from crawl2schema.crawler.browser import SyncBrowserCrawler
from crawl2schema.crawler.schema import BrowserCrawlerSchema
import re

def clean_text(text):
    return text.replace("\n", " ").strip()

def price_to_number(text):
    text = clean_text(text)
    return re.sub(".*€", "", text.replace(",", "."))

def rating_to_number(text):
    text = clean_text(text)

    return re.match(r"^(\d\.\d{1,2}) stars$", text).group(1)

crawler = SyncBrowserCrawler(headless=True)
schema: BrowserCrawlerSchema = {
    'base_selector': "div.grid-product__content",
    "fields": [
        { "name": "title", "type": "text", "selector": "div.grid-product__title", "postformatter": clean_text },
        { "name": "price", "type": "number", "selector": "div.grid-product__price", "preformatter": price_to_number },
        { "name": "sold-out", "selector": "div.grid-product__tag--sold-out", "type": "undefined", "default": False, "preformatter": bool },
        { "name": "rating", "selector": "span.jdgm-prev-badge__stars", "attribute": "aria-label", "type": "number", "preformatter": rating_to_number },
        { "name": "img", "selector": "img", "attribute": "src", "type": "text", "postformatter": lambda txt: txt.strip("//").strip() },
        { "name": "href", "selector": "a", "attribute": "href", "type": "text" }
    ],
    "scroll_pagination": {
        "type": "scroll",
        "stop_condition": "no-new-elements",
        "scroll_distance": 1200,
        "retry_limit": 5,
        "scroll_delay": 3,
        "retry_scroll_distance": -100,
    }
}

url = "https://www.hhcfriends.eu/collections/bestseller-buy"
data = crawler.fetch(url, schema=schema)
```

---

## Running Tests

```bash
python -m pytest -v
```

---

## License

MIT License © 2025
