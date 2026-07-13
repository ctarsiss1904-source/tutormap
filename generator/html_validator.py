import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass
class HtmlValidationError:
    title: str
    url: str
    path: str
    error_type: str
    message: str
    line: int | None = None
    column: int | None = None

    def to_dict(self):
        return {
            "title": self.title,
            "url": self.url,
            "path": self.path,
            "error_type": self.error_type,
            "message": self.message,
            "line": self.line,
            "column": self.column,
        }


class HtmlValidator:
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

    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def validate(self, paths, output_dir):
        output_dir = Path(output_dir)
        errors = []

        for path in paths:
            html = path.read_text(encoding="utf-8")
            context = self._page_context(html, path, output_dir)
            parser = _StructureParser(self.VOID_TAGS)
            parser.feed(html)
            parser.close()

            errors.extend(self._structure_errors(parser, context))
            errors.extend(self._semantic_errors(parser, context))
            errors.extend(self._asset_errors(parser, context, path))
            errors.extend(self._json_ld_errors(html, context))
            errors.extend(self._canonical_errors(parser, context))

        return errors

    def _page_context(self, html, path, output_dir):
        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.DOTALL | re.IGNORECASE)
        url_match = re.search(
            r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )

        return {
            "title": self._strip_tags(title_match.group(1)).strip() if title_match else "",
            "url": url_match.group(1) if url_match else "",
            "path": str(path),
            "relative_path": str(path.relative_to(output_dir)) if path.is_relative_to(output_dir) else str(path),
        }

    def _structure_errors(self, parser, context):
        return [
            self._error(context, "HTML_STRUCTURE", message, line, column)
            for line, column, message in parser.errors
        ]

    def _semantic_errors(self, parser, context):
        errors = []

        if parser.tag_counts.get("head", 0) != 1:
            errors.append(self._error(context, "DUPLICATE_HEAD", "HTML must contain exactly one head tag."))

        if parser.tag_counts.get("body", 0) != 1:
            errors.append(self._error(context, "DUPLICATE_BODY", "HTML must contain exactly one body tag."))

        if parser.tag_counts.get("h1", 0) != 1:
            errors.append(self._error(context, "H1_COUNT", "HTML must contain exactly one h1 tag."))

        for tag, line, column, attrs, ancestors in parser.start_tags:
            if tag == "meta" and "head" not in ancestors:
                errors.append(self._error(context, "META_OUTSIDE_HEAD", "Meta tag must be inside head.", line, column))

            if tag == "section" and "body" not in ancestors:
                errors.append(self._error(context, "SECTION_OUTSIDE_BODY", "Section tag must be inside body.", line, column))

            if tag == "img" and not self._attr(attrs, "alt").strip():
                errors.append(self._error(context, "EMPTY_ALT", "Image alt attribute must not be empty.", line, column))

            if tag in self.HEADING_TAGS and not self._valid_heading(tag, ancestors):
                errors.append(self._error(context, "HEADING_NESTING", f"{tag} appears inside another heading.", line, column))

        return errors

    def _asset_errors(self, parser, context, path):
        errors = []
        base_dir = path.parent

        for tag, line, column, attrs, _ancestors in parser.start_tags:
            if tag == "img":
                src = self._attr(attrs, "src")
                if src and not self._asset_exists(base_dir, src):
                    errors.append(self._error(context, "MISSING_IMAGE", f"Image file does not exist: {src}", line, column))

            if tag == "link" and self._attr(attrs, "rel").lower() == "stylesheet":
                href = self._attr(attrs, "href")
                if href and not self._asset_exists(base_dir, href):
                    errors.append(self._error(context, "MISSING_CSS", f"CSS file does not exist: {href}", line, column))

            if tag == "script" and self._attr(attrs, "src"):
                src = self._attr(attrs, "src")
                if not self._asset_exists(base_dir, src):
                    errors.append(self._error(context, "MISSING_JS", f"JS file does not exist: {src}", line, column))

        return errors

    def _json_ld_errors(self, html, context):
        errors = []
        for match in re.finditer(
            r'<script\s+type=["\']application/ld\+json["\']>\s*(.*?)\s*</script>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            try:
                json.loads(match.group(1))
            except json.JSONDecodeError as error:
                line = html[: match.start(1)].count("\n") + error.lineno
                errors.append(
                    self._error(
                        context,
                        "JSON_LD",
                        f"Invalid JSON-LD: {error.msg}",
                        line,
                        error.colno,
                    )
                )

        return errors

    def _canonical_errors(self, parser, context):
        canonicals = []
        for tag, line, column, attrs, ancestors in parser.start_tags:
            if tag != "link":
                continue

            if self._attr(attrs, "rel").lower() != "canonical":
                continue

            href = self._attr(attrs, "href")
            canonicals.append((href, line, column, ancestors))

        if len(canonicals) != 1:
            return [
                self._error(
                    context,
                    "CANONICAL",
                    "HTML must contain exactly one canonical link.",
                )
            ]

        href, line, column, ancestors = canonicals[0]
        if "head" not in ancestors:
            return [self._error(context, "CANONICAL", "Canonical link must be inside head.", line, column)]

        if not href.startswith(("http://", "https://")):
            return [self._error(context, "CANONICAL", "Canonical URL must be absolute.", line, column)]

        return []

    def _error(self, context, error_type, message, line=None, column=None):
        return HtmlValidationError(
            title=context["title"],
            url=context["url"],
            path=context["path"],
            error_type=error_type,
            message=message,
            line=line,
            column=column,
        )

    def _asset_exists(self, base_dir, value):
        if not value or value.startswith(("http://", "https://", "data:", "#")):
            return True

        return (base_dir / value).resolve().exists()

    def _attr(self, attrs, name):
        for key, value in attrs:
            if key == name:
                return value or ""
        return ""

    def _valid_heading(self, tag, ancestors):
        return not any(ancestor in self.HEADING_TAGS for ancestor in ancestors)

    def _strip_tags(self, value):
        return re.sub(r"<[^>]*>", "", value)


class _StructureParser(HTMLParser):
    def __init__(self, void_tags):
        super().__init__(convert_charrefs=True)
        self.void_tags = void_tags
        self.stack = []
        self.errors = []
        self.tag_counts = {}
        self.start_tags = []

    def handle_starttag(self, tag, attrs):
        line, column = self.getpos()
        self.tag_counts[tag] = self.tag_counts.get(tag, 0) + 1
        self.start_tags.append((tag, line, column, attrs, [item[0] for item in self.stack]))

        if tag not in self.void_tags:
            self.stack.append((tag, line, column))

    def handle_endtag(self, tag):
        line, column = self.getpos()
        if tag in self.void_tags:
            return

        if not self.stack:
            self.errors.append((line, column, f"Unexpected closing tag: {tag}"))
            return

        current, _start_line, _start_column = self.stack[-1]
        if current != tag:
            self.errors.append((line, column, f"Unexpected closing tag: {tag}. Expected: {current}"))
            return

        self.stack.pop()

    def close(self):
        super().close()
        for tag, line, column in self.stack:
            self.errors.append((line, column, f"Unclosed tag: {tag}"))
