# Crawl2Schema

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

---

## License

This project is licensed under the MIT License.
