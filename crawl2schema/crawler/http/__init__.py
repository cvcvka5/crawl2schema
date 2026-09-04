from typing import List, Dict, Any, Callable, Optional, Tuple
import asyncio
import aiohttp
import json
import time
import copy
import re
from urllib.parse import urljoin
from selectolax.parser import HTMLParser
from ..schema import HTTPCrawlerSchema, HTTPFieldSchema, URLPaginationSchema, RequestRetrySchema
from ...exceptions import InvalidSchema, CrawlerError, FormatterError, PaginationError, ParseError, RequestError
import requests


class SyncHTTPCrawler:
    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self._close_session = session is None
        self._nested_cache: Dict[Tuple[str, int], Any] = {}

    def fetch(self, url: str, schema: HTTPCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        self._validate_schema(schema)
        pagination = schema.get("url_pagination", None)
        on_pageload = schema.get("on_pageload")
        urls = self._build_paginated_urls(url, pagination)
        retry_config = self._get_retry_config(schema)
        cache_nested_requests = schema.get("cache_nested_requests", True)

        records: List[Dict[str, Any]] = []
        for page_url in urls:
            response = self._request_with_retries(page_url, retry_config, *args, **kwargs)

            if on_pageload and callable(on_pageload):
                on_pageload(response)

            try:
                tree = HTMLParser(response.text)
            except Exception as e:
                raise ParseError(f"Failed to parse HTML from {page_url}: {e}") from e

            records.extend(
                self._extract_from_tree(
                    tree,
                    schema,
                    source_url=page_url,
                    retry_config=retry_config,
                    cache_nested_requests=cache_nested_requests,
                    *args,
                    **kwargs,
                )
            )
        return self._finalize_records(records, schema)

    def _request_with_retries(self, url: str, retry_config: RequestRetrySchema, *args, **kwargs):
        attempts = retry_config["attempts"]
        retry_on_status = set(retry_config["retry_on_status"])
        retry_on_exceptions = retry_config["retry_on_exceptions"]
        delay = retry_config["delay"]
        backoff = retry_config["backoff"]
        max_delay = retry_config["max_delay"]

        current_delay = delay
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                response = self.session.get(url, *args, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                last_error = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                status_retryable = status in retry_on_status
                should_retry = status_retryable or retry_on_exceptions

                if not should_retry or attempt >= attempts:
                    raise RequestError(f"Failed to fetch {url}: {e}") from e

                if current_delay > 0:
                    time.sleep(current_delay)
                    current_delay = min(current_delay * backoff, max_delay)

        raise RequestError(f"Failed to fetch {url}: {last_error}")

    def _extract_from_tree(
        self,
        tree: HTMLParser,
        schema: HTTPCrawlerSchema,
        source_url: str,
        retry_config: RequestRetrySchema,
        cache_nested_requests: bool,
        *args,
        **kwargs,
    ) -> List[Dict[str, Any]]:
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
                    record[field["name"]] = self._extract_list_field(
                        parent,
                        field,
                        source_url=source_url,
                        retry_config=retry_config,
                        cache_nested_requests=cache_nested_requests,
                        *args,
                        **kwargs,
                    )
                    continue

                value = self._extract_scalar_value(
                    parent=parent,
                    selector=selector,
                    attr=attr,
                    default=default,
                    type_=type_,
                    preformatter=preformatter,
                    postformatter=postformatter,
                    required=bool(field.get("required", False)),
                    extract_regex=field.get("extract_regex"),
                    extract_regex_group=int(field.get("extract_regex_group", 0)),
                    field_name=field.get("name"),
                )

                if url_follow_schema and isinstance(value, str) and value:
                    try:
                        nested_url = self._resolve_url(source_url, value)
                        nested = self._fetch_nested(
                            nested_url,
                            url_follow_schema,
                            retry_config,
                            cache_nested_requests,
                            *args,
                            **kwargs,
                        )
                        record[field["name"]] = self._merge_nested_records(nested)
                    except Exception as e:
                        raise CrawlerError(f"Nested fetch failed for {value}: {e}") from e
                else:
                    record[field["name"]] = value
            records.append(record)
        return records

    def _extract_list_field(
        self,
        parent,
        field: HTTPFieldSchema,
        source_url: str,
        retry_config: RequestRetrySchema,
        cache_nested_requests: bool,
        *args,
        **kwargs,
    ):
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
                    if bool(sub.get("required", False)) and subel is None:
                        raise ParseError(f"Required subfield '{sub.get('name')}' not found")

                    subval = subdefault
                    if subel:
                        subval = self._extract_text_or_attribute(subel, subattr, subdefault)
                        subval = self._apply_regex_extract(
                            subval,
                            sub.get("extract_regex"),
                            int(sub.get("extract_regex_group", 0)),
                            sub.get("name"),
                        )
                        subval = self._apply_formatters(subval, sub_pre, sub_post, subtype, subdefault)

                    if "url_follow_schema" in sub and isinstance(subval, str) and subval:
                        nested_url = self._resolve_url(source_url, subval)
                        nested = self._fetch_nested(
                            nested_url,
                            sub["url_follow_schema"],
                            retry_config,
                            cache_nested_requests,
                            *args,
                            **kwargs,
                        )
                        obj[sub["name"]] = self._merge_nested_records(nested)
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

    def _extract_scalar_value(
        self,
        parent,
        selector: Optional[str],
        attr: Optional[str],
        default: Any,
        type_: str,
        preformatter: Optional[Callable],
        postformatter: Optional[Callable],
        required: bool,
        extract_regex,
        extract_regex_group: int,
        field_name: Optional[str],
    ):
        el = parent.css_first(selector) if selector else None
        if required and el is None:
            raise ParseError(f"Required field '{field_name}' not found")
        if el is None:
            return default

        value = self._extract_text_or_attribute(el, attr, default)
        value = self._apply_regex_extract(value, extract_regex, extract_regex_group, field_name)
        return self._apply_formatters(value, preformatter, postformatter, type_, default)

    @staticmethod
    def _extract_text_or_attribute(el, attr: Optional[str], default: Any):
        return el.text() if not attr else el.attributes.get(attr, default)

    @staticmethod
    def _apply_regex_extract(value, pattern, group: int, field_name: Optional[str]):
        if pattern is None or value is None:
            return value
        match = re.search(pattern, str(value))
        if match is None:
            raise ParseError(f"Regex extract failed for field '{field_name}'")
        return match.group(group)

    def _fetch_nested(
        self,
        nested_url: str,
        nested_schema: HTTPCrawlerSchema,
        retry_config: RequestRetrySchema,
        cache_nested_requests: bool,
        *args,
        **kwargs,
    ):
        cache_key = (nested_url, id(nested_schema))
        if cache_nested_requests and cache_key in self._nested_cache:
            return copy.deepcopy(self._nested_cache[cache_key])

        nested = self.fetch(nested_url, nested_schema, *args, **kwargs)
        if cache_nested_requests:
            self._nested_cache[cache_key] = copy.deepcopy(nested)
        return nested

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

    def _build_paginated_urls(
        self, url: str, pagination: Optional[URLPaginationSchema]
    ) -> List[str]:
        if pagination is None:
            return [url]

        try:
            start = pagination.get("start_page", 1)
            end = pagination["end_page"]
            placeholder = pagination.get("page_placeholder", "{page}")
            if not isinstance(start, int) or not isinstance(end, int):
                raise PaginationError("start_page and end_page must be integers")
            if start > end:
                raise PaginationError("start_page cannot be greater than end_page")
            if placeholder not in url:
                raise PaginationError(f"page placeholder '{placeholder}' not found in url")
            return [url.replace(placeholder, str(i)) for i in range(start, end + 1)]
        except KeyError as e:
            raise PaginationError(f"Invalid pagination schema: missing {e}") from e
        except PaginationError:
            raise
        except Exception as e:
            raise PaginationError(f"Invalid pagination schema: {e}") from e

    def _validate_schema(self, schema: HTTPCrawlerSchema) -> None:
        if not isinstance(schema, dict):
            raise InvalidSchema("schema must be a dictionary")
        fields = schema.get("fields")
        if not isinstance(fields, list) or len(fields) == 0:
            raise InvalidSchema("schema.fields must be a non-empty list")
        for field in fields:
            if not isinstance(field, dict):
                raise InvalidSchema("each field must be a dictionary")
            if not field.get("name"):
                raise InvalidSchema("each field must define a non-empty name")
            if field.get("type") == "list" and not field.get("selector"):
                raise InvalidSchema("list fields must define selector")
            if field.get("extract_regex_group") is not None and not isinstance(field.get("extract_regex_group"), int):
                raise InvalidSchema("extract_regex_group must be an integer")

    @staticmethod
    def _merge_nested_records(nested):
        if isinstance(nested, list) and len(nested) == 1:
            return nested[0]
        if isinstance(nested, list):
            nested_obj = {}
            for item in nested:
                if isinstance(item, dict):
                    nested_obj.update(item)
            return nested_obj
        return nested

    @staticmethod
    def _resolve_url(source_url: str, candidate_url: str) -> str:
        return urljoin(source_url, candidate_url)

    @staticmethod
    def _get_retry_config(schema: HTTPCrawlerSchema) -> RequestRetrySchema:
        retry = schema.get("request_retry", {})
        attempts = max(1, int(retry.get("attempts", 1)))
        delay = max(0.0, float(retry.get("delay", 0.0)))
        backoff = max(1.0, float(retry.get("backoff", 2.0)))
        max_delay = max(0.0, float(retry.get("max_delay", 30.0)))
        retry_on_status = list(retry.get("retry_on_status", [429, 500, 502, 503, 504]))
        retry_on_exceptions = bool(retry.get("retry_on_exceptions", True))
        return {
            "attempts": attempts,
            "delay": delay,
            "backoff": backoff,
            "max_delay": max_delay,
            "retry_on_status": retry_on_status,
            "retry_on_exceptions": retry_on_exceptions,
        }

    @staticmethod
    def _finalize_records(records: List[Dict[str, Any]], schema: HTTPCrawlerSchema) -> List[Dict[str, Any]]:
        transformed: List[Dict[str, Any]] = []
        record_transform = schema.get("record_transform")
        record_filter = schema.get("record_filter")
        deduplicate_by = schema.get("deduplicate_by", [])
        include_metadata = bool(schema.get("include_metadata", False))

        for idx, record in enumerate(records):
            candidate = dict(record)
            if include_metadata:
                candidate["_meta"] = {
                    "record_index": idx,
                    "extracted_at": time.time(),
                }
            if record_transform and callable(record_transform):
                candidate = record_transform(candidate)
            if record_filter and callable(record_filter) and not record_filter(candidate):
                continue
            transformed.append(candidate)

        if not deduplicate_by:
            return transformed

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for record in transformed:
            signature = tuple(record.get(key) for key in deduplicate_by)
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(record)
        return deduped

    def __enter__(self):
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
        self._nested_cache: Dict[Tuple[str, int], Any] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            self._close_session = True
        return self.session

    async def close(self):
        if self.session and not self.session.closed and self._close_session:
            await self.session.close()

    async def fetch(self, url: str, schema: HTTPCrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        self._validate_schema(schema)
        pagination = schema.get("url_pagination")
        urls = self._build_paginated_urls(url, pagination)
        retry_config = self._get_retry_config(schema)
        cache_nested_requests = schema.get("cache_nested_requests", True)

        tasks = [
            self._fetch_page(
                page_url,
                schema,
                retry_config=retry_config,
                cache_nested_requests=cache_nested_requests,
                *args,
                **kwargs,
            )
            for page_url in urls
        ]
        results = await asyncio.gather(*tasks)
        flattened = [r for sublist in results for r in sublist]
        return self._finalize_records(flattened, schema)

    async def _request_with_retries(self, url: str, retry_config: RequestRetrySchema, *args, **kwargs):
        attempts = retry_config["attempts"]
        retry_on_status = set(retry_config["retry_on_status"])
        retry_on_exceptions = retry_config["retry_on_exceptions"]
        delay = retry_config["delay"]
        backoff = retry_config["backoff"]
        max_delay = retry_config["max_delay"]

        current_delay = delay
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                session = await self._get_session()
                async with session.get(url, *args, **kwargs) as resp:
                    resp.raise_for_status()
                    html = await resp.text()
                    return resp, html
            except Exception as e:
                last_error = e
                status = getattr(e, "status", None)
                status_retryable = status in retry_on_status if status is not None else False
                should_retry = status_retryable or retry_on_exceptions

                if not should_retry or attempt >= attempts:
                    raise RequestError(f"Failed to fetch {url}: {e}") from e

                if current_delay > 0:
                    await asyncio.sleep(current_delay)
                    current_delay = min(current_delay * backoff, max_delay)

        raise RequestError(f"Failed to fetch {url}: {last_error}")

    async def _fetch_page(
        self,
        url: str,
        schema: HTTPCrawlerSchema,
        retry_config: RequestRetrySchema,
        cache_nested_requests: bool,
        *args,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        on_pageload = schema.get("on_pageload")
        async with self.semaphore:
            resp, html = await self._request_with_retries(url, retry_config, *args, **kwargs)
            if on_pageload and callable(on_pageload):
                callback_result = on_pageload(resp)
                if asyncio.iscoroutine(callback_result):
                    await callback_result

            try:
                tree = HTMLParser(html)
            except Exception as e:
                raise ParseError(f"Failed to parse HTML from {url}: {e}") from e
            return await self._extract_from_tree(
                tree,
                schema,
                source_url=url,
                retry_config=retry_config,
                cache_nested_requests=cache_nested_requests,
                *args,
                **kwargs,
            )

    async def _extract_from_tree(
        self,
        tree: HTMLParser,
        schema: HTTPCrawlerSchema,
        source_url: str,
        retry_config: RequestRetrySchema,
        cache_nested_requests: bool,
        *args,
        **kwargs,
    ):
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
                    record[field["name"]] = await self._extract_list_field(
                        parent,
                        field,
                        source_url=source_url,
                        retry_config=retry_config,
                        cache_nested_requests=cache_nested_requests,
                        *args,
                        **kwargs,
                    )
                    continue

                value = self._extract_scalar_value(
                    parent=parent,
                    selector=selector,
                    attr=attr,
                    default=default,
                    type_=type_,
                    preformatter=preformatter,
                    postformatter=postformatter,
                    required=bool(field.get("required", False)),
                    extract_regex=field.get("extract_regex"),
                    extract_regex_group=int(field.get("extract_regex_group", 0)),
                    field_name=field.get("name"),
                )

                if url_follow_schema and isinstance(value, str) and value:
                    nested_url = self._resolve_url(source_url, value)
                    nested = await self._fetch_nested(
                        nested_url,
                        url_follow_schema,
                        retry_config,
                        cache_nested_requests,
                        *args,
                        **kwargs,
                    )
                    record[field["name"]] = self._merge_nested_records(nested)
                else:
                    record[field["name"]] = value
            records.append(record)
        return records

    async def _extract_list_field(
        self,
        parent,
        field: HTTPFieldSchema,
        source_url: str,
        retry_config: RequestRetrySchema,
        cache_nested_requests: bool,
        *args,
        **kwargs,
    ):
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
                    if bool(sub.get("required", False)) and subel is None:
                        raise ParseError(f"Required subfield '{sub.get('name')}' not found")

                    subval = subdefault
                    if subel:
                        subval = self._extract_text_or_attribute(subel, subattr, subdefault)
                        subval = self._apply_regex_extract(
                            subval,
                            sub.get("extract_regex"),
                            int(sub.get("extract_regex_group", 0)),
                            sub.get("name"),
                        )
                        subval = self._apply_formatters(subval, sub_pre, sub_post, subtype, subdefault)

                    if "url_follow_schema" in sub and isinstance(subval, str) and subval:
                        nested_url = self._resolve_url(source_url, subval)
                        nested = await self._fetch_nested(
                            nested_url,
                            sub["url_follow_schema"],
                            retry_config,
                            cache_nested_requests,
                            *args,
                            **kwargs,
                        )
                        obj[sub["name"]] = self._merge_nested_records(nested)
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

    async def _fetch_nested(
        self,
        nested_url: str,
        nested_schema: HTTPCrawlerSchema,
        retry_config: RequestRetrySchema,
        cache_nested_requests: bool,
        *args,
        **kwargs,
    ):
        cache_key = (nested_url, id(nested_schema))
        if cache_nested_requests and cache_key in self._nested_cache:
            return copy.deepcopy(self._nested_cache[cache_key])

        nested = await self.fetch(nested_url, nested_schema, *args, **kwargs)
        if cache_nested_requests:
            self._nested_cache[cache_key] = copy.deepcopy(nested)
        return nested

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

    def _extract_scalar_value(
        self,
        parent,
        selector: Optional[str],
        attr: Optional[str],
        default: Any,
        type_: str,
        preformatter: Optional[Callable],
        postformatter: Optional[Callable],
        required: bool,
        extract_regex,
        extract_regex_group: int,
        field_name: Optional[str],
    ):
        el = parent.css_first(selector) if selector else None
        if required and el is None:
            raise ParseError(f"Required field '{field_name}' not found")
        if el is None:
            return default

        value = self._extract_text_or_attribute(el, attr, default)
        value = self._apply_regex_extract(value, extract_regex, extract_regex_group, field_name)
        return self._apply_formatters(value, preformatter, postformatter, type_, default)

    @staticmethod
    def _extract_text_or_attribute(el, attr: Optional[str], default: Any):
        return el.text() if not attr else el.attributes.get(attr, default)

    @staticmethod
    def _apply_regex_extract(value, pattern, group: int, field_name: Optional[str]):
        if pattern is None or value is None:
            return value
        match = re.search(pattern, str(value))
        if match is None:
            raise ParseError(f"Regex extract failed for field '{field_name}'")
        return match.group(group)

    def _build_paginated_urls(
        self, url: str, pagination: Optional[URLPaginationSchema]
    ) -> List[str]:
        if pagination is None:
            return [url]

        try:
            start = pagination.get("start_page", 1)
            end = pagination["end_page"]
            placeholder = pagination.get("page_placeholder", "{page}")
            if not isinstance(start, int) or not isinstance(end, int):
                raise PaginationError("start_page and end_page must be integers")
            if start > end:
                raise PaginationError("start_page cannot be greater than end_page")
            if placeholder not in url:
                raise PaginationError(f"page placeholder '{placeholder}' not found in url")
            return [url.replace(placeholder, str(i)) for i in range(start, end + 1)]
        except KeyError as e:
            raise PaginationError(f"Invalid pagination schema: missing {e}") from e
        except PaginationError:
            raise
        except Exception as e:
            raise PaginationError(f"Invalid pagination schema: {e}") from e

    def _validate_schema(self, schema: HTTPCrawlerSchema) -> None:
        if not isinstance(schema, dict):
            raise InvalidSchema("schema must be a dictionary")
        fields = schema.get("fields")
        if not isinstance(fields, list) or len(fields) == 0:
            raise InvalidSchema("schema.fields must be a non-empty list")
        for field in fields:
            if not isinstance(field, dict):
                raise InvalidSchema("each field must be a dictionary")
            if not field.get("name"):
                raise InvalidSchema("each field must define a non-empty name")
            if field.get("type") == "list" and not field.get("selector"):
                raise InvalidSchema("list fields must define selector")
            if field.get("extract_regex_group") is not None and not isinstance(field.get("extract_regex_group"), int):
                raise InvalidSchema("extract_regex_group must be an integer")

    @staticmethod
    def _merge_nested_records(nested):
        if isinstance(nested, list) and len(nested) == 1:
            return nested[0]
        if isinstance(nested, list):
            nested_obj = {}
            for item in nested:
                if isinstance(item, dict):
                    nested_obj.update(item)
            return nested_obj
        return nested

    @staticmethod
    def _resolve_url(source_url: str, candidate_url: str) -> str:
        return urljoin(source_url, candidate_url)

    @staticmethod
    def _get_retry_config(schema: HTTPCrawlerSchema) -> RequestRetrySchema:
        retry = schema.get("request_retry", {})
        attempts = max(1, int(retry.get("attempts", 1)))
        delay = max(0.0, float(retry.get("delay", 0.0)))
        backoff = max(1.0, float(retry.get("backoff", 2.0)))
        max_delay = max(0.0, float(retry.get("max_delay", 30.0)))
        retry_on_status = list(retry.get("retry_on_status", [429, 500, 502, 503, 504]))
        retry_on_exceptions = bool(retry.get("retry_on_exceptions", True))
        return {
            "attempts": attempts,
            "delay": delay,
            "backoff": backoff,
            "max_delay": max_delay,
            "retry_on_status": retry_on_status,
            "retry_on_exceptions": retry_on_exceptions,
        }

    @staticmethod
    def _finalize_records(records: List[Dict[str, Any]], schema: HTTPCrawlerSchema) -> List[Dict[str, Any]]:
        transformed: List[Dict[str, Any]] = []
        record_transform = schema.get("record_transform")
        record_filter = schema.get("record_filter")
        deduplicate_by = schema.get("deduplicate_by", [])
        include_metadata = bool(schema.get("include_metadata", False))

        for idx, record in enumerate(records):
            candidate = dict(record)
            if include_metadata:
                candidate["_meta"] = {
                    "record_index": idx,
                    "extracted_at": time.time(),
                }
            if record_transform and callable(record_transform):
                candidate = record_transform(candidate)
            if record_filter and callable(record_filter) and not record_filter(candidate):
                continue
            transformed.append(candidate)

        if not deduplicate_by:
            return transformed

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for record in transformed:
            signature = tuple(record.get(key) for key in deduplicate_by)
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(record)
        return deduped

    async def __aenter__(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._close_session = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._close_session and self.session:
            await self.session.close()
