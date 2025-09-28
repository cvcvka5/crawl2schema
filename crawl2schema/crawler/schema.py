from typing import TypedDict, List, Callable, Optional, Any, Generic, TypeVar

T = TypeVar("T")

class ElementSchema(Generic[T], TypedDict):
    name: str
    selector: str
    type: type[T]
    attribute: Optional[str]
    default: Optional[Any]
    formatter: Optional[Callable[[T], Any]]

class CrawlerSchema(TypedDict):
    baseSelector: str
    targetElements: List[ElementSchema]