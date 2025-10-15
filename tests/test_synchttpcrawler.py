import pytest
import requests
import copy
from selectolax.parser import HTMLParser
from crawl2schema.crawler.http import SyncHTTPCrawler
from crawl2schema.crawler.schema import HTTPCrawlerSchema
from crawl2schema.exceptions import (
    InvalidSchema,
    RequestError,
    ParseError,
    FormatterError,
    PaginationError,
    CrawlerError
)

def as_new_section(func):
    def inner():
        print(f"\n\n---\t{func.__name__}\t---\n")
        try:
            func()
        except Exception as e:
            print(f"[EXCEPTION] {type(e).__name__}: {e}")
            raise
        print(f"\n---\tEND\t---")
    return inner


BASE_URL = "https://web-scraping.dev/products"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}


@as_new_section
def test_webpage_live():
    assert requests.get(BASE_URL, headers=HEADERS).status_code == 200
    print("Webpage is LIVE.")


shallow_crawler_schema: HTTPCrawlerSchema = {
    "base_selector": "div.product",
    "fields": [
        {"name": "name", "type": "text", "selector": "div.description > h3 > a",
         "postformatter": lambda name: name.strip().lower()},
        {"name": "href", "type": "text", "selector": "div.description > h3 > a",
         "attribute": "href", "postformatter": lambda url: url.replace("https://web-scraping.dev", "")},
        {"name": "short_description", "type": "text", "selector": "div.short-description",
         "postformatter": lambda desc: desc.strip().upper()[:30].strip()},
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


product_schema: HTTPCrawlerSchema = {
    "base_selector": "body",
    "fields": [
        {"name": "reviews", "type": "json", "selector": "script#reviews-data"},
        {"name": "suggested", "type": "list", "selector": "div.similar-products > a.product-preview",
         "list_subfields": [
             {"name": "name", "type": "text", "selector": "h3"},
             {"name": "price", "type": "number", "selector": "div.price"},
             {"name": "image", "type": "text", "attribute": "src", "selector": "img"},
         ]}
    ]
}


@as_new_section
def test_sync_product_reviews():
    sync_crawler = SyncHTTPCrawler()
    product_url = f"{BASE_URL[:-1]}/5"
    data = sync_crawler.fetch(product_url, schema=product_schema, headers=HEADERS)

    print(data)
    assert len(data) > 0
    for product in data:
        assert "reviews" in product
        assert isinstance(product["reviews"], list)


deep_crawler_schema: HTTPCrawlerSchema = copy.deepcopy(shallow_crawler_schema)
deep_crawler_schema["fields"].append({
    "type": "text", "selector": "div.description > h3 > a", "attribute": "href", "url_follow_schema": product_schema
})


@as_new_section
def test_sync_url_follow_httpcrawler():
    sync_crawler = SyncHTTPCrawler()
    data = sync_crawler.fetch(BASE_URL, schema=deep_crawler_schema, headers=HEADERS)

    print(data)
    assert len(data) == 5
    for product in data:
        assert all(field["name"] in product for field in shallow_crawler_schema["fields"])
        assert None not in product.values()
        assert len(product["short_description"]) <= 30
        assert "reviews" in product
        assert isinstance(product["reviews"], list)


@as_new_section
def test_sync_paginated_shallow_httpcrawler():
    base_url = "https://web-scraping.dev/products?page={page_index}"

    shallow_paginated_crawler_schema = copy.deepcopy(shallow_crawler_schema)
    shallow_paginated_crawler_schema["url_pagination"] = {
        "page_placeholder": "{page_index}",
        "start_page": 1,
        "end_page": 5,
        "interval": 1.0
    }

    sync_crawler = SyncHTTPCrawler()
    data = sync_crawler.fetch(url=base_url, schema=shallow_paginated_crawler_schema, headers=HEADERS)

    print(data)
    assert len(data) == 25
    for product in data:
        assert all(field["name"] in product for field in shallow_crawler_schema["fields"])
        assert None not in product.values()
        assert len(product["short_description"]) <= 30


@as_new_section
def test_sync_paginated_url_follow_shallow_httpcrawler():
    base_url = "https://web-scraping.dev/products?page={page_index}"

    deep_paginated_crawler_schema = copy.deepcopy(deep_crawler_schema)
    deep_paginated_crawler_schema["url_pagination"] = {
        "page_placeholder": "{page_index}",
        "start_page": 1,
        "end_page": 5,
        "interval": 1.5
    }

    sync_crawler = SyncHTTPCrawler()
    data = sync_crawler.fetch(url=base_url, schema=deep_paginated_crawler_schema, headers=HEADERS)

    print(data)
    assert len(data) == 25
    for product in data:
        assert "reviews" in product
        assert isinstance(product["reviews"], list)
        assert all(field["name"] in product for field in shallow_crawler_schema["fields"])
        assert None not in product.values()
        assert len(product["short_description"]) <= 30


# ─────────────────────────────
# Exception Tests
# ─────────────────────────────

@as_new_section
def test_invalid_pagination_schema():
    sync_crawler = SyncHTTPCrawler()
    bad_schema = copy.deepcopy(shallow_crawler_schema)
    bad_schema["url_pagination"] = {"invalid_key": True}

    with pytest.raises(PaginationError):
        sync_crawler.fetch("https://example.com", schema=bad_schema)


@as_new_section
def test_request_error():
    sync_crawler = SyncHTTPCrawler()
    with pytest.raises(RequestError):
        sync_crawler.fetch("https://definitelynotarealurl.abcxyz", schema=shallow_crawler_schema)


@as_new_section
def test_pagination_error():
    sync_crawler = SyncHTTPCrawler()
    bad_pagination_schema = {
        "base_selector": "div.product",
        "fields": [{"name": "name", "type": "text", "selector": "h3"}],
        "url_pagination": {
            "page_placeholder": "{page}",  
            "start_page": "one",  
            "end_page": "five",
        }
    }

    with pytest.raises(PaginationError):
        sync_crawler.fetch(BASE_URL, schema=bad_pagination_schema)


@as_new_section
def test_sync_crawler_error():
    """Should raise CrawlerError on unexpected internal exception."""
    crawler = SyncHTTPCrawler()
    broken_schema = {
        "base_selector": "body",
        "fields": [{"name": "test", "type": "text", "selector": "body", "postformatter": "not_callable"}]
    }

    with pytest.raises(CrawlerError):
        crawler.fetch(BASE_URL, schema=broken_schema)


# ─────────────────────────────
# Manual Execution Entry Point
# ─────────────────────────────

if __name__ == "__main__":
    test_webpage_live()
    test_sync_shallow_httpcrawler()
    test_sync_product_reviews()
    test_sync_url_follow_httpcrawler()
    test_sync_paginated_shallow_httpcrawler()
    test_sync_paginated_url_follow_shallow_httpcrawler()
    
    test_invalid_pagination_schema()
    test_request_error()
    test_pagination_error()
    test_sync_crawler_error()
