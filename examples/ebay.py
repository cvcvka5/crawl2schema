from crawl2schema.crawler.browser import SyncBrowserCrawler
from crawl2schema.crawler.schema import BrowserCrawlerSchema
from pprint import pprint
import re

# helper functions
def clean_text(text: str) -> str:
    return text.replace("\n", " ").strip()

def price_to_number(price: str) -> int | float:
    price = price.replace(",", "").strip()
    return re.match(r"^\$(\d*\.\d*)$", price).group(1)

crawler = SyncBrowserCrawler(headless=False)
schema: BrowserCrawlerSchema = {
    "base_selector": "li.s-card[id^=item]",
    "fields": [
        { "name": "title", "selector": "span.primary.default", "type": "text", "postformatter": clean_text },
        { "name": "price", "selector": "span.s-card__price", "type": "number", "preformatter": price_to_number},
        { "name": "owner", "selector": "div.su-card-container__attributes__secondary > div > span", "type": "text" },
        { "name": "image", "selector": "img", "type": "text", "attribute": "src"},
        { "name": "url", "selector": "a", "type": "text", "attribute": "href" }
    ],
    "url_pagination": {
        "end_page": 20
    },
    "wait_for_selector": { "selector": "li.s-card[id^=item]"}
}

base_url = "https://www.ebay.com/sch/i.html?_nkw=bicycle&_pgn={page}"
data = crawler.fetch(base_url, schema=schema)

pprint(data)
pprint(len(data))