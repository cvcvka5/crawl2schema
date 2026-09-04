import asyncio
import pytest

from crawl2schema.crawler.http import SyncHTTPCrawler, AsyncHTTPCrawler
from crawl2schema.exceptions import InvalidSchema, PaginationError, RequestError


class FakeSyncResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status={self.status_code}")


class FakeSyncSession:
    def __init__(self, payload_by_url):
        self.payload_by_url = payload_by_url
        self.calls = []

    def get(self, url, *args, **kwargs):
        self.calls.append(url)
        if url not in self.payload_by_url:
            raise RuntimeError(f"missing url {url}")
        return FakeSyncResponse(self.payload_by_url[url])

    def close(self):
        return None


class FakeAsyncResponse:
    def __init__(self, text: str, status_code: int = 200):
        self._text = text
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status={self.status_code}")

    async def text(self):
        return self._text


class FakeAsyncSession:
    def __init__(self, payload_by_url):
        self.payload_by_url = payload_by_url
        self.calls = []
        self.closed = False

    def get(self, url, *args, **kwargs):
        self.calls.append(url)
        if url not in self.payload_by_url:
            raise RuntimeError(f"missing url {url}")
        return FakeAsyncResponse(self.payload_by_url[url])

    async def close(self):
        self.closed = True


def test_sync_resolves_relative_nested_url():
    main_url = "https://example.com/products"
    detail_url = "https://example.com/p/1"
    session = FakeSyncSession(
        {
            main_url: """
            <div class='product'>
                <a class='link' href='/p/1'>Product</a>
            </div>
            """,
            detail_url: "<body><script id='reviews-data'>[{\"score\": 5}]</script></body>",
        }
    )
    crawler = SyncHTTPCrawler(session=session)
    schema = {
        "base_selector": "div.product",
        "fields": [
            {
                "name": "details",
                "selector": "a.link",
                "attribute": "href",
                "type": "text",
                "url_follow_schema": {
                    "base_selector": "body",
                    "fields": [{"name": "reviews", "selector": "script#reviews-data", "type": "json"}],
                },
            }
        ],
    }

    data = crawler.fetch(main_url, schema=schema)

    assert detail_url in session.calls
    assert data[0]["details"]["reviews"][0]["score"] == 5


def test_sync_schema_validation_errors():
    crawler = SyncHTTPCrawler(session=FakeSyncSession({}))

    with pytest.raises(InvalidSchema):
        crawler.fetch("https://example.com", schema={"fields": []})

    with pytest.raises(PaginationError):
        crawler.fetch(
            "https://example.com/products",
            schema={
                "base_selector": "div.product",
                "fields": [{"name": "name", "selector": "h3", "type": "text"}],
                "url_pagination": {"start_page": 1, "end_page": 2, "page_placeholder": "{page}"},
            },
        )


def test_async_resolves_relative_nested_url():
    async def run():
        main_url = "https://example.com/products"
        detail_url = "https://example.com/p/1"
        session = FakeAsyncSession(
            {
                main_url: """
                <div class='product'>
                    <a class='link' href='/p/1'>Product</a>
                </div>
                """,
                detail_url: "<body><script id='reviews-data'>[{\"score\": 4}]</script></body>",
            }
        )
        crawler = AsyncHTTPCrawler(session=session)
        schema = {
            "base_selector": "div.product",
            "fields": [
                {
                    "name": "details",
                    "selector": "a.link",
                    "attribute": "href",
                    "type": "text",
                    "url_follow_schema": {
                        "base_selector": "body",
                        "fields": [{"name": "reviews", "selector": "script#reviews-data", "type": "json"}],
                    },
                }
            ],
        }

        data = await crawler.fetch(main_url, schema=schema)
        assert detail_url in session.calls
        assert data[0]["details"]["reviews"][0]["score"] == 4

    asyncio.run(run())


def test_async_wraps_request_errors():
    class BrokenSession:
        closed = False

        def get(self, *_args, **_kwargs):
            raise RuntimeError("network down")

        async def close(self):
            return None

    async def run():
        crawler = AsyncHTTPCrawler(session=BrokenSession())
        schema = {
            "base_selector": "div.product",
            "fields": [{"name": "name", "selector": "h3", "type": "text"}],
        }
        with pytest.raises(RequestError):
            await crawler.fetch("https://example.com", schema=schema)

    asyncio.run(run())
