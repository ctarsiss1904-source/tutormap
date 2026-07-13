import json
from pathlib import Path

from config import OUTPUT_DIR, SITE_NAME


class ManifestBuilder:
    def __init__(self, output_dir=OUTPUT_DIR):
        self.output_dir = Path(output_dir).resolve()

    def build(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_icons()
        return self._write_manifest()

    def _write_manifest(self):
        manifest = {
            "name": SITE_NAME,
            "short_name": SITE_NAME,
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#123c7c",
            "lang": "ko",
            "icons": [
                {
                    "src": "/assets/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                },
                {
                    "src": "/assets/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                },
            ],
        }
        path = self.output_dir / "manifest.webmanifest"
        path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def _write_icons(self):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            self._write_placeholder_icon("favicon.ico")
            self._write_placeholder_icon("apple-touch-icon.png")
            return

        icon_dir = self.output_dir / "assets" / "icons"
        icon_dir.mkdir(parents=True, exist_ok=True)

        for size in (192, 512):
            image = self._create_icon_image(size, Image, ImageDraw, ImageFont)
            image.save(icon_dir / f"icon-{size}.png", "PNG")

        apple_icon = self._create_icon_image(180, Image, ImageDraw, ImageFont)
        apple_icon.save(self.output_dir / "apple-touch-icon.png", "PNG")

        favicon = self._create_icon_image(64, Image, ImageDraw, ImageFont)
        favicon.save(self.output_dir / "favicon.ico", sizes=[(16, 16), (32, 32), (64, 64)])

    def _create_icon_image(self, size, image_module, draw_module, font_module):
        image = image_module.new("RGB", (size, size), "#123c7c")
        draw = draw_module.Draw(image)
        text = "T"

        try:
            font = font_module.truetype("arial.ttf", int(size * 0.62))
        except OSError:
            font = font_module.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        x = (size - (bbox[2] - bbox[0])) / 2
        y = (size - (bbox[3] - bbox[1])) / 2 - size * 0.04
        draw.text((x, y), text, fill="#ffffff", font=font)
        return image

    def _write_placeholder_icon(self, filename):
        path = self.output_dir / filename
        path.write_bytes(b"")
