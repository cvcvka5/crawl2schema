from crawl2schema.crawler.browser import SyncBrowserCrawler
from crawl2schema.crawler.schema import BrowserCrawlerSchema


crawler = SyncBrowserCrawler(headless=False)
schema: BrowserCrawlerSchema = {
    "base_selector": "div.review",
    "fields": [
        { "name": "text", "selector": "p", "type": "text", "preformatter": lambda text: text.replace("\n", "").strip() },
        { "name": "date", "selector": "span[data-testid='review-date']", "type": "text" },
        { "name": "rating", "selector": "span[data-testid='review-stars'] > svg", "type": "list", "list_formatter": len }
    ]
}

url = "https://web-scraping.dev/reviews"
data = crawler.fetch(url, schema=schema, wait_until="networkidle")
print(data)