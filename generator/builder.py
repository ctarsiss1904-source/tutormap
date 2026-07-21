import json
import re
import shutil
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from config import ASSETS_DIR, BASE_URL, DATA_DIR, OUTPUT_DIR, PROJECT_ROOT, TEMPLATES_DIR
from generator.breadcrumb import BreadcrumbBuilder
from generator.content_fallback import ContentFallbackGenerator
from generator.html_validator import HtmlValidator
from generator.image_builder import ImageBuilder
from generator.internal_links import InternalLinkBuilder
from generator.loader import DataLoader, Region
from generator.keyword_definition import KeywordDefinition
from generator.manifest import ManifestBuilder
from generator.page import Page
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
    GENERATED_OUTPUT_FILES = {
        "sitemap.xml",
        "robots.txt",
        "manifest.webmanifest",
        "build_report.json",
        "site_audit_report.json",
    }

    def __init__(
        self,
        filepath=None,
        project_root=PROJECT_ROOT,
        data_dir=DATA_DIR,
        templates_dir=TEMPLATES_DIR,
        assets_dir=ASSETS_DIR,
        output_dir=OUTPUT_DIR,
    ):
        self.project_root = Path(project_root).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.templates_dir = Path(templates_dir).resolve()
        self.assets_dir = Path(assets_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.filepath = Path(filepath).resolve() if filepath else None
        self.loader = DataLoader()
        self.tree_builder = TreeBuilder()
        self.page_factory = PageFactory()
        self.site_builder = SiteBuilder(page_factory=self.page_factory)
        self.route_builder = RouteBuilder()
        self.seo_builder = SEOBuilder()
        self.schema_builder = SchemaBuilder()
        self.breadcrumb_builder = BreadcrumbBuilder()
        self.internal_link_builder = InternalLinkBuilder()
        self.content_fallback_generator = ContentFallbackGenerator(report_path=self.output_dir)
        self.image_builder = ImageBuilder(output_dir=self.output_dir)
        self.html_validator = HtmlValidator()
        self.sitemap_builder = SitemapBuilder(output_dir=self.output_dir)
        self.robots_builder = RobotsBuilder(output_dir=self.output_dir)
        self.manifest_builder = ManifestBuilder(output_dir=self.output_dir)
        self.renderer = Renderer(
            template_dir=self.templates_dir,
            output_dir=self.output_dir,
            asset_dir=self.assets_dir,
        )
        self.data = []
        self.tree = []
        self.pages = []
        self.routes = []
        self.content_results = []
        self.snapshot_pages = []
        self.loaded_from_snapshot = False
        self.build_version = None
        self.build_time = None

    def load_data(self):
        print("Loading data...")
        if self.filepath:
            self.data = self.loader.load(self.filepath)
        else:
            self.data = self.loader.load_directory(self.data_dir)

        self.snapshot_pages = []
        self.loaded_from_snapshot = False
        if not self.data:
            self.snapshot_pages = SnapshotRouteLoader(
                self.output_dir,
                self.data_dir / "route_snapshot.txt",
            ).load()
            self.loaded_from_snapshot = bool(self.snapshot_pages)

        self._print_build_paths()
        self._print_data_summary()
        return self.data

    def build_tree(self):
        print("Building tree...")
        self.tree = self.tree_builder.build(self.data)
        return self.tree

    def build_site(self):
        print("Building site...")
        pages = self.snapshot_pages if self.loaded_from_snapshot else self._build_region_pages()
        if not pages:
            raise RuntimeError(
                "No build data was loaded. The data directory is empty or invalid, "
                "and no route snapshot could be recovered from output/index.html files. "
                f"Data Directory: {self.data_dir}"
            )

        self.pages = pages if self.loaded_from_snapshot else self.site_builder.build(pages)
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
        if not self.pages:
            raise RuntimeError("Refusing to clean output because no pages were built.")

        output_dir = Path(self.renderer.output_dir)
        if not output_dir.exists():
            return

        for path in output_dir.rglob("index.html"):
            path.unlink()

    def clean_build_outputs(self):
        print("Cleaning previous build outputs...")
        output_dir = Path(self.renderer.output_dir)
        if not output_dir.exists():
            return

        for path in output_dir.rglob("index.html"):
            path.unlink()

        for filename in self.GENERATED_OUTPUT_FILES:
            path = output_dir / filename
            if path.exists() and path.is_file():
                path.unlink()

        render_checks = output_dir / "render_checks"
        if render_checks.exists() and render_checks.is_dir():
            shutil.rmtree(render_checks)

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

        index_path = Path(self.renderer.output_dir) / "index.html"
        if not index_path.exists():
            print("Build Failed")
            raise RuntimeError(f"Missing required output file: {index_path}")

        return output_path

    def build(self):
        self._start_build_version()
        self.clean_build_outputs()
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
        self.verify_build_outputs()
        print("Done.")

    def _start_build_version(self):
        now = datetime.now()
        self.build_time = now.strftime("%Y-%m-%d %H:%M:%S")
        self.build_version = now.strftime("%Y%m%d-%H%M%S")
        self.renderer.set_build_metadata(self.build_version, self.build_time)
        self.image_builder.set_build_version(self.build_version)
        print(f"Build Version: {self.build_version}")

    def _print_build_paths(self):
        print(f"Project Root: {self.project_root}")
        print(f"Data Directory: {self.data_dir}")
        print(f"Templates Directory: {self.templates_dir}")
        print(f"Assets Directory: {self.assets_dir}")
        print(f"Output Directory: {self.output_dir}")

    def _print_data_summary(self):
        regions = len(self.data)
        districts = len({item.district for item in self.data if getattr(item, "district", "")})
        dongs = len({item.dong for item in self.data if getattr(item, "dong", "")})

        if self.loaded_from_snapshot:
            snapshot_pages = self._flatten_pages(self.snapshot_pages)
            regions = len(
                {
                    tuple(
                        getattr(page.region, attr, "")
                        for attr in ("province", "city", "district", "dong")
                    )
                    for page in snapshot_pages
                    if page.page_type == PageType.DONG
                }
            )
            districts = len(
                {
                    (page.region.province, page.region.city, page.region.district)
                    for page in snapshot_pages
                    if page.page_type == PageType.DISTRICT and page.region.district
                }
            )
            dongs = len(
                {
                    (page.region.province, page.region.city, page.region.district, page.region.dong)
                    for page in snapshot_pages
                    if page.page_type == PageType.DONG and page.region.dong
                }
            )
            print("Data Source: output route snapshot")
        else:
            print("Data Source: structured data directory")

        print(f"Loaded Regions: {regions}")
        print(f"Loaded Districts: {districts}")
        print(f"Loaded Dongs: {dongs}")

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
            "build_version": self.build_version,
            "build_time": self.build_time,
            "total_page_count": len(pages),
            "generated_html_count": len(existing_html_paths),
            "generated_image_count": self._generated_image_count(),
            "generated_webp_count": self._generated_webp_count(),
            "generated_schema_count": self._generated_schema_count(pages),
            "generated_sitemap_count": self._generated_sitemap_count(),
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
            "build_version": self.build_version,
            "build_time": self.build_time,
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

    def _generated_image_count(self):
        image_dir = Path(self.renderer.output_dir) / "assets" / "images"
        if not image_dir.exists():
            return 0

        extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico"}
        return sum(
            1
            for path in image_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in extensions
        )

    def _generated_webp_count(self):
        image_dir = Path(self.renderer.output_dir) / "assets" / "images"
        if not image_dir.exists():
            return 0

        return sum(1 for path in image_dir.rglob("*.webp") if path.is_file())

    def _generated_schema_count(self, pages):
        return sum(len(getattr(page, "schema", []) or []) for page in pages)

    def _generated_sitemap_count(self):
        return 1 if (Path(self.renderer.output_dir) / "sitemap.xml").exists() else 0

    def verify_build_outputs(self):
        print("Verifying build outputs...")
        checks = [
            self._verify_index_build_version,
            self._verify_main_hero_image,
            self._verify_css_outputs,
            self._verify_html_outputs,
            self._verify_sitemap,
            self._verify_robots,
            self._verify_manifest,
        ]

        for check in checks:
            check()

    def _verify_index_build_version(self):
        index_path = Path(self.renderer.output_dir) / "index.html"
        if not index_path.exists():
            self._fail_build(f"Missing required output file: {index_path}")

        text = index_path.read_text(encoding="utf-8")
        if f"Build Version: {self.build_version}" not in text:
            self._fail_build(
                f"output/index.html does not match Build Version: {self.build_version}"
            )

        if "Template: home.html" not in text:
            self._fail_build("output/index.html is missing home template build metadata.")

    def _verify_main_hero_image(self):
        index_path = Path(self.renderer.output_dir) / "index.html"
        text = index_path.read_text(encoding="utf-8")
        match = re.search(
            r'<figure\s+class=["\']hero-image["\'][\s\S]*?<img\b[^>]*?\bsrc=["\']([^"\']+)["\']',
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            self._fail_build("Main hero image markup is missing from output/index.html.")

        src = match.group(1).split("?", 1)[0].split("#", 1)[0]
        hero_path = (index_path.parent / src).resolve()
        home_image_dir = (Path(self.renderer.output_dir) / "assets" / "images" / "home").resolve()

        if not hero_path.exists() or not hero_path.is_file():
            self._fail_build(f"Main hero image file does not exist: {hero_path}")

        if not hero_path.is_relative_to(home_image_dir):
            self._fail_build(f"Main hero image is outside home image directory: {hero_path}")

    def _verify_css_outputs(self):
        css_dir = Path(self.renderer.output_dir) / "assets" / "css"
        for css_name in ("home.css", "site.css"):
            path = css_dir / css_name
            if not path.exists() or not path.is_file():
                self._fail_build(f"Missing required CSS file: {path}")

    def _verify_html_outputs(self):
        html_paths = [path for path in Path(self.renderer.output_dir).rglob("index.html")]
        errors = self.html_validator.validate(html_paths, self.renderer.output_dir)
        if errors:
            self._print_html_validation_errors([error.to_dict() for error in errors])
            self._fail_build("HTML validation failed.")

    def _verify_sitemap(self):
        path = Path(self.renderer.output_dir) / "sitemap.xml"
        if not path.exists() or not path.is_file():
            self._fail_build(f"Missing sitemap: {path}")

        try:
            root = ElementTree.parse(path).getroot()
        except ElementTree.ParseError as error:
            self._fail_build(f"Invalid sitemap XML: {error}")

        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        expected_url_prefix = f"{BASE_URL.rstrip('/')}/"
        urls = root.findall("sm:url", namespace)
        if not urls:
            self._fail_build("Sitemap has no URLs.")

        for url in urls:
            locs = url.findall("sm:loc", namespace)
            if len(locs) != 1:
                self._fail_build("Sitemap URL entry must contain exactly one loc element.")

            loc = (locs[0].text or "").strip()
            if not loc.startswith(expected_url_prefix):
                self._fail_build(f"Sitemap has invalid URL: {loc!r}")

        if len(urls) != self._sitemap_url_count():
            self._fail_build("Sitemap URL count does not match loc count.")

    def _verify_robots(self):
        path = Path(self.renderer.output_dir) / "robots.txt"
        if not path.exists() or not path.is_file():
            self._fail_build(f"Missing robots.txt: {path}")

        text = path.read_text(encoding="utf-8")
        if "Sitemap:" not in text:
            self._fail_build("robots.txt is missing Sitemap.")

    def _verify_manifest(self):
        path = Path(self.renderer.output_dir) / "manifest.webmanifest"
        if not path.exists() or not path.is_file():
            self._fail_build(f"Missing manifest: {path}")

        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            self._fail_build(f"Invalid manifest JSON: {error}")

    def _fail_build(self, message):
        print(message)
        print("Build Failed")
        raise SystemExit(1)

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


class SnapshotRouteLoader:
    SUBJECT_MARKERS = ("영어", "수학", "국어", "과학")

    def __init__(self, output_dir, snapshot_file=None):
        self.output_dir = Path(output_dir).resolve()
        self.snapshot_file = Path(snapshot_file).resolve() if snapshot_file else None

    def load(self):
        snapshot_exists = self.snapshot_file and self.snapshot_file.exists()
        if not self.output_dir.exists() and not snapshot_exists:
            return []

        route_parts = self._route_parts()
        if not route_parts or () not in route_parts:
            return []

        children = self._children_by_parent(route_parts)
        page_types = {}
        pages = {}

        for parts in sorted(route_parts, key=lambda item: (len(item), item)):
            page_type = self._page_type(parts, page_types, children)
            page_types[parts] = page_type
            parent = pages.get(parts[:-1])
            region = self._region(parts, page_types)
            title = "TutorMap" if page_type == PageType.NATION else parts[-1]
            keyword = KeywordDefinition(
                name=title,
                suffix="",
                parent=None,
                page_type=page_type,
            )
            page = Page(
                id="/".join(parts) or "TutorMap",
                title=title,
                url_segment="" if page_type == PageType.NATION else title,
                region=region,
                keyword=keyword,
                page_type=page_type,
                parent=parent,
                url=None,
                template=None,
                meta=None,
                schema=None,
                is_hub=True,
            )
            pages[parts] = page
            if parent is not None and page not in parent.children:
                parent.children.append(page)

        return [pages[()]]

    def _route_parts(self):
        parts = set()
        for path in self.output_dir.rglob("index.html"):
            try:
                relative = path.relative_to(self.output_dir)
            except ValueError:
                continue

            parent = relative.parent
            if str(parent) == ".":
                parts.add(())
            else:
                parts.add(tuple(parent.parts))

        if not parts and self.snapshot_file and self.snapshot_file.exists():
            parts.update(self._route_parts_from_snapshot())

        return parts

    def _route_parts_from_snapshot(self):
        parts = set()
        for line in self.snapshot_file.read_text(encoding="utf-8-sig").splitlines():
            route = line.strip()
            if not route or route.startswith("#"):
                continue

            route = route.strip("/")
            parts.add(tuple(route.split("/")) if route else ())

        return parts

    def _children_by_parent(self, route_parts):
        children = {}
        for parts in route_parts:
            children.setdefault(parts[:-1], []).append(parts)
        return children

    def _page_type(self, parts, page_types, children):
        depth = len(parts)
        if depth == 0:
            return PageType.NATION
        if depth == 1:
            return PageType.PROVINCE
        if depth == 2:
            return PageType.CITY

        parent_type = page_types.get(parts[:-1])
        if parent_type == PageType.DONG:
            return PageType.SUBJECT
        if parent_type == PageType.SUBJECT:
            return PageType.GRADE
        if parent_type == PageType.GRADE:
            return PageType.SCHOOL

        return PageType.DONG if self._looks_like_dong(parts, children) else PageType.DISTRICT

    def _looks_like_dong(self, parts, children):
        base = self._strip_suffix(parts[-1])
        child_segments = [item[-1] for item in children.get(parts, [])]

        for child_segment in child_segments:
            child_base = self._strip_suffix(child_segment)
            if child_base.startswith(base) and any(marker in child_base for marker in self.SUBJECT_MARKERS):
                return True

        if not child_segments:
            return True

        return base.endswith(("동", "읍", "면", "리"))

    def _region(self, parts, page_types):
        province = self._strip_suffix(parts[0]) if len(parts) > 0 else ""
        city = self._strip_suffix(parts[1]) if len(parts) > 1 else ""
        district = ""
        dong = ""

        for index in range(2, len(parts) + 1):
            page_type = page_types.get(parts[:index])
            if page_type == PageType.DISTRICT:
                district = self._strip_suffix(parts[index - 1])
            elif page_type == PageType.DONG:
                dong = self._strip_suffix(parts[index - 1])

        return Region(province=province, city=city, district=district, dong=dong)

    def _strip_suffix(self, value):
        return value[:-2] if value.endswith("과외") else value


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
