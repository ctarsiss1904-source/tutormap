from generator.page_type import PageType


class RouteBuilder:
    def generate(self, pages):
        page_list = self._normalize_pages(pages)

        for page in page_list:
            self._assign_url(page)

        return page_list

    def _normalize_pages(self, pages):
        if pages is None:
            return []

        if isinstance(pages, list):
            return pages

        return [pages]

    def _assign_url(self, page):
        if not hasattr(page, "url_segment") or not hasattr(page, "children"):
            return

        page.url = self._build_url(page)

        for child in page.children:
            self._assign_url(child)

    def _build_url(self, page):
        if page.page_type == PageType.NATION:
            return "/"

        nodes = []
        current = page

        while current is not None:
            nodes.append(current)
            current = current.parent

        nodes.reverse()
        if len(nodes) > 1 and nodes[0].page_type == PageType.NATION:
            nodes = nodes[1:]

        parts = [node.url_segment for node in nodes if node.url_segment]
        return "/" + "/".join(parts) + "/"
