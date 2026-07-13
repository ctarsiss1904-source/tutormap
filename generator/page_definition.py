from dataclasses import dataclass, field
from typing import Dict, List, Optional

from generator.page_type import PageType


@dataclass
class PageDefinition:
    page_type: PageType
    title_pattern: str
    parent_type: Optional[PageType]
    child_types: List[PageType] = field(default_factory=list)
    is_hub: bool = True
    template: str = ""
    schema_type: str = ""


class PageRegistry:
    def __init__(self):
        self._definitions: Dict[PageType, PageDefinition] = {}

    def register(self, definition):
        self._definitions[definition.page_type] = definition

    def get(self, page_type):
        return self._definitions.get(page_type)

    def all(self):
        return list(self._definitions.values())


def create_default_registry():
    registry = PageRegistry()

    registry.register(
        PageDefinition(
            page_type=PageType.NATION,
            title_pattern="전국과외",
            parent_type=None,
            child_types=[PageType.PROVINCE],
            is_hub=True,
            template="region",
            schema_type="CollectionPage",
        )
    )
    registry.register(
        PageDefinition(
            page_type=PageType.PROVINCE,
            title_pattern="{region}과외",
            parent_type=PageType.NATION,
            child_types=[PageType.CITY],
            is_hub=True,
            template="region",
            schema_type="CollectionPage",
        )
    )
    registry.register(
        PageDefinition(
            page_type=PageType.CITY,
            title_pattern="{region}과외",
            parent_type=PageType.PROVINCE,
            child_types=[PageType.DISTRICT, PageType.DONG],
            is_hub=True,
            template="region",
            schema_type="CollectionPage",
        )
    )
    registry.register(
        PageDefinition(
            page_type=PageType.DISTRICT,
            title_pattern="{region}과외",
            parent_type=PageType.CITY,
            child_types=[PageType.DONG],
            is_hub=True,
            template="region",
            schema_type="CollectionPage",
        )
    )
    registry.register(
        PageDefinition(
            page_type=PageType.DONG,
            title_pattern="{region}과외",
            parent_type=PageType.DISTRICT,
            child_types=[PageType.SUBJECT],
            is_hub=True,
            template="region",
            schema_type="CollectionPage",
        )
    )
    registry.register(
        PageDefinition(
            page_type=PageType.SUBJECT,
            title_pattern="{region}{subject}과외",
            parent_type=PageType.DONG,
            child_types=[PageType.GRADE],
            is_hub=True,
            template="subject",
            schema_type="CollectionPage",
        )
    )
    registry.register(
        PageDefinition(
            page_type=PageType.GRADE,
            title_pattern="{region}{grade}{subject}과외",
            parent_type=PageType.SUBJECT,
            child_types=[PageType.SCHOOL],
            is_hub=True,
            template="grade",
            schema_type="CollectionPage",
        )
    )
    registry.register(
        PageDefinition(
            page_type=PageType.SCHOOL,
            title_pattern="{school}{subject}과외",
            parent_type=PageType.GRADE,
            child_types=[],
            is_hub=True,
            template="school",
            schema_type="CollectionPage",
        )
    )

    return registry
