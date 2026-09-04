import asyncio
import copy
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
        self.payload_by_url = copy.deepcopy(payload_by_url)
        self.calls = []

    def get(self, url, *args, **kwargs):
        self.calls.append(url)
        if url not in self.payload_by_url:
            raise RuntimeError(f"missing url {url}")

        payload = self.payload_by_url[url]
        if isinstance(payload, list):
            if not payload:
                raise RuntimeError(f"no payload left for {url}")
            payload = payload.pop(0)

        if isinstance(payload, Exception):
            raise payload

        if isinstance(payload, dict):
            return FakeSyncResponse(payload.get("text", ""), payload.get("status_code", 200))

        return FakeSyncResponse(payload)

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
        self.payload_by_url = copy.deepcopy(payload_by_url)
        self.calls = []
        self.closed = False

    def get(self, url, *args, **kwargs):
        self.calls.append(url)
        if url not in self.payload_by_url:
            raise RuntimeError(f"missing url {url}")

        payload = self.payload_by_url[url]
        if isinstance(payload, list):
            if not payload:
                raise RuntimeError(f"no payload left for {url}")
            payload = payload.pop(0)

        if isinstance(payload, Exception):
            raise payload

        if isinstance(payload, dict):
            return FakeAsyncResponse(payload.get("text", ""), payload.get("status_code", 200))

        return FakeAsyncResponse(payload)

    async def close(self):
        self.closed = True


def _nested_schema():
    return {
        "base_selector": "body",
        "fields": [{"name": "reviews", "selector": "script#reviews-data", "type": "json"}],
    }


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
                "url_follow_schema": _nested_schema(),
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


def test_sync_retries_then_success():
    url = "https://example.com/products"
    session = FakeSyncSession(
        {
            url: [
                RuntimeError("temporary"),
                "<div class='product'><h3>Recovered</h3></div>",
            ]
        }
    )
    crawler = SyncHTTPCrawler(session=session)
    schema = {
        "base_selector": "div.product",
        "fields": [{"name": "name", "selector": "h3", "type": "text"}],
        "request_retry": {"attempts": 2, "delay": 0},
    }

    data = crawler.fetch(url, schema=schema)

    assert len([call for call in session.calls if call == url]) == 2
    assert data[0]["name"] == "Recovered"


def test_sync_nested_caching_avoids_duplicate_fetches():
    main_url = "https://example.com/products"
    detail_url = "https://example.com/p/1"
    session = FakeSyncSession(
        {
            main_url: """
            <div class='product'><a class='link' href='/p/1'>A</a></div>
            <div class='product'><a class='link' href='/p/1'>B</a></div>
            """,
            detail_url: "<body><script id='reviews-data'>[{\"score\": 7}]</script></body>",
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
                "url_follow_schema": _nested_schema(),
                "cache_nested_requests": True,
            }
        ],
        "cache_nested_requests": True,
    }

    data = crawler.fetch(main_url, schema=schema)

    assert len(data) == 2
    assert len([call for call in session.calls if call == detail_url]) == 1


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
                    "url_follow_schema": _nested_schema(),
                }
            ],
        }

        data = await crawler.fetch(main_url, schema=schema)
        assert detail_url in session.calls
        assert data[0]["details"]["reviews"][0]["score"] == 4

    asyncio.run(run())


def test_async_retries_then_success():
    async def run():
        url = "https://example.com/products"
        session = FakeAsyncSession(
            {
                url: [
                    RuntimeError("temporary"),
                    "<div class='product'><h3>Recovered</h3></div>",
                ]
            }
        )
        crawler = AsyncHTTPCrawler(session=session)
        schema = {
            "base_selector": "div.product",
            "fields": [{"name": "name", "selector": "h3", "type": "text"}],
            "request_retry": {"attempts": 2, "delay": 0},
        }

        data = await crawler.fetch(url, schema=schema)

        assert len([call for call in session.calls if call == url]) == 2
        assert data[0]["name"] == "Recovered"

    asyncio.run(run())


def test_async_nested_caching_avoids_duplicate_fetches():
    async def run():
        main_url = "https://example.com/products"
        detail_url = "https://example.com/p/1"
        session = FakeAsyncSession(
            {
                main_url: """
                <div class='product'><a class='link' href='/p/1'>A</a></div>
                <div class='product'><a class='link' href='/p/1'>B</a></div>
                """,
                detail_url: "<body><script id='reviews-data'>[{\"score\": 9}]</script></body>",
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
                    "url_follow_schema": _nested_schema(),
                }
            ],
            "cache_nested_requests": True,
        }

        data = await crawler.fetch(main_url, schema=schema)

        assert len(data) == 2
        assert len([call for call in session.calls if call == detail_url]) == 1

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


def test_async_supports_async_on_pageload_callback():
    async def run():
        main_url = "https://example.com/products"
        session = FakeAsyncSession(
            {
                main_url: "<div class='product'><h3>Item</h3></div>",
            }
        )
        crawler = AsyncHTTPCrawler(session=session)
        callback_log = []

        async def on_pageload(resp):
            callback_log.append(resp.status_code)

        schema = {
            "base_selector": "div.product",
            "fields": [{"name": "name", "selector": "h3", "type": "text"}],
            "on_pageload": on_pageload,
        }
        await crawler.fetch(main_url, schema=schema)
        assert callback_log == [200]

    asyncio.run(run())
