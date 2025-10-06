from typing import List, Dict, Any
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
    - supports attributes, default values, and formatter callables
    - supports nested schemas via `follow_schema`
    """

    def __init__(self, session: requests.Session | None = None) -> None:
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

        urls: list[str] = []
        if pagination is None:
            urls = [url]
        elif pagination.get("page_placeholder"): # only exists in URLPaginationSchema
            pagination = schema["pagination"]
            
            for page_n in range(pagination["start_page"], pagination["end_page"]+1):
                urls.append(url.replace(pagination["page_placeholder"], str(page_n)))
        else:
            raise InvalidSchema(f"Invalid pagination schema for SyncHTTPCrawler, allowed types are: {None} and {URLPaginationSchema}")
        

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
                    formatter = field.get("formatter")
                    follow_schema = field.get("follow_schema")

                    # TYPE: list
                    if type_ == "list":
                        values: List[Any] = []
                        for el in parent.css(selector):
                            if el is None:
                                continue
                            raw = el.text(strip=True) if not attr else el.attributes.get(attr, default)
                            if not raw:
                                raw = default
                            elif formatter:
                                raw = formatter(raw)
                            values.append(raw)
                        record[field["name"]] = values
                        continue

                    # Singular value
                    el = parent.css_first(selector)
                    if not el:
                        record[field["name"]] = default
                        continue

                    raw = el.text(strip=True) if not attr else el.attributes.get(attr, default)
                    if raw is None:
                        record[field["name"]] = default
                        continue

                    # Type coercion
                    value: Any = raw
                    if type_ == "number":
                        try:
                            value = float(raw)
                            if value.is_integer():
                                value = int(value)
                        except ValueError:
                            value = default
                    elif type_ == "text":
                        value = str(raw)
                    elif type_ == "json":
                        value = json.loads(raw)

                    # Apply formatter
                    if formatter:
                        value = formatter(value)


                    # Nested schema
                    if follow_schema and isinstance(value, str):
                        nested = self.fetch(value, follow_schema, *args, **kwargs)
                        if isinstance(nested, list):
                            for item in nested:
                                for key, val in item.items():
                                    record[key] = val
                        else:
                            for key, val in item.items():
                                record[key] = val
                        
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
