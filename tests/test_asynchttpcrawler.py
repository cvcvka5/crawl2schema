import asyncio
import pytest
import aiohttp
from crawl2schema.crawler.http import AsyncHTTPCrawler, CrawlerSchema
from crawl2schema.exceptions import (
    RequestError,
    PaginationError,
    CrawlerError
)

def as_new_section(func):
    def inner():
        print(f"\n\n---\t{func.__name__}\t---\n")
        asyncio.run(func())
        print(f"\n---\tEND\t---")
    return inner

BASE_URL = "https://web-scraping.dev/products"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}

# --- Schemas ---

async_shallow_crawler_schema: CrawlerSchema = {
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

product_schema: CrawlerSchema = {
    "base_selector": "body",
    "fields": [
        {"name": "reviews", "type": "json", "selector": "script#reviews-data"},
        {"name": "suggested", "type": "list", "selector": "div.similar-products > a.product-preview", "list_subfields": [
            {"name": "name", "type": "text", "selector": "h3"},
            {"name": "price", "type": "number", "selector": "div.price"},
            {"name": "image", "type": "text", "attribute": "src", "selector": "img"},
        ]}
    ]
}

deep_async_crawler_schema: CrawlerSchema = {
    "base_selector": "div.product",
    "fields": [
        {"name": "name", "type": "text", "selector": "div.description > h3 > a",
         "postformatter": lambda name: name.strip().lower()},
        {"name": "href", "type": "text", "selector": "div.description > h3 > a",
         "attribute": "href", "postformatter": lambda url: url.replace("https://web-scraping.dev", "")},
        {"name": "short_description", "type": "text", "selector": "div.short-description",
         "postformatter": lambda desc: desc.strip().upper()[:30].strip()},
        {"name": "price", "type": "number", "selector": "div.price"},
        {"type": "text", "selector": "div.description > h3 > a", "attribute": "href", "url_follow_schema": product_schema}
    ]
}

# --- Tests ---

@as_new_section
async def test_async_webpage_live():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(BASE_URL) as resp:
            assert resp.status == 200
            print("Webpage is LIVE.")

@as_new_section
async def test_async_shallow_httpcrawler():
    crawler = AsyncHTTPCrawler()
    products = await crawler.fetch(BASE_URL, schema=async_shallow_crawler_schema, headers=HEADERS)
    
    print(len(products), products)
    assert len(products) == 5
    for product in products:
        assert all(field["name"] in product for field in async_shallow_crawler_schema["fields"])
        assert None not in product.values()
        assert len(product["short_description"]) <= 30

@as_new_section
async def test_async_product_reviews():
    crawler = AsyncHTTPCrawler()
    product_url = f"{BASE_URL[:-1]}/5"
    data = await crawler.fetch(product_url, schema=product_schema, headers=HEADERS)
    
    print(data)
    assert len(data) > 0
    for product in data:
        assert "reviews" in product
        assert isinstance(product["reviews"], list)

@as_new_section
async def test_async_url_follow_httpcrawler():
    crawler = AsyncHTTPCrawler()
    data = await crawler.fetch(BASE_URL, schema=deep_async_crawler_schema, headers=HEADERS)
    
    print(data)
    assert len(data) == 5
    for product in data:
        assert all(field["name"] in product for field in async_shallow_crawler_schema["fields"])
        assert None not in product.values()
        assert len(product["short_description"]) <= 30
        assert "reviews" in product
        assert isinstance(product["reviews"], list)

@as_new_section
async def test_async_paginated_shallow_httpcrawler():
    base_url = "https://web-scraping.dev/products?page={page_index}"
    shallow_paginated_schema = async_shallow_crawler_schema.copy()
    shallow_paginated_schema["pagination"] = {
        "page_placeholder": "{page_index}",
        "start_page": 1,
        "end_page": 5
    }
    
    crawler = AsyncHTTPCrawler()
    data = await crawler.fetch(base_url, schema=shallow_paginated_schema, headers=HEADERS)
    
    print(data)
    assert len(data) == 25
    for product in data:
        assert all(field["name"] in product for field in async_shallow_crawler_schema["fields"])
        assert None not in product.values()
        assert len(product["short_description"]) <= 30

@as_new_section
async def test_async_paginated_url_follow_httpcrawler():
    base_url = "https://web-scraping.dev/products?page={page_index}"
    deep_paginated_schema = deep_async_crawler_schema.copy()
    deep_paginated_schema["pagination"] = {
        "page_placeholder": "{page_index}",
        "start_page": 1,
        "end_page": 5
    }
    
    crawler = AsyncHTTPCrawler()
    data = await crawler.fetch(base_url, schema=deep_paginated_schema, headers=HEADERS)
    
    print(data)
    assert len(data) == 25
    for product in data:
        assert "reviews" in product
        assert isinstance(product["reviews"], list)
        assert all(field["name"] in product for field in async_shallow_crawler_schema["fields"])
        assert None not in product.values()
        assert len(product["short_description"]) <= 30

# --- Concurrency / Semaphore tests ---

@as_new_section
async def test_async_multiple_concurrent_fetches():
    crawler = AsyncHTTPCrawler()
    urls = [f"{BASE_URL}?page={i}" for i in range(1, 4)]
    
    tasks = [crawler.fetch(url, schema=async_shallow_crawler_schema, headers=HEADERS) for url in urls]
    results = await asyncio.gather(*tasks)
    
    total = sum(len(r) for r in results)
    print(f"Fetched {total} products concurrently from {len(urls)} URLs")
    
    assert total == 15

@as_new_section
async def test_async_semaphore_limited_fetch():
    crawler = AsyncHTTPCrawler()
    urls = [f"{BASE_URL}?page={i}" for i in range(1, 6)]
    semaphore = asyncio.Semaphore(2)
    
    async def sem_fetch(url):
        async with semaphore:
            return await crawler.fetch(url, schema=async_shallow_crawler_schema, headers=HEADERS)
    
    tasks = [sem_fetch(url) for url in urls]
    results = await asyncio.gather(*tasks)
    
    total = sum(len(r) for r in results)
    print(f"Fetched {total} products with semaphore limit 2")
    
    assert total == 25

# ─────────────────────
#  Async Exception Tests
# ─────────────────────

@as_new_section
async def test_async_request_error():
    """Should raise RequestError for invalid/bad responses."""
    crawler = AsyncHTTPCrawler()
    bad_url = "https://httpbin.org/status/500"

    with pytest.raises(RequestError):
        await crawler.fetch(bad_url, schema=async_shallow_crawler_schema, headers=HEADERS)


@as_new_section
async def test_async_crawler_error():
    """Should raise CrawlerError on unexpected internal exception."""
    crawler = AsyncHTTPCrawler()
    broken_schema = {
        "base_selector": "body",
        "fields": [{"name": "test", "type": "text", "selector": "body", "postformatter": "not_callable"}]
    }

    with pytest.raises(CrawlerError):
        await crawler.fetch(BASE_URL, schema=broken_schema, headers=HEADERS)


@as_new_section
async def test_async_pagination_error():
    """Should raise PaginationError for invalid pagination schema."""
    crawler = AsyncHTTPCrawler()
    bad_schema = async_shallow_crawler_schema.copy()
    bad_schema["pagination"] = {
        "page_placeholder": "{page_index}",
        "start_page": 1,
        "end_page": "not-an-int",
        "interval": 1.0
    }

    base_url = "https://web-scraping.dev/products?page={page_index}"
    with pytest.raises(PaginationError):
        await crawler.fetch(base_url, schema=bad_schema, headers=HEADERS)


# Run all async tests directly
if __name__ == "__main__":
    test_async_webpage_live()
    test_async_shallow_httpcrawler()
    test_async_product_reviews()
    test_async_url_follow_httpcrawler()
    test_async_paginated_shallow_httpcrawler()
    test_async_paginated_url_follow_httpcrawler()
    test_async_multiple_concurrent_fetches()
    test_async_semaphore_limited_fetch()

    test_async_request_error()
    test_async_crawler_error()
    test_async_pagination_error()