from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PageContext:
    region: Any
    keyword: Any
    parent: Optional[Any] = None
