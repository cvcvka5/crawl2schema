from typing import List, Dict, Any, Callable, Optional
import requests
from ..schema import CrawlerSchema, FieldSchema, URLPaginationSchema
from ...exceptions import InvalidSchema
from selectolax.parser import HTMLParser
import json


class SyncHTTPCrawler:
    """
    A synchronous HTML crawler that extracts structured data from web pages
    based on a provided CrawlerSchema.

    Features:
    - base_selector selects multiple parent elements (one record per parent)
    - fields can extract text, numbers, or lists inside each parent element
    - supports attributes, default values, preformatter and postformatter callables
    - supports nested schemas via `follow_schema`
    - supports structured lists via `list_subfields` (list of objects)
    """

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def fetch(self, url: str, schema: CrawlerSchema, *args, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetches a page and extracts data according to the given schema.

        Args:
            url: URL to fetch.
            schema: CrawlerSchema dict with base_selector and fields.
            *args, **kwargs: Extra arguments passed to requests.get().

        Returns:
            List of dictionaries, one per parent element matched by base_selector.
        """

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

            base_elements = tree.css(schema.get("base_selector", "body"))
            fields: List[FieldSchema] = schema.get("fields", [])

            for parent in base_elements:
                record: Dict[str, Any] = {}

                for field in fields:
                    selector = field["selector"]
                    attr = field.get("attribute")
                    default = field.get("default")
                    type_ = field.get("type", "text")
                    preformatter: Optional[Callable] = field.get("preformatter")
                    postformatter: Optional[Callable] = field.get("postformatter")
                    follow_schema = field.get("follow_schema")

                    # --- TYPE: list ---
                    if type_ == "list":
                        values: List[Any] = []
                        list_subfields = field.get("list_subfields")

                        list_base_elements = parent.css(selector)

                        for el in list_base_elements:
                            if list_subfields:
                                # structured list of objects
                                obj: Dict[str, Any] = {}
                                for subfield in list_subfields:
                                    subsel = subfield["selector"]
                                    subattr = subfield.get("attribute")
                                    subdefault = subfield.get("default")
                                    subtype = subfield.get("type", "text")
                                    sub_pre = subfield.get("preformatter")
                                    sub_post = subfield.get("postformatter")

                                    subel = el.css_first(subsel)
                                    subraw = subdefault
                                    if subel:
                                        subraw = subel.text(strip=True) if not subattr else subel.attributes.get(subattr, subdefault)

                                    # Apply subfield preformatter
                                    if sub_pre:
                                        subraw = sub_pre(subraw)

                                    # Type coercion
                                    if subtype == "number":
                                        try:
                                            subraw = float(subraw)
                                            if subraw.is_integer():
                                                subraw = int(subraw)
                                        except (ValueError, TypeError):
                                            subraw = subdefault
                                    elif subtype == "json":
                                        try:
                                            subraw = json.loads(subraw)
                                        except (json.JSONDecodeError, TypeError):
                                            subraw = subdefault
                                    elif subtype == "text":
                                        subraw = str(subraw) if subraw is not None else subdefault

                                    # Apply subfield postformatter
                                    if sub_post:
                                        subraw = sub_post(subraw)

                                    obj[subfield["name"]] = subraw
                                values.append(obj)
                            else:
                                # simple list
                                raw = el.text(strip=True) if not attr else el.attributes.get(attr, default)

                                if preformatter:
                                    raw = preformatter(raw)

                                # Type coercion for simple list
                                if type_ == "number":
                                    try:
                                        raw = float(raw)
                                        if raw.is_integer():
                                            raw = int(raw)
                                    except (ValueError, TypeError):
                                        raw = default
                                elif type_ == "json":
                                    try:
                                        raw = json.loads(raw)
                                    except (json.JSONDecodeError, TypeError):
                                        raw = default
                                elif type_ == "text":
                                    raw = str(raw) if raw is not None else default

                                if postformatter:
                                    raw = postformatter(raw)

                                values.append(raw)

                        record[field["name"]] = values
                        continue

                    # --- TYPE: singular ---
                    el = parent.css_first(selector)
                    raw = default
                    if el:
                        raw = el.text(strip=True) if not attr else el.attributes.get(attr, default)

                    value: Any = raw

                    # Apply preformatter
                    if preformatter:
                        value = preformatter(value)

                    # Type coercion
                    if type_ == "number":
                        try:
                            value = float(value)
                            if value.is_integer():
                                value = int(value)
                        except (ValueError, TypeError):
                            value = default
                    elif type_ == "json":
                        try:
                            value = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            value = default
                    elif type_ == "text":
                        value = str(value) if value is not None else default

                    # Apply postformatter
                    if postformatter:
                        value = postformatter(value)

                    # Follow nested schema
                    if follow_schema and isinstance(value, str):
                        nested = self.fetch(value, follow_schema, *args, **kwargs)
                        if isinstance(nested, list):
                            for item in nested:
                                for k, v in item.items():
                                    record[k] = v
                        else:
                            for k, v in nested.items():
                                record[k] = v
                    else:
                        record[field["name"]] = value

                records.append(record)

        return records


class AsyncHTTPCrawler:
    """
    Placeholder for asynchronous implementation.
    Will likely use aiohttp + asyncio + selectolax.
    """

    def __init__(self) -> None:
        pass


__all__ = ["SyncHTTPCrawler", "AsyncHTTPCrawler"]
