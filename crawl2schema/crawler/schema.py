from __future__ import annotations
from typing import TypedDict, List, Callable, Optional, Any, Generic, TypeVar, Literal

T = TypeVar("T")

class FieldSchema(Generic[T], TypedDict, total=False):
    """
    Defines how to extract a single piece of data from the HTML.
    Each field is tied to a CSS selector, data type, and optional transformation logic.
    """

    # The key name for this field in the returned dictionary
    name: Optional[str]

    # CSS selector used to find matching elements
    selector: str

    # Python type used to cast the extracted value (e.g., str, int, float)
    type: Optional[Literal["text", "list", "number", "json"]]

    list_subfields: Optional[List[FieldSchema]]

    # (Optional) Which HTML attribute to extract instead of inner text
    # Example: {"attribute": "href"} for links
    attribute: Optional[str]

    # (Optional) Fallback value if nothing is found
    default: Optional[Any]

    # (Optional) A function to further process the extracted value (before type casting)
    # Example: lambda x: x.strip().lower()
    preformatter: Optional[Callable[[T], Any]]
    
    # (Optional) A function to further process the extracted value (before type casting)
    # Example: lambda x: x.strip().lower()
    postformatter: Optional[Callable[[T], Any]]

    # (Optional) Nested schema for following links and extracting more data
    # Example: Use this to crawl product detail pages
    url_follow_schema: Optional[CrawlerSchema]


class URLPaginationSchema(TypedDict):
    end_page: int # inclusive
    
    interval: Optional[float] = 0
    page_placeholder: Optional[str] = "{page}"
    start_page: Optional[int] = 1


class CrawlerSchema(TypedDict, total=False):
    """
    Defines how to crawl a web page.
    Specifies a base container (CSS selector) and multiple fields to extract.
    """

    # The root CSS selector that contains all target elements (default: body)
    base_selector: str

    # List of fields to extract from the page
    fields: List[FieldSchema]
    
    # This is kept only so its more schema driven for SyncHTTPCrawler
    # Instead its recommended to generate your own urls with a for loop.
    pagination: Optional[URLPaginationSchema] = None 
    