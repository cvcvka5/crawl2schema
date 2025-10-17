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

crawler = SyncBrowserCrawler()
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

pprint(data)
pprint(len(data))