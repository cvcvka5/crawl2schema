from typing import List, Dict, Any, Callable, Optional
import asyncio
import aiohttp
import json
from selectolax.parser import HTMLParser
from ..schema import HTTPCrawlerSchema, HTTPFieldSchema, URLPaginationSchema
from ...exceptions import InvalidSchema, CrawlerError, FormatterError, PaginationError, ParseError, RequestError
import requests


class SyncHTTPCrawler:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.session = session or requests.Session()
        self._close_session = False

    def fetch(self, url: str, schema: HTTPCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        pagination = schema.get("url_pagination", None)
        on_pageload = schema.get("on_pageload")
        urls: List[str] = []

        if pagination is None:
            urls = [url]
        else:
            try:
                start = pagination.get("start_page", 1)
                end = pagination["end_page"]
                placeholder = pagination.get("page_placeholder", "{page}")
                urls = [url.replace(placeholder, str(i)) for i in range(start, end + 1)]
            except Exception as e:
                raise PaginationError(f"Invalid pagination schema: {e}")

        records: List[Dict[str, Any]] = []
        for url in urls:
            try:
                response = self.session.get(url, *args, **kwargs)
                response.raise_for_status()
            except Exception as e:
                raise RequestError(f"Failed to fetch {url}: {e}") from e
            
            if on_pageload and callable(on_pageload):
                on_pageload(response)

            try:
                tree = HTMLParser(response.text)
            except Exception as e:
                raise ParseError(f"Failed to parse HTML from {url}: {e}") from e

            records.extend(self._extract_from_tree(tree, schema, *args, **kwargs))
        return records

    def _extract_from_tree(self, tree: HTMLParser, schema: HTTPCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        base_elements = tree.css(schema.get("base_selector", "body"))
        fields: List[HTTPFieldSchema] = schema.get("fields", [])
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
                    record[field["name"]] = self._extract_list_field(parent, field, *args, **kwargs)
                    continue

                el = parent.css_first(selector) if selector else None
                value = default
                if el:
                    value = el.text() if not attr else el.attributes.get(attr, default)
                    value = self._apply_formatters(value, preformatter, postformatter, type_, default)

                if url_follow_schema and isinstance(value, str) and value:
                    try:
                        nested = self.fetch(value, url_follow_schema, *args, **kwargs)
                        # Merge nested results
                        if isinstance(nested, list) and len(nested) == 1:
                            record[field["name"]] = nested[0]
                        elif isinstance(nested, list):
                            nested_obj = {}
                            for n in nested:
                                nested_obj.update(n)
                            record[field["name"]] = nested_obj
                        else:
                            record[field["name"]] = nested
                    except Exception as e:
                        raise CrawlerError(f"Nested fetch failed for {value}: {e}") from e
                else:
                    record[field["name"]] = value
            records.append(record)
        return records

    def _extract_list_field(self, parent, field: HTTPFieldSchema, *args, **kwargs):
        values: List[Any] = []
        selector = field.get("selector")
        attr = field.get("attribute")
        default = field.get("default")
        type_ = field.get("type", "text")
        preformatter = field.get("preformatter")
        postformatter = field.get("postformatter")
        list_subfields = field.get("list_subfields")
        list_formatter = field.get("list_formatter")

        for el in parent.css(selector):
            if list_subfields:
                obj: Dict[str, Any] = {}
                for sub in list_subfields:
                    subel = el.css_first(sub["selector"])
                    subattr = sub.get("attribute")
                    subdefault = sub.get("default")
                    subtype = sub.get("type", "text")
                    sub_pre = sub.get("preformatter")
                    sub_post = sub.get("postformatter")
                    subval = subdefault

                    if subel:
                        subval = subel.text() if not subattr else subel.attributes.get(subattr, subdefault)
                        subval = self._apply_formatters(subval, sub_pre, sub_post, subtype, subdefault)

                    if "url_follow_schema" in sub and isinstance(subval, str) and subval:
                        nested = self.fetch(subval, sub["url_follow_schema"], *args, **kwargs)
                        if isinstance(nested, list) and len(nested) == 1:
                            obj[sub["name"]] = nested[0]
                        elif isinstance(nested, list):
                            nested_obj = {}
                            for n in nested:
                                nested_obj.update(n)
                            obj[sub["name"]] = nested_obj
                        else:
                            obj[sub["name"]] = nested
                    else:
                        obj[sub["name"]] = subval
                values.append(obj)
            else:
                val = el.text() if not attr else el.attributes.get(attr, default)
                if val != default:
                    val = self._apply_formatters(val, preformatter, postformatter, type_, default)
                values.append(val)

        if list_formatter and callable(list_formatter):
            values = list_formatter(values)
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
        except Exception as e:
            raise FormatterError(f"Failed to cast '{value}' to {type_}: {e}") from e
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
    def __init__(self, session: Optional[aiohttp.ClientSession] = None, max_concurrency: int = 10, timeout: int = 20):
        self.external_session = session
        self.session: Optional[aiohttp.ClientSession] = session
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._close_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            self._close_session = True
        return self.session

    async def close(self):
        if self.session and not self.session.closed and self._close_session:
            await self.session.close()

    async def fetch(self, url: str, schema: HTTPCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        pagination = schema.get("url_pagination")
        urls: List[str] = []

        if pagination is None:
            urls = [url]
        else:
            start = pagination.get("start_page", 1)
            end = pagination["end_page"]
            placeholder = pagination.get("page_placeholder", "{page}")
            urls = [url.replace(placeholder, str(i)) for i in range(start, end + 1)]

        tasks = [self._fetch_page(u, schema, *args, **kwargs) for u in urls]
        results = await asyncio.gather(*tasks)
        return [r for sublist in results for r in sublist]

    async def _fetch_page(self, url: str, schema: HTTPCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        on_pageload = schema.get("on_pageload")
        async with self.semaphore:
            session = await self._get_session()
            async with session.get(url, *args, **kwargs) as resp:
                resp.raise_for_status()
                if on_pageload and callable(on_pageload):
                    on_pageload(resp)
                html = await resp.text()

            tree = HTMLParser(html)
            return await self._extract_from_tree(tree, schema, *args, **kwargs)

    async def _extract_from_tree(self, tree: HTMLParser, schema: HTTPCrawlerSchema, *args, **kwargs):
        base_elements = tree.css(schema.get("base_selector", "body"))
        fields: List[HTTPFieldSchema] = schema.get("fields", [])
        records: List[Dict[str, Any]] = []

        for parent in base_elements:
            record: Dict[str, Any] = {}
            for field in fields:
                selector = field.get("selector")
                attr = field.get("attribute")
                default = field.get("default")
                type_ = field.get("type", "text")
                preformatter = field.get("preformatter")
                postformatter = field.get("postformatter")
                url_follow_schema = field.get("url_follow_schema")

                if type_ == "list":
                    record[field["name"]] = await self._extract_list_field(parent, field, *args, **kwargs)
                    continue

                el = parent.css_first(selector) if selector else None
                value = default
                if el:
                    value = el.text() if not attr else el.attributes.get(attr, default)
                    value = self._apply_formatters(value, preformatter, postformatter, type_, default)

                if url_follow_schema and isinstance(value, str) and value:
                    nested = await self.fetch(value, url_follow_schema, *args, **kwargs)
                    if isinstance(nested, list) and len(nested) == 1:
                        record[field["name"]] = nested[0]
                    elif isinstance(nested, list):
                        nested_obj = {}
                        for n in nested:
                            nested_obj.update(n)
                        record[field["name"]] = nested_obj
                    else:
                        record[field["name"]] = nested
                else:
                    record[field["name"]] = value
            records.append(record)
        return records

    async def _extract_list_field(self, parent, field: HTTPFieldSchema, *args, **kwargs):
        values: List[Any] = []
        selector = field.get("selector")
        attr = field.get("attribute")
        default = field.get("default")
        type_ = field.get("type", "text")
        preformatter = field.get("preformatter")
        postformatter = field.get("postformatter")
        list_subfields = field.get("list_subfields")
        list_formatter = field.get("list_formatter")

        for el in parent.css(selector):
            if list_subfields:
                obj: Dict[str, Any] = {}
                for sub in list_subfields:
                    subel = el.css_first(sub["selector"])
                    subattr = sub.get("attribute")
                    subdefault = sub.get("default")
                    subtype = sub.get("type", "text")
                    sub_pre = sub.get("preformatter")
                    sub_post = sub.get("postformatter")
                    subval = subdefault
                    if subel:
                        subval = subel.text() if not subattr else subel.attributes.get(subattr, subdefault)
                        subval = self._apply_formatters(subval, sub_pre, sub_post, subtype, subdefault)

                    if "url_follow_schema" in sub and isinstance(subval, str) and subval:
                        nested = await self.fetch(subval, sub["url_follow_schema"], *args, **kwargs)
                        if isinstance(nested, list) and len(nested) == 1:
                            obj[sub["name"]] = nested[0]
                        elif isinstance(nested, list):
                            nested_obj = {}
                            for n in nested:
                                nested_obj.update(n)
                            obj[sub["name"]] = nested_obj
                        else:
                            obj[sub["name"]] = nested
                    else:
                        obj[sub["name"]] = subval
                values.append(obj)
            else:
                val = el.text() if not attr else el.attributes.get(attr, default)
                if val != default:
                    val = self._apply_formatters(val, preformatter, postformatter, type_, default)
                values.append(val)

        if list_formatter and callable(list_formatter):
            values = list_formatter(values)
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
        except Exception as e:
            raise FormatterError(f"Failed to cast '{value}' to {type_}: {e}") from e
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
