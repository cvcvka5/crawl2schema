# Crawl2Schema
[![Python Tests](https://github.com/cvcvka5/crawl2schema/actions/workflows/python-tests.yml/badge.svg)](https://github.com/cvcvka5/crawl2schema/actions/workflows/python-tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Crawl2Schema** is a Python web crawler that uses **schemas** to extract, format, and return structured data from websites. It’s designed to make web scraping more organized, reusable, and easy to manage.

---

## Features

* **Schema-driven scraping**: Define a crawler schema with selectors, types, and formatter functions.
* **Synchronous crawling**: Reliable and simple to use for single-page scrapes.
* **Paginated crawling**: Crawl multiple pages by specifying a start and end page.
* **Structured output**: Automatically returns data in a clean, structured format (list of dictionaries).
* **Customizable formatting**: Apply functions to clean or transform extracted values.

---

## Installation

```bash
git clone https://github.com/yourusername/crawl2schema.git
cd crawl2schema
pip install -r requirements.txt
```

---

## Usage Example

```python
from crawl2schema.crawler.http import SyncHTTPCrawler

crawler = SyncHTTPCrawler()

schema = {
    "baseSelector": "body",
    "targetElements": [
        {"name": "price", "selector": ".price", "type": float, "formatter": lambda price: round(price, 2)},
        {"name": "name", "selector": ".product", "type": str, "default": "NO NAME"},
        {"name": "description", "selector": "div.desc", "type": str, "default": None, "formatter": lambda desc: desc.lower()[:10]},
        {"name": "href", "selector": "div > a", "type": str, "attribute": "href"},
    ]
}

results = crawler.paginated_fetch(
    base_url="https://www.example.com/products?page={page}",
    start_page=1,
    end_page=10,
    interval_s=0.5,
    crawler_schema=schema,
    headers={"User-Agent": "Mozilla/5.0"},
)

print(results)
```

---

## Running Tests

```bash
python -m pytest -v
```

## Feature Roadmap for Crawl2Schema

We should plan and implement additional features to make Crawl2Schema more powerful, flexible, and user-friendly. Proposed features include:

### Core Features / Enhancements

- [ ] **Async Crawling:** Implement `AsyncHTTPCrawler` using `aiohttp` and `asyncio`.
- [ ] **Advanced Pagination:** Support dynamic pagination (e.g., “next page” buttons) and custom pagination rules.
- [ ] **URL Following / Crawling:** Follow links from a page using a schema field, with optional depth limits.
- [ ] **Output Options:** Save results to JSON, CSV, SQLite, or Pandas DataFrame.
- [ ] **Error Handling & Retry:** Retry failed requests with exponential backoff and log failures.
- [ ] **Rate Limiting & Throttling:** Control request frequency and per-domain concurrency.
- [ ] **Logging & Debugging:** Verbose mode and detailed logs for scraping steps.
- [ ] **Schema Enhancements:** Nested schemas, conditional scraping, and pre-processing functions.
- [ ] **Browser Support:** Add Playwright or Selenium crawler for JS-heavy pages.
- [ ] **Testing & Validation:** Schema validation and unit tests with mock HTML pages.

## Goal

Prioritize and implement these features in stages to improve Crawl2Schema’s usability and reliability.


---

## License

This project is licensed under the MIT License.
