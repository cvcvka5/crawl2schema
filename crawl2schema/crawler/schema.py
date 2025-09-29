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

    # (Optional) Which HTML attribute to extract instead of inner text
    # Example: {"attribute": "href"} for links
    attribute: Optional[str]

    # (Optional) Fallback value if nothing is found
    default: Optional[Any]

    # (Optional) A function to further process the extracted value
    # Example: lambda x: x.strip().lower()
    formatter: Callable[[T], Any]

    # (Optional) Nested schema for following links and extracting more data
    # Example: Use this to crawl product detail pages
    follow_schema: Optional[CrawlerSchema]


class CrawlerSchema(TypedDict, total=False):
    """
    Defines how to crawl a web page.
    Specifies a base container (CSS selector) and multiple fields to extract.
    """

    # The root CSS selector that contains all target elements (default: body)
    base_selector: str

    # List of fields to extract from the page
    fields: List[FieldSchema]
    