from generator.keyword_definition import create_default_keyword_registry
from generator.page_context import PageContext
from generator.page_definition import create_default_registry
from generator.page_factory import PageFactory
from generator.page_type import PageType


class SiteBuilder:
    def __init__(self, page_registry=None, keyword_registry=None, page_factory=None):
        self.page_registry = page_registry or create_default_registry()
        self.keyword_registry = keyword_registry or create_default_keyword_registry()
        self.page_factory = page_factory or PageFactory(self.page_registry)

    def build(self, pages):
        roots = self._normalize_pages(pages)
        visited = set()

        for page in roots:
            self._expand(page, visited)

        self.connect_existing_pages(roots)
        self._validate_subject_connections(roots)
        self._validate_expansion(roots)
        return roots

    def _normalize_pages(self, pages):
        if pages is None:
            return []

        if isinstance(pages, list):
            return pages

        return [pages]

    def _expand(self, page, visited):
        page_id = id(page)
        if page_id in visited:
            return

        visited.add(page_id)

        self._connect_children(page, self.page_factory.create_children(page))

        for child in self._create_children_from_definitions(page):
            self._connect_child(page, child)

        for child in list(page.children):
            self._expand(child, visited)

    def _create_children_from_definitions(self, parent):
        page_definition = self.page_registry.get(parent.page_type)
        if not page_definition:
            return []

        keyword_children = sorted(
            self._keyword_children(parent.keyword),
            key=lambda keyword: keyword.order,
        )

        children = []
        for child_type in page_definition.child_types:
            if not self.page_registry.get(child_type):
                continue

            for keyword in keyword_children:
                if not keyword.enabled:
                    continue

                if keyword.page_type != child_type:
                    continue

                children.append(
                    self.page_factory.create(
                        PageContext(
                            region=parent.region,
                            keyword=keyword,
                            parent=parent,
                        )
                    )
                )

        return children

    def _keyword_children(self, keyword):
        children = self.keyword_registry.children(keyword.name)
        if children:
            return children

        if keyword.suffix != keyword.name:
            return self.keyword_registry.children(keyword.suffix)

        return []

    def _connect_children(self, parent, children):
        if not children:
            return

        for child in children:
            self._connect_child(parent, child)

    def _connect_child(self, parent, child):
        child.parent = parent

        if child not in parent.children:
            parent.children.append(child)

    def connect_existing_pages(self, pages):
        all_pages = self._flatten(pages)
        index = self._page_index(all_pages)

        for parent in all_pages:
            for child_type, keyword in self._expected_children(parent):
                key = (self._region_key(parent.region), child_type, keyword.name)
                for child in index.get(key, []):
                    self._connect_child(parent, child)

    def _page_index(self, pages):
        index = {}
        for page in pages:
            key = (
                self._region_key(page.region),
                page.page_type,
                page.keyword.name,
            )
            index.setdefault(key, []).append(page)

        return index

    def _region_key(self, region):
        return (
            getattr(region, "province", ""),
            getattr(region, "city", ""),
            getattr(region, "district", ""),
            getattr(region, "dong", ""),
        )

    def _validate_subject_connections(self, pages):
        unconnected = []
        for page in self._flatten(pages):
            if page.page_type != PageType.SUBJECT:
                continue

            if page.parent is None or page.parent.page_type != PageType.DONG:
                unconnected.append(page.title)

        if unconnected:
            details = "\n".join(unconnected[:50])
            raise ValueError(
                "Page Tree connection failed. Unconnected SUBJECT pages:\n"
                f"{details}"
            )

    def _validate_expansion(self, pages):
        missing = []
        for page in self._flatten(pages):
            expected = self._expected_children(page)
            if not expected:
                continue

            actual = {
                (child.page_type, child.keyword.name)
                for child in getattr(page, "children", [])
            }
            for child_type, keyword in expected:
                if (child_type, keyword.name) not in actual:
                    missing.append(
                        f"{page.title} -> {child_type.name}:{keyword.name}"
                    )

        if missing:
            details = "\n".join(missing[:50])
            raise ValueError(
                "Page Tree expansion failed. Missing child pages:\n"
                f"{details}"
            )

    def _expected_children(self, parent):
        page_definition = self.page_registry.get(parent.page_type)
        if not page_definition:
            return []

        keyword_children = self._keyword_children(parent.keyword)
        expected = []
        for child_type in page_definition.child_types:
            if not self.page_registry.get(child_type):
                continue

            for keyword in keyword_children:
                if keyword.enabled and keyword.page_type == child_type:
                    expected.append((child_type, keyword))

        return expected

    def _flatten(self, pages):
        flattened = []
        for page in self._normalize_pages(pages):
            self._walk(page, flattened)
        return flattened

    def _walk(self, page, flattened):
        if page is None:
            return

        flattened.append(page)
        for child in getattr(page, "children", []):
            self._walk(child, flattened)
