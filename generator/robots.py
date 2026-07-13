from pathlib import Path

from config import BASE_URL, OUTPUT_DIR


class RobotsBuilder:
    def __init__(self, output_dir=OUTPUT_DIR):
        self.output_dir = Path(output_dir).resolve()

    def build(self):
        sitemap_url = f"{BASE_URL.rstrip('/')}/sitemap.xml"
        content = "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                f"Sitemap: {sitemap_url}",
                "",
            ]
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / "robots.txt"
        path.write_text(content, encoding="utf-8")
        return path
