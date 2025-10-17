from __future__ import annotations
from typing import TypedDict, List, Callable, Any, Literal, Generic, TypeVar, Tuple
from requests import Response
from playwright.sync_api import Page as SyncPage
from playwright.async_api import Page as AsyncPage

T = TypeVar("T")


# Field schema definition
class BaseFieldSchema(Generic[T], TypedDict, total=True):
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
    
class HTTPFieldSchema(BaseFieldSchema):
    url_follow_schema: HTTPCrawlerSchema
    list_subfields: List[HTTPFieldSchema]
    
class SyncBrowserFieldSchema(BaseFieldSchema):
    url_follow_schema: SyncBrowserCrawlerSchema
    list_subfields: List[SyncBrowserCrawlerSchema]
  
class AsyncBrowserFieldSchema(BaseFieldSchema):
    url_follow_schema: AsyncBrowserCrawlerSchema
    list_subfields: List[AsyncBrowserCrawlerSchema]


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
    scroll_horizontal: bool

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
    scroll_selector: str
    cycle_delay: float
    scroll_horizontal: bool
    
    # Scroll stop conditions (optional)
    scroll_count: int
    stop_selector: str
    
    # Retry options for scroll
    retry_delay: float
    retry_limit: int
    retry_scroll_distance: int
    
    # Button-specific
    click_count: int


# Crawler Schemas
class BaseCrawlerSchema(TypedDict, total=False):
    """Common fields shared by all crawlers."""
    base_selector: str


class HTTPCrawlerSchema(BaseCrawlerSchema, total=True):
    """
    Schema for HTTP-based crawlers (requests, aiohttp, etc.)
    """
    fields: List[HTTPFieldSchema]
    url_pagination: URLPaginationSchema
    on_pageload: Callable[[Response], None]


class WaitForSelectorArgs(TypedDict, total=False):
    selector: str
    timeout: float
    state: Literal["attached", "detached", "hidden", "visible"]
    strict: bool

class BrowserCrawlerSchema(BaseCrawlerSchema, total=True):
    """
    Schema for browser-based crawlers (Playwright, Selenium, etc.)
    Supports both scroll and URL pagination.
    """
    wait_for_selector: WaitForSelectorArgs
    
    scroll_pagination: ScrollPaginationSchema
    button_pagination: ButtonPaginationSchema
    url_pagination: URLPaginationSchema
    

class SyncBrowserCrawlerSchema(BrowserCrawlerSchema, total=True):
    """
    Schema for browser-based crawlers (Playwright)
    Supports both scroll and URL pagination.
    """
    fields: List[SyncBrowserFieldSchema]
    on_pageload: Callable[[SyncPage], None]
    on_scroll: Callable[[SyncPage], None]
    
    
class AsyncBrowserCrawlerSchema(BrowserCrawlerSchema, total=True):
    """
    Schema for browser-based crawlers (Playwright)
    Supports both scroll and URL pagination.
    """
    fields: List[AsyncBrowserFieldSchema]
    on_pageload: Callable[[AsyncPage], None]
    on_scroll: Callable[[AsyncPage], None]
