import pytest
import requests
from crawl2schema.crawler.http import SyncHTTPCrawler

base_url = "https://web-scraping.dev/products"
pagination_url = "https://web-scraping.dev/products?page={page}"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}

def test_webpage_live():
    assert requests.get(base_url).status_code == 200
    

shallow_crawler_schema = {
    "baseSelector": "div.products",
    "targetElements": [
        {"name": "name", "type": str, "selector": "div.description > h3 > a", "formatter": lambda name: name.strip().lower()},                           
        {"name": "href", "type": str, "selector": "div.description > h3 > a", "attribute": "href", "formatter": lambda url: url.replace("https://web-scraping.dev", "")},                           
        {"name": "short-description", "type": str, "selector": "div.short-description", "formatter": lambda desc: desc.strip().upper()[:30].strip()},
        {"name": "price", "type": float, "selector": "div.price"}                          
    ]
}
def test_sync_shallow_httpcrawler():
    sync_crawler = SyncHTTPCrawler()
    
    products_data_1 = sync_crawler.fetch(base_url, crawler_schema=shallow_crawler_schema, headers=headers)
    
    assert len(products_data_1) == 5
    assert list(products_data_1[0].keys()) == [elDict["name"] for elDict in shallow_crawler_schema.get("targetElements", [])]
    assert None not in products_data_1[0].values()
    assert len(products_data_1[0]["short-description"]) <= 30
    
def test_sync_shallow_paginated_httpcrawler():
    sync_crawler = SyncHTTPCrawler()
    
    paginated_products = sync_crawler.paginated_fetch(base_url=pagination_url, start_page=1, end_page=5, crawler_schema=shallow_crawler_schema, headers=headers)
    
    assert len(paginated_products) == 25
    assert list(paginated_products[10].keys()) == [elDict["name"] for elDict in shallow_crawler_schema.get("targetElements", [])]
    assert None not in paginated_products[10].values()
    assert len(paginated_products[10]["short-description"]) <= 30
    