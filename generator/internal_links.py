class InternalLinkBuilder:
    def build(self, page):
        if not hasattr(page, "parent"):
            return {}

        page.internal_links = {
            "parent": self._parent_link(page),
            "children": self._child_links(page),
            "siblings": self._sibling_links(page),
            "related": self._related_links(page),
        }

        for child in page.children:
            self.build(child)

        return page.internal_links

    def _parent_link(self, page):
        if page.parent is None:
            return None

        return self._link(page.parent)

    def _child_links(self, page):
        return [self._link(child) for child in page.children]

    def _sibling_links(self, page):
        if page.parent is None:
            return []

        return [
            self._link(sibling)
            for sibling in page.parent.children
            if sibling is not page
        ]

    def _related_links(self, page):
        links = []

        if page.parent is not None:
            links.append(self._link(page.parent))

        links.extend(self._sibling_links(page)[:5])
        links.extend(self._child_links(page)[:5])

        unique_links = []
        seen = set()
        for link in links:
            url = link["url"]
            if url in seen:
                continue

            seen.add(url)
            unique_links.append(link)

        return unique_links

    def _link(self, page):
        return {
            "title": page.title,
            "url": page.url,
        }
