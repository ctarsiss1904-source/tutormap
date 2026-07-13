from dataclasses import dataclass, field
from typing import Any, List, Optional

from generator.page_type import PageType


@dataclass
class Page:
    id: str
    title: str
    url_segment: str
    region: Any
    keyword: Any
    page_type: PageType
    parent: Optional["Page"] = None
    children: List["Page"] = field(default_factory=list)
    url: Optional[str] = None
    template: Optional[str] = None
    meta: Any = None
    schema: Any = None
    breadcrumb: List[Any] = field(default_factory=list)
    internal_links: List[Any] = field(default_factory=list)
    content: str = ""
    hero_image: Any = None
    seo_image: Any = None
    is_hub: bool = True
