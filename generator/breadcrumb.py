class BreadcrumbBuilder:
    def build(self, page):
        if not hasattr(page, "parent"):
            return []

        page.breadcrumb = self._items(page)

        for child in page.children:
            self.build(child)

        return page.breadcrumb

    def _items(self, page):
        items = []
        current = page

        while current is not None:
            items.append(
                {
                    "title": current.title,
                    "url": current.url,
                }
            )
            current = current.parent

        items.reverse()
        return items
