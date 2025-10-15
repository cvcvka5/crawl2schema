from crawl2schema.crawler.browser import SyncBrowserCrawler
from crawl2schema.crawler.schema import BrowserCrawlerSchema
from pprint import pprint

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
pprint(data)
pprint(len(data))