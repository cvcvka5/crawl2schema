from typing import List, Dict, Any, Callable, Optional
import asyncio
import aiohttp
import json
from selectolax.parser import HTMLParser
from ..schema import CrawlerSchema, FieldSchema, URLPaginationSchema
from ...exceptions import InvalidSchema
import requests


class SyncHTTPCrawler:
    """
    A synchronous HTML crawler that extracts structured data from web pages
    based on a provided CrawlerSchema.

    Features:
    - base_selector selects multiple parent elements (one record per parent)
    - fields can extract text, numbers, or lists inside each parent element
    - supports attributes, default values, preformatter and postformatter callables
    - supports nested schemas via `url_follow_schema`
    - supports structured lists via `list_subfields` (list of objects)
    """

    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.session = session or requests.Session()
        self._close_session = False


    def fetch(self, url: str, schema: CrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        pagination = schema.get("pagination", None)
        urls: List[str] = []

        if pagination is None:
            urls = [url]
        elif pagination.get("page_placeholder"):
            start = pagination.get("start_page", 1)
            end = pagination.get("end_page", 1)
            placeholder = pagination.get("page_placeholder", "{page}")
            urls = [url.replace(placeholder, str(i)) for i in range(start, end + 1)]
        else:
            raise InvalidSchema(
                f"Invalid pagination schema for SyncHTTPCrawler, allowed types are: {None} and {URLPaginationSchema}"
            )

        records: List[Dict[str, Any]] = []
        for url in urls:
            response = self.session.get(url, *args, **kwargs)
            response.raise_for_status()
            tree = HTMLParser(response.text)
            records.extend(self._extract_from_tree(tree, schema, *args, **kwargs))
        return records

    def _extract_from_tree(self, tree: HTMLParser, schema: CrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        base_elements = tree.css(schema.get("base_selector", "body"))
        fields: List[FieldSchema] = schema.get("fields", [])
        records: List[Dict[str, Any]] = []

        for parent in base_elements:
            record: Dict[str, Any] = {}
            for field in fields:
                selector = field["selector"]
                attr = field.get("attribute")
                default = field.get("default")
                type_ = field.get("type", "text")
                preformatter: Optional[Callable] = field.get("preformatter")
                postformatter: Optional[Callable] = field.get("postformatter")
                url_follow_schema = field.get("url_follow_schema")

                if type_ == "list":
                    record[field["name"]] = self._extract_list_field(parent, field)
                    continue

                el = parent.css_first(selector)
                raw = default
                if el:
                    raw = el.text(strip=True) if not attr else el.attributes.get(attr, default)

                value: Any = self._apply_formatters(raw, preformatter, postformatter, type_, default)

                if url_follow_schema and isinstance(value, str):
                    nested = self.fetch(value, url_follow_schema, *args, **kwargs)
                    if isinstance(nested, list):
                        for item in nested:
                            record.update(item)
                    else:
                        record.update(nested)
                else:
                    record[field["name"]] = value
            records.append(record)
        return records

    def _extract_list_field(self, parent, field: FieldSchema):
        values: List[Any] = []
        selector = field["selector"]
        attr = field.get("attribute")
        default = field.get("default")
        type_ = field.get("type", "text")
        preformatter = field.get("preformatter")
        postformatter = field.get("postformatter")
        list_subfields = field.get("list_subfields")

        for el in parent.css(selector):
            if list_subfields:
                obj: Dict[str, Any] = {}
                for subfield in list_subfields:
                    subel = el.css_first(subfield["selector"])
                    subattr = subfield.get("attribute")
                    subdefault = subfield.get("default")
                    subtype = subfield.get("type", "text")
                    sub_pre = subfield.get("preformatter")
                    sub_post = subfield.get("postformatter")

                    subraw = subdefault
                    if subel:
                        subraw = subel.text(strip=True) if not subattr else subel.attributes.get(subattr, subdefault)
                    subval = self._apply_formatters(subraw, sub_pre, sub_post, subtype, subdefault)
                    obj[subfield["name"]] = subval
                values.append(obj)
            else:
                raw = el.text(strip=True) if not attr else el.attributes.get(attr, default)
                val = self._apply_formatters(raw, preformatter, postformatter, type_, default)
                values.append(val)
        return values

    def _apply_formatters(self, value, pre, post, type_, default):
        if pre:
            value = pre(value)
        try:
            if type_ == "number":
                value = float(value)
                if value.is_integer():
                    value = int(value)
            elif type_ == "json":
                value = json.loads(value)
            elif type_ == "text":
                value = str(value)
        except Exception:
            value = default
        if post:
            value = post(value)
        return value

    def __enter__(self):
        if self.session is None:
            self.session = requests.Session()
            self._close_session = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._close_session and self.session:
            self.session.close()

class AsyncHTTPCrawler:
    """
    Fully asynchronous HTML crawler.

    Features:
    - Supports text, number, json, list fields
    - Handles attributes, default values, pre/postformatters
    - Nested schemas via url_follow_schema
    - Structured lists via list_subfields
    - Pagination support
    - Optional external session reuse
    - Concurrency limit via semaphore
    """

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        max_concurrency: int = 10,
        timeout: int = 20
    ) -> None:
        self.external_session = session
        self.session: Optional[aiohttp.ClientSession] = session
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit_per_host=10, ssl=False)
            self.session = aiohttp.ClientSession(connector=connector, timeout=self.timeout)
        return self.session

    async def close(self):
        """Close session if it was internally created."""
        if self.session and not self.session.closed and not self.external_session:
            await self.session.close()

    async def fetch(self, url: str, schema: CrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        """Fetch data from a URL or paginated URLs using the provided schema."""
        pagination = schema.get("pagination")
        urls: List[str] = []

        if pagination is None:
            urls = [url]
        elif pagination.get("page_placeholder"):
            start = pagination.get("start_page", 1)
            end = pagination.get("end_page", 1)
            placeholder = pagination.get("page_placeholder", "{page}")
            urls = [url.replace(placeholder, str(i)) for i in range(start, end + 1)]
        else:
            raise InvalidSchema(
                f"Invalid pagination schema for AsyncHTTPCrawler, allowed types: None and {URLPaginationSchema}"
            )

        session = await self._get_session()

        tasks = [self._fetch_page(u, schema, *args, **kwargs) for u in urls]
        results = await asyncio.gather(*tasks)
        # Flatten the list of lists
        return [r for sublist in results for r in sublist]

    async def _fetch_page(self, url: str, schema: CrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        async with self.semaphore:
            session = await self._get_session()
            async with session.get(url, *args, **kwargs) as resp:
                resp.raise_for_status()
                html = await resp.text()
                tree = HTMLParser(html)
                return await self._extract_from_tree(tree, schema, *args, **kwargs)

    async def _extract_from_tree(self, tree: HTMLParser, schema: CrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        base_elements = tree.css(schema.get("base_selector", "body"))
        fields: List[FieldSchema] = schema.get("fields", [])
        records: List[Dict[str, Any]] = []

        for parent in base_elements:
            record: Dict[str, Any] = {}
            for field in fields:
                selector = field.get("selector")
                attr = field.get("attribute")
                default = field.get("default")
                type_ = field.get("type", "text")
                preformatter: Optional[Callable] = field.get("preformatter")
                postformatter: Optional[Callable] = field.get("postformatter")
                url_follow_schema = field.get("url_follow_schema")

                if type_ == "list":
                    record[field["name"]] = await self._extract_list_field(parent, field, *args, **kwargs)
                    continue

                el = parent.css_first(selector) if selector else None
                raw = default
                if el:
                    raw = el.text(strip=True) if not attr else el.attributes.get(attr, default)

                value = self._apply_formatters(raw, preformatter, postformatter, type_, default)

                # Nested fetch for url_follow_schema
                if url_follow_schema and isinstance(value, str):
                    nested = await self.fetch(value, url_follow_schema, *args, **kwargs)
                    # merge nested keys into record
                    if isinstance(nested, list):
                        for item in nested:
                            record.update(item)
                    else:
                        record.update(nested)
                else:
                    record[field["name"]] = value

            records.append(record)
        return records

    async def _extract_list_field(self, parent, field: FieldSchema, *args, **kwargs) -> List[Any]:
        values: List[Any] = []
        selector = field.get("selector")
        attr = field.get("attribute")
        default = field.get("default")
        type_ = field.get("type", "text")
        preformatter = field.get("preformatter")
        postformatter = field.get("postformatter")
        list_subfields = field.get("list_subfields")

        for el in parent.css(selector):
            if list_subfields:
                obj: Dict[str, Any] = {}
                for subfield in list_subfields:
                    subel = el.css_first(subfield["selector"])
                    subattr = subfield.get("attribute")
                    subdefault = subfield.get("default")
                    subtype = subfield.get("type", "text")
                    sub_pre = subfield.get("preformatter")
                    sub_post = subfield.get("postformatter")

                    subraw = subdefault
                    if subel:
                        subraw = subel.text(strip=True) if not subattr else subel.attributes.get(subattr, subdefault)
                    subval = self._apply_formatters(subraw, sub_pre, sub_post, subtype, subdefault)
                    obj[subfield["name"]] = subval
                values.append(obj)
            else:
                raw = el.text(strip=True) if not attr else el.attributes.get(attr, default)
                val = self._apply_formatters(raw, preformatter, postformatter, type_, default)
                values.append(val)
        return values

    def _apply_formatters(self, value, pre, post, type_, default):
        if pre:
            value = pre(value)
        try:
            if type_ == "number":
                value = float(value)
                if value.is_integer():
                    value = int(value)
            elif type_ == "json":
                value = json.loads(value)
            elif type_ == "text":
                value = str(value)
        except Exception:
            value = default
        if post:
            value = post(value)
        return value
    
    async def __aenter__(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._close_session = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._close_session and self.session:
            await self.session.close()

__all__ = ["SyncHTTPCrawler", "AsyncHTTPCrawler"]