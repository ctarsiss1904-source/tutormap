from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from config import BASE_URL, OUTPUT_DIR


class SitemapBuilder:
    def __init__(self, output_dir=OUTPUT_DIR):
        self.output_dir = Path(output_dir).resolve()

    def build(self, pages):
        urls = []

        for page in self._normalize_pages(pages):
            self._collect_urls(page, urls)

        sitemap = self._build_xml(self._unique_urls(urls))
        output_path = self.output_dir / "sitemap.xml"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ElementTree(sitemap).write(
            output_path,
            encoding="utf-8",
            xml_declaration=True,
        )

        return output_path

    def _normalize_pages(self, pages):
        if pages is None:
            return []

        if isinstance(pages, list):
            return pages

        return [pages]

    def _collect_urls(self, page, urls):
        if getattr(page, "url", None):
            urls.append(self._absolute_url(page.url))

        for child in page.children:
            self._collect_urls(child, urls)

    def _build_xml(self, urls):
        urlset = Element(
            "urlset",
            xmlns="http://www.sitemaps.org/schemas/sitemap/0.9",
        )

        for page_url in urls:
            url = SubElement(urlset, "url")
            loc = SubElement(url, "loc")
            loc.text = page_url

        return urlset

    def _unique_urls(self, urls):
        seen = set()
        unique_urls = []

        for url in urls:
            if url in seen:
                continue

            seen.add(url)
            unique_urls.append(url)

        return unique_urls

    def _absolute_url(self, url):
        base_url = BASE_URL.rstrip("/")
        if not base_url:
            return url

        return f"{base_url}{url}"
