from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil
import struct

from config import OUTPUT_DIR, SITE_NAME
from generator.page_type import PageType

try:
    from PIL import Image
except ImportError:
    Image = None


IMAGE_ROOT = Path(r"C:\Users\lovel\OneDrive\桌面\이미지")
HERO_IMAGE_PATH = IMAGE_ROOT / "본문이미지" / "본문.png"
HOME_HERO_IMAGE_PATH = Path(r"C:\Users\lovel\Downloads\ChatGPT Image 2026년 7월 10일 오후 02_51_01.png")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
RESPONSIVE_WIDTHS = (480, 768, 960, 1280)


@dataclass
class PageImage:
    src: str
    srcset: str
    sizes: str
    width: int
    height: int
    alt: str


@dataclass
class ImageVariant:
    public_path: str
    width: int
    height: int


@dataclass
class ImageAsset:
    source_path: Path
    output_path: Path
    public_path: str
    width: int
    height: int
    variants: list[ImageVariant]


class ImageBuilder:
    def __init__(
        self,
        image_root=IMAGE_ROOT,
        hero_image_path=HERO_IMAGE_PATH,
        home_hero_image_path=HOME_HERO_IMAGE_PATH,
        output_dir=OUTPUT_DIR,
    ):
        self.image_root = Path(image_root).resolve()
        self.hero_image_path = Path(hero_image_path).resolve()
        self.home_hero_image_path = Path(home_hero_image_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.home_asset = None
        self.hero_asset = None
        self.seo_assets = []

    def build(self, pages):
        self._load_assets_once()

        for page in self._flatten(pages):
            if self._is_main_page(page):
                page.hero_image = self._page_image(page, self.home_asset) if self.home_asset else None
                page.seo_image = None
                continue

            if self.hero_asset:
                page.hero_image = self._page_image(page, self.hero_asset)

            if self.seo_assets:
                page.seo_image = self._page_image(
                    page,
                    self._select_seo_asset(page),
                )

    def _load_assets_once(self):
        self.home_asset = self._build_home_asset()
        self.hero_asset = self._build_hero_asset()

        self.seo_assets = []
        for index, source_path in enumerate(self._seo_source_paths(), start=1):
            suffix = source_path.suffix.lower()
            output_name = f"seo-{index:03d}{suffix}"
            asset = self._copy_asset(
                source_path,
                self.output_dir / "assets" / "images" / "seo" / output_name,
                f"assets/images/seo/{output_name}",
            )
            if asset:
                self.seo_assets.append(asset)

    def _build_home_asset(self):
        if (
            Image is None
            or not self.home_hero_image_path.exists()
            or self.home_hero_image_path.suffix.lower() not in IMAGE_EXTENSIONS
        ):
            return None

        output_path = self.output_dir / "assets" / "images" / "home" / "home-hero.webp"
        public_path = "assets/images/home/home-hero.webp"

        try:
            with Image.open(self.home_hero_image_path) as image:
                hero = image.copy()
                if hero.mode not in {"RGB", "RGBA"}:
                    hero = hero.convert("RGB")

                output_path.parent.mkdir(parents=True, exist_ok=True)
                hero.save(output_path, "WEBP", quality=84, method=6)
        except OSError:
            return None

        width, height = self._image_size(output_path)
        return ImageAsset(
            source_path=self.home_hero_image_path,
            output_path=output_path,
            public_path=public_path,
            width=width,
            height=height,
            variants=self._create_webp_variants(
                output_path,
                output_path,
                public_path,
                width,
                height,
            ),
        )

    def _build_hero_asset(self):
        if (
            not self.hero_image_path.exists()
            or self.hero_image_path.suffix.lower() not in IMAGE_EXTENSIONS
        ):
            return None

        self._clear_hero_outputs()

        original_output = (
            self.output_dir
            / "assets"
            / "images"
            / "original"
            / f"body{self.hero_image_path.suffix.lower()}"
        )
        original_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.hero_image_path, original_output)

        if Image is None:
            return self._copy_asset(
                self.hero_image_path,
                self.output_dir / "assets" / "images" / "content" / "body-display.png",
                "assets/images/content/body-display.png",
            )

        display_output = self.output_dir / "assets" / "images" / "content" / "body.webp"
        display_public = "assets/images/content/body.webp"

        try:
            with Image.open(self.hero_image_path) as image:
                display_image = image.copy()
                if display_image.mode not in {"RGB", "RGBA"}:
                    display_image = display_image.convert("RGB")

                display_output.parent.mkdir(parents=True, exist_ok=True)
                display_image.save(display_output, "WEBP", quality=84, method=6)
        except OSError:
            return None

        width, height = self._image_size(display_output)
        return ImageAsset(
            source_path=self.hero_image_path,
            output_path=display_output,
            public_path=display_public,
            width=width,
            height=height,
            variants=self._create_webp_variants(
                display_output,
                display_output,
                display_public,
                width,
                height,
            ),
        )

    def _clear_hero_outputs(self):
        content_dir = self.output_dir / "assets" / "images" / "content"
        if content_dir.exists():
            for path in content_dir.glob("body*"):
                if path.is_file():
                    path.unlink()

    def _seo_source_paths(self):
        if not self.image_root.exists():
            return []

        return sorted(
            [
                path
                for path in self.image_root.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ],
            key=lambda path: path.name,
        )

    def _copy_asset(self, source_path, output_path, public_path):
        if not source_path.exists() or source_path.suffix.lower() not in IMAGE_EXTENSIONS:
            return None

        width, height = self._image_size(source_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, output_path)
        return ImageAsset(
            source_path=source_path,
            output_path=output_path,
            public_path=public_path,
            width=width,
            height=height,
            variants=self._create_webp_variants(source_path, output_path, public_path, width, height),
        )

    def _select_seo_asset(self, page):
        digest = sha256(page.title.encode("utf-8")).hexdigest()
        index = int(digest, 16) % len(self.seo_assets)
        return self.seo_assets[index]

    def _page_image(self, page, asset):
        display_width = min(asset.width, 960)
        src_asset = asset.variants[-1].public_path if asset.variants else asset.public_path
        srcset_items = asset.variants or [
            ImageVariant(
                public_path=asset.public_path,
                width=asset.width,
                height=asset.height,
            )
        ]

        return PageImage(
            src=self._relative_src(page, src_asset),
            srcset=", ".join(
                f"{self._relative_src(page, item.public_path)} {item.width}w"
                for item in srcset_items
            ),
            sizes=f"(max-width: 768px) 100vw, {display_width}px",
            width=asset.width,
            height=asset.height,
            alt=SITE_NAME if self._is_main_page(page) else page.title,
        )

    def _create_webp_variants(self, source_path, output_path, public_path, width, height):
        if Image is None or not width or not height:
            return []

        widths = [item for item in RESPONSIVE_WIDTHS if item <= width]
        if not widths:
            widths = [width]

        variants = []
        try:
            with Image.open(source_path) as image:
                for target_width in widths:
                    target_height = max(1, round(height * (target_width / width)))
                    variant_output = output_path.with_name(
                        f"{output_path.stem}-{target_width}.webp"
                    )
                    variant_public = str(
                        Path(public_path).with_name(f"{Path(public_path).stem}-{target_width}.webp")
                    ).replace("\\", "/")

                    resized = image
                    if image.width != target_width:
                        resized = image.resize(
                            (target_width, target_height),
                            Image.Resampling.LANCZOS,
                        )

                    if resized.mode not in {"RGB", "RGBA"}:
                        resized = resized.convert("RGB")

                    variant_output.parent.mkdir(parents=True, exist_ok=True)
                    resized.save(variant_output, "WEBP", quality=82, method=6)
                    variants.append(
                        ImageVariant(
                            public_path=variant_public,
                            width=target_width,
                            height=target_height,
                        )
                    )
        except OSError:
            return []

        return variants

    def _relative_src(self, page, public_path):
        depth = len([part for part in page.url.strip("/").split("/") if part])
        prefix = "../" * depth
        return f"{prefix}{public_path}"

    def _is_main_page(self, page):
        return page.page_type == PageType.NATION or page.title == "전국과외"

    def _flatten(self, pages):
        roots = pages if isinstance(pages, list) else [pages]
        flattened = []
        for page in roots:
            self._walk(page, flattened)
        return flattened

    def _walk(self, page, flattened):
        if page is None:
            return

        flattened.append(page)
        for child in getattr(page, "children", []):
            self._walk(child, flattened)

    def _image_size(self, path):
        suffix = path.suffix.lower()
        with path.open("rb") as file:
            if suffix == ".png":
                return self._png_size(file)
            if suffix in {".jpg", ".jpeg"}:
                return self._jpeg_size(file)
            if suffix == ".gif":
                return self._gif_size(file)
            if suffix == ".webp":
                return self._webp_size(file)

        return 0, 0

    def _png_size(self, file):
        file.seek(16)
        width, height = struct.unpack(">II", file.read(8))
        return width, height

    def _gif_size(self, file):
        file.seek(6)
        width, height = struct.unpack("<HH", file.read(4))
        return width, height

    def _jpeg_size(self, file):
        file.seek(2)
        while True:
            marker_start = file.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue

            marker = file.read(1)
            if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"}:
                file.read(3)
                height, width = struct.unpack(">HH", file.read(4))
                return width, height

            size_bytes = file.read(2)
            if len(size_bytes) != 2:
                break
            size = struct.unpack(">H", size_bytes)[0]
            file.seek(size - 2, 1)

        return 0, 0

    def _webp_size(self, file):
        data = file.read(32)
        if data[12:16] == b"VP8 ":
            width, height = struct.unpack("<HH", data[26:30])
            return width & 0x3FFF, height & 0x3FFF
        if data[12:16] == b"VP8X":
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
            return width, height
        return 0, 0
