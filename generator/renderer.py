from pathlib import Path
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import ASSETS_DIR, OUTPUT_DIR, TEMPLATES_DIR
from generator.page_type import PageType


class Renderer:
    def __init__(
        self,
        template_dir=TEMPLATES_DIR,
        output_dir=OUTPUT_DIR,
        asset_dir=ASSETS_DIR,
        build_version=None,
        build_time=None,
    ):
        self.output_dir = Path(output_dir).resolve()
        self.asset_dir = Path(asset_dir).resolve()
        self.build_version = build_version
        self.build_time = build_time
        self._assets_copied = False
        self.environment = Environment(
            loader=FileSystemLoader(str(Path(template_dir).resolve())),
            autoescape=select_autoescape(["html"]),
        )

    def set_build_metadata(self, build_version, build_time):
        self.build_version = build_version
        self.build_time = build_time

    def render(self, page):
        if not getattr(page, "url", None):
            return

        self._copy_static_assets()
        template_name = "home.html" if page.page_type == PageType.NATION else "base.html"
        css_path = "assets/css/home.css" if page.page_type == PageType.NATION else "assets/css/site.css"
        template = self.environment.get_template(template_name)
        html = template.render(
            page=page,
            css_href=self._relative_asset(page, css_path),
        )
        html = self._append_build_comment(html, template_name)
        output_path = self._output_path(page)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        for child in page.children:
            self.render(child)

    def _output_path(self, page):
        parts = [part for part in page.url.strip("/").split("/") if part]
        return self.output_dir.joinpath(*parts, "index.html")

    def _relative_asset(self, page, public_path):
        depth = len([part for part in page.url.strip("/").split("/") if part])
        prefix = "../" * depth
        return self._with_build_version(f"{prefix}{public_path}")

    def _with_build_version(self, path):
        if not self.build_version:
            return path

        separator = "&" if "?" in path else "?"
        return f"{path}{separator}v={self.build_version}"

    def _append_build_comment(self, html, template_name):
        if not self.build_version or not self.build_time:
            return html

        comment = "\n".join(
            [
                "<!--",
                f"Build Time: {self.build_time}",
                f"Build Version: {self.build_version}",
                f"Template: {template_name}",
                "-->",
            ]
        )
        return f"{html.rstrip()}\n{comment}\n"

    def _copy_static_assets(self):
        if self._assets_copied:
            return

        for css_name in ["site.css", "home.css"]:
            css_source = self.asset_dir / "css" / css_name
            if not css_source.exists():
                continue

            css_output = self.output_dir / "assets" / "css" / css_name
            css_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(css_source, css_output)

        self._assets_copied = True
