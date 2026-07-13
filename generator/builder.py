import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from generator.breadcrumb import BreadcrumbBuilder
from generator.content_fallback import ContentFallbackGenerator
from generator.html_validator import HtmlValidator
from generator.image_builder import ImageBuilder
from generator.internal_links import InternalLinkBuilder
from generator.loader import DataLoader
from generator.keyword_definition import KeywordDefinition
from generator.manifest import ManifestBuilder
from generator.page_context import PageContext
from generator.page_factory import PageFactory
from generator.page_type import PageType
from generator.renderer import Renderer
from generator.routes import RouteBuilder
from generator.schema import SchemaBuilder
from generator.seo import SEOBuilder
from generator.sitemap import SitemapBuilder
from generator.site_builder import SiteBuilder
from generator.robots import RobotsBuilder
from generator.tree import TreeBuilder


class Builder:
    def __init__(self, filepath=None):
        self.filepath = filepath
        self.loader = DataLoader()
        self.tree_builder = TreeBuilder()
        self.page_factory = PageFactory()
        self.site_builder = SiteBuilder(page_factory=self.page_factory)
        self.route_builder = RouteBuilder()
        self.seo_builder = SEOBuilder()
        self.schema_builder = SchemaBuilder()
        self.breadcrumb_builder = BreadcrumbBuilder()
        self.internal_link_builder = InternalLinkBuilder()
        self.content_fallback_generator = ContentFallbackGenerator()
        self.image_builder = ImageBuilder()
        self.html_validator = HtmlValidator()
        self.sitemap_builder = SitemapBuilder()
        self.robots_builder = RobotsBuilder()
        self.manifest_builder = ManifestBuilder()
        self.renderer = Renderer()
        self.data = []
        self.tree = []
        self.pages = []
        self.routes = []
        self.content_results = []

    def load_data(self):
        print("Loading data...")
        self.data = self.loader.load(self.filepath)
        print(f"Loaded {len(self.data)} regions.")
        return self.data

    def build_tree(self):
        print("Building tree...")
        self.tree = self.tree_builder.build(self.data)
        return self.tree

    def build_site(self):
        print("Building site...")
        pages = self._build_region_pages()
        self.pages = self.site_builder.build(pages)
        return self.pages

    def build_routes(self):
        print("Generating routes...")
        self.routes = self.route_builder.generate(self.pages)
        return self.routes

    def build_seo(self):
        print("Generating SEO...")
        for route in self.routes:
            self.seo_builder.build(route)

    def build_schema(self):
        print("Generating schema...")
        for route in self.routes:
            self.schema_builder.build(route)

    def build_content(self):
        print("Generating content fallback...")
        try:
            self.content_results = self.content_fallback_generator.build(self.routes)
        except ValueError as error:
            print(str(error))
            self._write_abort_report(error)
            raise

        return self.content_results

    def build_breadcrumbs(self):
        print("Generating breadcrumbs...")
        for route in self.routes:
            self.breadcrumb_builder.build(route)

    def build_internal_links(self):
        print("Generating internal links...")
        for route in self.routes:
            self.internal_link_builder.build(route)

    def build_images(self):
        print("Generating images...")
        self.image_builder.build(self.routes)

    def clean_html_outputs(self):
        print("Cleaning HTML output...")
        output_dir = Path(self.renderer.output_dir)
        if not output_dir.exists():
            return

        for path in output_dir.rglob("index.html"):
            path.unlink()

    def render_pages(self):
        print("Rendering pages...")
        for route in self.routes:
            self.renderer.render(route)

    def build_sitemap(self):
        print("Generating sitemap...")
        self.sitemap_builder.build(self.routes)

    def build_robots(self):
        print("Generating robots...")
        self.robots_builder.build()

    def build_manifest(self):
        print("Generating manifest...")
        self.manifest_builder.build()

    def build_report(self):
        print("Generating build report...")
        pages = self._flatten_pages(self.routes)
        report = self._build_report_data(pages)
        output_path = Path(self.renderer.output_dir) / "build_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if report["html_validation_fail"]:
            self._print_html_validation_errors(report["html_validation_errors"])
            print("Build Failed")
            raise SystemExit(1)

        return output_path

    def build(self):
        self.load_data()
        self.build_tree()
        self.build_site()
        self.build_routes()
        self.build_seo()
        self.build_schema()
        self.build_breadcrumbs()
        self.build_internal_links()
        self.build_content()
        self.clean_html_outputs()
        self.build_images()
        self.render_pages()
        self.build_sitemap()
        self.build_robots()
        self.build_manifest()
        self.build_report()
        print("Done.")

    def _build_report_data(self, pages):
        url_counts = Counter(page.url for page in pages if page.url)
        canonical_counts = Counter(
            page.meta.canonical
            for page in pages
            if getattr(page, "meta", None) and page.meta.canonical
        )
        content_summary = self._content_summary()
        html_paths = [self.renderer._output_path(page) for page in pages if page.url]
        existing_html_paths = [path for path in html_paths if path.exists()]
        html_validation_errors = self.html_validator.validate(
            existing_html_paths,
            self.renderer.output_dir,
        )
        html_checks = self._check_html_files(html_validation_errors)

        return {
            "total_page_count": len(pages),
            "generated_html_count": len(existing_html_paths),
            "content_normal_count": content_summary["normal"],
            "fallback_generated_count": content_summary["generated"],
            "duplicate_content_key_count": len(
                self.content_fallback_generator.duplicate_content_keys
            ),
            "content_missing_count": content_summary["missing"],
            "broken_html_count": content_summary["broken_html"] + html_checks["html_tag_error_count"],
            "not_found_link_count": self._count_not_found_links(pages),
            "duplicate_url_count": sum(1 for count in url_counts.values() if count > 1),
            "duplicate_canonical_count": sum(1 for count in canonical_counts.values() if count > 1),
            "sitemap_url_count": self._sitemap_url_count(),
            "html_tag_error_count": html_checks["html_tag_error_count"],
            "json_ld_error_count": html_checks["json_ld_error_count"],
            "html_validation_pass": len(existing_html_paths)
            - len({error.path for error in html_validation_errors}),
            "html_validation_fail": len(
                {error.path for error in html_validation_errors}
            ),
            "html_validation_errors": [
                error.to_dict() for error in html_validation_errors
            ],
            "duplicate_content_keys": self.content_fallback_generator.duplicate_content_keys,
            "duplicate_urls": [
                url for url, count in url_counts.items() if count > 1
            ],
            "duplicate_canonicals": [
                canonical for canonical, count in canonical_counts.items() if count > 1
            ],
        }

    def _write_abort_report(self, error):
        output_path = Path(self.renderer.output_dir) / "build_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duplicate_content_keys = getattr(
            self.content_fallback_generator,
            "duplicate_content_keys",
            [],
        )
        report = {
            "status": "aborted",
            "error": str(error).splitlines()[0],
            "total_page_count": len(self._flatten_pages(self.routes)),
            "generated_html_count": 0,
            "content_normal_count": 0,
            "fallback_generated_count": 0,
            "duplicate_content_key_count": len(duplicate_content_keys),
            "content_missing_count": 0,
            "broken_html_count": 0,
            "not_found_link_count": 0,
            "duplicate_url_count": 0,
            "duplicate_canonical_count": 0,
            "duplicate_content_keys": duplicate_content_keys,
        }
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _content_summary(self):
        summary = {
            "normal": 0,
            "generated": 0,
            "missing": 0,
            "broken_html": 0,
        }

        for result in self.content_results:
            if result.status == "EXCEL":
                summary["normal"] += 1
            elif result.status == "GENERATED":
                summary["generated"] += 1

            if "EMPTY" in result.reasons:
                summary["missing"] += 1

            if "BROKEN_HTML" in result.reasons:
                summary["broken_html"] += 1

        return summary

    def _flatten_pages(self, pages):
        roots = pages if isinstance(pages, list) else [pages]
        flattened = []

        for page in roots:
            self._walk_page(page, flattened)

        return flattened

    def _walk_page(self, page, flattened):
        if page is None:
            return

        flattened.append(page)

        for child in getattr(page, "children", []):
            self._walk_page(child, flattened)

    def _count_not_found_links(self, pages):
        urls = {page.url for page in pages if page.url}
        missing = 0

        for page in pages:
            links = getattr(page, "internal_links", {}) or {}
            for value in links.values():
                items = value if isinstance(value, list) else [value]
                for item in items:
                    if not item:
                        continue

                    url = item.get("url")
                    if url and url.startswith("/") and url not in urls:
                        missing += 1

        return missing

    def _check_html_files(self, html_validation_errors):
        return {
            "html_tag_error_count": len(
                {
                    error.path
                    for error in html_validation_errors
                    if error.error_type == "HTML_STRUCTURE"
                }
            ),
            "json_ld_error_count": len(
                [
                    error
                    for error in html_validation_errors
                    if error.error_type == "JSON_LD"
                ]
            ),
        }

    def _print_html_validation_errors(self, errors):
        print("HTML validation errors:")
        for error in errors:
            location = error["path"]
            if error.get("line") is not None:
                location += f":{error['line']}"
                if error.get("column") is not None:
                    location += f":{error['column']}"

            print(f"- {location}")
            print(f"  title: {error.get('title', '')}")
            print(f"  url: {error.get('url', '')}")
            print(f"  type: {error.get('error_type', '')}")
            print(f"  message: {error.get('message', '')}")

    def _sitemap_url_count(self):
        path = Path(self.renderer.output_dir) / "sitemap.xml"
        if not path.exists():
            return 0

        return len(re.findall(r"<loc>", path.read_text(encoding="utf-8")))

    def _build_region_pages(self):
        if not self.data:
            return []

        pages = {}
        roots = []
        nation = self._get_or_create_page(
            pages,
            roots,
            self._empty_region(),
            self._keyword("전국과외", PageType.NATION),
        )

        for region in self.data:
            if not self._is_region_row(region):
                continue

            province = self._get_or_create_page(
                pages,
                roots,
                region,
                self._keyword("과외", PageType.PROVINCE),
                parent=nation,
            )
            city = self._get_or_create_page(
                pages,
                roots,
                region,
                self._keyword("과외", PageType.CITY),
                parent=province,
            )
            parent = city

            if region.district:
                parent = self._get_or_create_page(
                    pages,
                    roots,
                    region,
                    self._keyword("과외", PageType.DISTRICT),
                    parent=city,
                )

            self._get_or_create_page(
                pages,
                roots,
                region,
                self._keyword("과외", PageType.DONG),
                parent=parent,
            )

        return roots

    def _get_or_create_page(self, pages, roots, region, keyword, parent=None):
        page = self.page_factory.create(PageContext(region=region, keyword=keyword))
        if not page:
            return None

        key = self._page_cache_key(page)
        if key in pages:
            page = pages[key]
        else:
            pages[key] = page

        if parent is None:
            if page not in roots:
                roots.append(page)
        else:
            page.parent = parent
            if page not in parent.children:
                parent.children.append(page)

        return page

    def _page_cache_key(self, page):
        region = page.region
        if page.page_type == PageType.NATION:
            return (page.page_type,)

        if page.page_type == PageType.PROVINCE:
            return (page.page_type, region.province)

        if page.page_type == PageType.CITY:
            return (page.page_type, region.province, region.city)

        if page.page_type == PageType.DISTRICT:
            return (
                page.page_type,
                region.province,
                region.city,
                region.district,
            )

        return (
            page.page_type,
            region.province,
            region.city,
            region.district,
            region.dong,
            page.keyword.name,
        )

    def _keyword(self, suffix, page_type):
        return KeywordDefinition(
            name=f"{page_type.value}:{suffix}",
            suffix=suffix,
            parent=None,
            page_type=page_type,
        )

    def _empty_region(self):
        class EmptyRegion:
            province = ""
            city = ""
            district = ""
            dong = ""

        return EmptyRegion()

    def _is_region_row(self, region):
        values = [region.province, region.city, region.district, region.dong]
        return all(self._is_region_value(value) for value in values)

    def _is_region_value(self, value):
        if not value:
            return True

        if len(value) > 40:
            return False

        if "과외" in value:
            return False

        return "<" not in value and ">" not in value and "\n" not in value


class _HTMLTagChecker(HTMLParser):
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self):
        super().__init__()
        self.stack = []
        self.has_error = False

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS:
            return

        if not self.stack or self.stack[-1] != tag:
            self.has_error = True
            return

        self.stack.pop()

    def close(self):
        super().close()
        if self.stack:
            self.has_error = True
