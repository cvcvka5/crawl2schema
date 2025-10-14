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
    url_follow_schema: "BaseCrawlerSchema"
    list_subfields: List["FieldSchema"]


# Pagination Schemas
class PaginationSchema(TypedDict, total=False):
    """Base pagination schema."""
    type: Literal["page", "scroll"]


# ---- URL Pagination ----
class URLPaginationSchema(PaginationSchema, total=False):
    type: Literal["page"]
    page_placeholder: str
    start_page: int
    end_page: int


# ---- Scroll Pagination ----
class ScrollPaginationSchema(PaginationSchema, total=False):
    type: Literal["scroll"]
    stop_condition: Literal["count", "element", "no-new-elements"]
    scroll_distance: int
    scroll_delay: float
    scroll_selector: str


class ScrollPaginationSchemaCount(ScrollPaginationSchema, total=True):
    stop_condition: Literal["count"]
    scroll_count: int


class ScrollPaginationSchemaElement(ScrollPaginationSchema, total=True):
    stop_condition: Literal["element"]
    stop_selector: str


class ScrollPaginationSchemaNoNewElements(ScrollPaginationSchema, total=True):
    stop_condition: Literal["no-new-elements"]
    retry_limit: int
    retry_scroll_distance: int


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
