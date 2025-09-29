import pytest
import requests
from crawl2schema.crawler.http import SyncHTTPCrawler, CrawlerSchema

def as_new_section(func):
    def inner():
        print(f"\n\n---\t{func.__name__}\t---\n")
        func()
        print(f"\n---\tEND\t---")
    return inner

BASE_URL = "https://web-scraping.dev/products"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}

@as_new_section
def test_webpage_live():
    """Ensure the webpage is up."""
    assert requests.get(BASE_URL, headers=HEADERS).status_code == 200
    print("Webpage is LIVE.")

shallow_crawler_schema: CrawlerSchema = {
    "base_selector": "div.product",
    "fields": [
        {"name": "name", "type": "text", "selector": "div.description > h3 > a", "formatter": lambda name: name.strip().lower()},
        {"name": "href", "type": "text", "selector": "div.description > h3 > a", "attribute": "href", "formatter": lambda url: url.replace("https://web-scraping.dev", "")},
        {"name": "short_description", "type": "text", "selector": "div.short-description", "formatter": lambda desc: desc.strip().upper()[:30].strip()},
        {"name": "price", "type": "number", "selector": "div.price"},
    ]
}

@as_new_section
def test_sync_shallow_httpcrawler():
    sync_crawler = SyncHTTPCrawler()
    products = sync_crawler.fetch(BASE_URL, schema=shallow_crawler_schema, headers=HEADERS)
    
    
    print(len(products), products)
    
    assert len(products) == 5
    for product in products:
        assert all(field["name"] in product for field in shallow_crawler_schema["fields"])
        assert None not in product.values()
        assert len(product["short_description"]) <= 30

product_schema: CrawlerSchema = {
    "base_selector": "script#reviews-data",
    "fields": [
        {"name": "reviews", "type": "json", "selector": "*"}
    ]
}

@as_new_section
def test_sync_product_reviews():
    sync_crawler = SyncHTTPCrawler()
    product_url = f"{BASE_URL[:-1]}/5"
    data = sync_crawler.fetch(product_url, schema=product_schema, headers=HEADERS)
    
    print(data)
    
    assert len(data) > 0
    for record in data:
        assert "reviews" in record
        assert isinstance(record["reviews"], list)

deep_crawler_schema: CrawlerSchema = {
    "base_selector": "div.product",
    "fields": [
        {"name": "name", "type": "text", "selector": "div.description > h3 > a", "formatter": lambda name: name.strip().lower()},
        {"name": "href", "type": "text", "selector": "div.description > h3 > a", "attribute": "href", "formatter": lambda url: url.replace("https://web-scraping.dev", "")},
        {"name": "short_description", "type": "text", "selector": "div.short-description", "formatter": lambda desc: desc.strip().upper()[:30].strip()},
        {"name": "price", "type": "number", "selector": "div.price"},
        
        {"type": "text", "selector": "div.description > h3 > a", "attribute": "href", "follow_schema": product_schema}
    ]
}

@as_new_section
def test_sync_url_follow_httpcrawler():
    sync_crawler = SyncHTTPCrawler()
    data = sync_crawler.fetch(BASE_URL, schema=deep_crawler_schema, headers=HEADERS)
    
    print(data)
    
    assert len(data) == 5
    for product in data:
        assert "reviews" in product
        assert isinstance(product["reviews"], list)

# Run all tests when executing directly
if __name__ == "__main__":

    test_webpage_live()
    test_sync_shallow_httpcrawler()
    test_sync_product_reviews()
    test_sync_url_follow_httpcrawler()
