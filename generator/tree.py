from dataclasses import dataclass, field
from typing import Any, List, Optional

from generator.page_type import PageType


@dataclass
class Node:
    name: str
    type: PageType
    parent: Optional["Node"] = None
    children: List["Node"] = field(default_factory=list)
    depth: int = 0
    data: Any = None


class TreeBuilder:
    def build(self, regions):
        roots = []
        indexes = {}

        for region in regions:
            parent = None
            path = []

            for node_type, name in self._region_parts(region):
                path.append((node_type, name))
                key = tuple(path)

                if key not in indexes:
                    node = Node(
                        name=name,
                        type=node_type,
                        parent=parent,
                        depth=len(path) - 1,
                        data=region,
                    )
                    indexes[key] = node

                    if parent is None:
                        roots.append(node)
                    else:
                        parent.children.append(node)

                parent = indexes[key]

        return roots

    def _region_parts(self, region):
        parts = [
            (PageType.PROVINCE, region.province),
            (PageType.CITY, region.city),
            (PageType.DISTRICT, region.district),
            (PageType.DONG, region.dong),
        ]

        return [(node_type, name) for node_type, name in parts if name]
