from dataclasses import dataclass, field
from typing import Dict, List, Optional

from generator.page_type import PageType


@dataclass
class KeywordDefinition:
    name: str
    suffix: str
    parent: Optional[str]
    page_type: PageType = PageType.ROOT
    children: List[str] = field(default_factory=list)
    order: int = 0
    is_hub: bool = True
    enabled: bool = True


class KeywordRegistry:
    def __init__(self):
        self._definitions: Dict[str, KeywordDefinition] = {}

    def register(self, definition):
        self._definitions[definition.name] = definition

    def get(self, name):
        return self._definitions.get(name)

    def children(self, name):
        definition = self.get(name)
        if not definition:
            return []

        return [
            self._definitions[child]
            for child in definition.children
            if child in self._definitions
        ]

    def roots(self):
        return [
            definition
            for definition in self._definitions.values()
            if definition.parent is None
        ]

    def all(self):
        return list(self._definitions.values())


def create_default_keyword_registry():
    registry = KeywordRegistry()

    registry.register(
        KeywordDefinition(
            name="과외",
            suffix="과외",
            parent=None,
            page_type=PageType.ROOT,
            children=["영어과외", "수학과외", "국어과외", "과학과외"],
            order=1,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="영어과외",
            suffix="영어과외",
            parent="과외",
            page_type=PageType.SUBJECT,
            children=["초등영어과외", "중등영어과외", "고등영어과외"],
            order=10,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="수학과외",
            suffix="수학과외",
            parent="과외",
            page_type=PageType.SUBJECT,
            children=["초등수학과외", "중등수학과외", "고등수학과외"],
            order=20,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="국어과외",
            suffix="국어과외",
            parent="과외",
            page_type=PageType.SUBJECT,
            children=[],
            order=30,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="과학과외",
            suffix="과학과외",
            parent="과외",
            page_type=PageType.SUBJECT,
            children=[],
            order=40,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="초등영어과외",
            suffix="초등영어과외",
            parent="영어과외",
            page_type=PageType.GRADE,
            children=[],
            order=100,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="중등영어과외",
            suffix="중등영어과외",
            parent="영어과외",
            page_type=PageType.GRADE,
            children=[],
            order=110,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="고등영어과외",
            suffix="고등영어과외",
            parent="영어과외",
            page_type=PageType.GRADE,
            children=[],
            order=120,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="초등수학과외",
            suffix="초등수학과외",
            parent="수학과외",
            page_type=PageType.GRADE,
            children=[],
            order=200,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="중등수학과외",
            suffix="중등수학과외",
            parent="수학과외",
            page_type=PageType.GRADE,
            children=[],
            order=210,
            is_hub=True,
            enabled=True,
        )
    )
    registry.register(
        KeywordDefinition(
            name="고등수학과외",
            suffix="고등수학과외",
            parent="수학과외",
            page_type=PageType.GRADE,
            children=[],
            order=220,
            is_hub=True,
            enabled=True,
        )
    )

    return registry
