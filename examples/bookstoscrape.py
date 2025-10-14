from crawl2schema.crawler.http import SyncHTTPCrawler
from crawl2schema.crawler.schema import HTTPCrawlerSchema
import json

def rating_formatter(rating):
    rating = rating.split(" ")[1].strip().lower()
    wrd_to_nmb = {"five": 5, "four": 4, "three": 3, "two": 2, "one": 1, "zero": 0}
    
    return wrd_to_nmb[rating]

def price_preformatter(price_raw):
    return price_raw[2:]

schema: HTTPCrawlerSchema = {
    "base_selector": "section li[class^=col]",
    "fields": [
        { "name": "name", "selector": "h3 a", "type": "text", "attribute": "title"},
        { "name": "price", "selector": "p.price_color", "type": "number", "preformatter": price_preformatter},
        { "name": "in-stock", "selector": "p.availability", "type": "bool", "postformatter": lambda text: text.strip().lower() == "in stock"},
        { "name": "rating",  "selector": "p.star-rating", "attribute": "class", "postformatter": rating_formatter},
        { "name": "image", "selector": "img", "type": "text", "attribute": "src", "postformatter": lambda url: "https://books.toscrape.com"+url[2:]},
        
        { "name": "url", "selector": "h3 a", "type": "text", "attribute": "href", "postformatter": lambda url: "https://books.toscrape.com/catalogue/"+url, "url_follow_schema": {
            "base_selector": "article.product_page",
            "fields": [
                {"name": "description", "type": "text", "selector": "div#product_description + p", "default": None},
                {"name": "upc", "type": "text", "selector": "tr:nth-child(1) td"},
                {"name": "type", "type": "text", "selector": "tr:nth-child(2) td"},
                {"name": "price_before_tax", "type": "number", "selector": "tr:nth-child(3) td", "preformatter": price_preformatter},
                {"name": "price_after_tax", "type": "number", "selector": "tr:nth-child(4) td", "preformatter": price_preformatter},
                {"name": "tax", "type": "number", "selector": "tr:nth-child(5) td", "preformatter": price_preformatter},
                {"name": "stock_count", "type": "number", "selector": "tr:nth-child(6) td", "preformatter": lambda text: text.replace("In stock (", "").replace(" available)", "").strip()},
                {"name": "review_count", "type": "number", "selector": "tr:nth-child(7) td"},
            ]
        }},
    ],
    "url_pagination": {
        "start_page": 1,
        "end_page": 5,
        "interval": 0,
        "page_placeholder": "{pgn}"
    }
}
base_url = "https://books.toscrape.com/catalogue/page-{pgn}.html"

crawler = SyncHTTPCrawler()

print("[STARTING] Crawler started.")

data = crawler.fetch(base_url, schema=schema)
print(data)

print("[DONE] Scraped", len(data), "books.")

with open("books_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f)