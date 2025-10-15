from __future__ import annotations
from typing import TypedDict, List, Callable, Any, Literal, Generic, TypeVar, Union

T = TypeVar("T")


# Field schema definition
class FieldSchema(Generic[T], TypedDict, total=True):
    """
    Defines how to extract a single piece of data from the HTML.
    """
    name: str
    selector: str
    type: Literal["text", "list", "number", "json", "undefined"]
    attribute: str
    default: Any
    
    preformatter: Callable[[Any], Any]
    postformatter: Callable[[Any], Any]
    list_formatter: Callable[[List[Any]], Any]
    
    url_follow_schema: BaseCrawlerSchema
    list_subfields: List[FieldSchema]


# Pagination Schemas

# ---- URL Pagination ----
class URLPaginationSchema(TypedDict, total=False):
    page_placeholder: str
    start_page: int
    end_page: int


# ---- Scroll Pagination ----
class ScrollPaginationSchema(TypedDict, total=False):
    stop_condition: Literal["count", "element", "no-new-elements"]
    scroll_distance: int
    scroll_delay: float
    scroll_selector: str

    # specific for count stop condition
    scroll_count: int

    # specific for element stop condition
    stop_selector: str

    # specific for no-new-elements stop condition
    retry_limit: int
    retry_scroll_distance: int



# ---- Button Pagination ----
class ButtonPaginationSchema(TypedDict, total=False):
    stop_condition: Literal["count", "element", "no-button"]
    button_selector: str
    
    # Scroll-like options (optional)
    scroll_distance: int
    scroll_delay: float
    scroll_selector: str
    
    # Scroll stop conditions (optional)
    scroll_count: int
    stop_selector: str
    
    # Retry options for scroll
    retry_limit: int
    retry_scroll_distance: int
    
    # Button-specific
    click_count: int


# Crawler Schemas
class BaseCrawlerSchema(TypedDict, total=False):
    """Common fields shared by all crawlers."""
    base_selector: str
    fields: List[FieldSchema]


class HTTPCrawlerSchema(BaseCrawlerSchema, total=True):
    """
    Schema for HTTP-based crawlers (requests, aiohttp, etc.)
    """
    url_pagination: URLPaginationSchema


class BrowserCrawlerSchema(BaseCrawlerSchema, total=True):
    """
    Schema for browser-based crawlers (Playwright, Selenium, etc.)
    Supports both scroll and URL pagination.
    """
    scroll_pagination: Union[
        ScrollPaginationSchemaCount,
        ScrollPaginationSchemaElement,
        ScrollPaginationSchemaNoNewElements
    ]
    url_pagination: URLPaginationSchema