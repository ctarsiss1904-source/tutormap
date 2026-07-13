from config import BASE_URL, SITE_NAME
from generator.page_type import PageType


class SchemaBuilder:
    def build(self, page):
        if not hasattr(page, "title"):
            return []

        page.schema = [
            self.website(page),
            self.webpage(page),
        ]
        if page.page_type == PageType.NATION:
            page.schema.append(self.organization(page))
        else:
            page.schema.append(self.breadcrumb(page))

        for child in page.children:
            self.build(child)

        return page.schema

    def website(self, page):
        return {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": SITE_NAME,
            "url": self._site_url(),
            "inLanguage": "ko-KR",
        }

    def webpage(self, page):
        return {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page.title,
            "url": self._absolute_url(page.url),
            "isPartOf": {
                "@type": "WebSite",
                "name": SITE_NAME,
                "url": self._site_url(),
            },
        }

    def organization(self, page):
        return {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": SITE_NAME,
            "url": self._site_url(),
        }

    def breadcrumb(self, page):
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index,
                    "name": item["title"],
                    "item": self._absolute_url(item["url"]),
                }
                for index, item in enumerate(self._breadcrumb_items(page), start=1)
            ],
        }

    def _breadcrumb_items(self, page):
        if page.breadcrumb:
            return page.breadcrumb

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

    def _site_url(self):
        return BASE_URL.rstrip("/") or "/"

    def _absolute_url(self, url):
        if not url:
            return ""

        base_url = BASE_URL.rstrip("/")
        if not base_url:
            return url

        return f"{base_url}{url}"
