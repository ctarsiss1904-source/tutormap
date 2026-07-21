from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent
from urllib.parse import quote, urlsplit, urlunsplit

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
        tree = ElementTree(sitemap)
        indent(tree, space="    ")
        tree.write(
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
        url = self._absolute_url(getattr(page, "url", None))
        if url:
            urls.append(url)

        for child in getattr(page, "children", []):
            self._collect_urls(child, urls)

    def _build_xml(self, urls):
        urlset = Element(
            "urlset",
            xmlns="http://www.sitemaps.org/schemas/sitemap/0.9",
        )

        for page_url in urls:
            if not self._is_valid_sitemap_url(page_url):
                raise RuntimeError(f"Build Failed: Invalid sitemap URL: {page_url!r}")

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
        if not url:
            return None

        value = str(url).strip()
        if not value:
            return None

        configured_base_url = BASE_URL.rstrip("/")
        parsed_base_url = urlsplit(configured_base_url)
        if parsed_base_url.scheme != "https" or not parsed_base_url.netloc:
            raise RuntimeError(
                f"Build Failed: Invalid sitemap base URL: {configured_base_url!r}"
            )

        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlsplit(value)
            path = parsed.path or "/"
            query = parsed.query
        else:
            path = value if value.startswith("/") else f"/{value}"
            query = ""

        if not path.endswith("/"):
            path = f"{path}/"

        encoded_path = quote(path, safe="/%")
        return urlunsplit(
            (parsed_base_url.scheme, parsed_base_url.netloc, encoded_path, query, "")
        )

    def _is_valid_sitemap_url(self, url):
        if not url:
            return False

        parsed_base_url = urlsplit(BASE_URL.rstrip("/"))
        parsed = urlsplit(url)
        return (
            parsed.scheme == parsed_base_url.scheme
            and parsed.netloc == parsed_base_url.netloc
            and bool(parsed.path)
            and "<" not in url
            and ">" not in url
        )
