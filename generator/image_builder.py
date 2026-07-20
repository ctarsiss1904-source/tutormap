from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import shutil
import struct
import sys

from config import OUTPUT_DIR, SITE_NAME
from generator.page_type import PageType

Image = None
PIL_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_IMAGE_ROOT = PROJECT_ROOT / "assets" / "source"
IMAGE_ROOT = SOURCE_IMAGE_ROOT / "seo"
HERO_IMAGE_PATH = SOURCE_IMAGE_ROOT / "content" / "body.png"
HOME_HERO_IMAGE_PATH = SOURCE_IMAGE_ROOT / "home" / "hero.png"
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
        build_version=None,
    ):
        self.image_root = Path(image_root).resolve()
        self.hero_image_path = Path(hero_image_path).resolve()
        self.home_hero_image_path = Path(home_hero_image_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.build_version = build_version
        self.home_asset = None
        self.hero_asset = None
        self.seo_assets = []

    def set_build_version(self, build_version):
        self.build_version = build_version

    def build(self, pages):
        self._validate_source_assets()
        self._clear_image_outputs()
        self._load_assets_once()

        for page in self._flatten(pages):
            if self._is_main_page(page):
                page.hero_image = self._page_image(page, self.home_asset)
                page.seo_image = None
                continue

            page.hero_image = self._page_image(page, self.hero_asset)
            page.seo_image = self._page_image(
                page,
                self._select_seo_asset(page),
            )

    def _validate_source_assets(self):
        global Image, PIL_IMPORT_ERROR

        print("[Pillow Debug] entering _validate_source_assets")
        print(f"[Pillow Debug] Python version: {sys.version}")
        print(f"[Pillow Debug] sys.executable: {sys.executable}")
        print(f"[Pillow Debug] cwd: {os.getcwd()}")
        print(f"[Pillow Debug] sys.path: {sys.path}")

        try:
            import PIL

            pil_file = getattr(PIL, "__file__", None)
            pil_path = list(getattr(PIL, "__path__", []))
            pil_package_dir = Path(pil_file).parent if pil_file else None

            print(f"[Pillow Debug] PIL.__file__: {pil_file}")
            print(f"[Pillow Debug] PIL.__path__: {pil_path}")
            print(f"[Pillow Debug] PIL package dir: {pil_package_dir}")
            if pil_package_dir and pil_package_dir.exists():
                package_contents = sorted(path.name for path in pil_package_dir.iterdir())
                print(f"[Pillow Debug] package contents: {package_contents}")
                print(f"[Pillow Debug] _imaging.so exists: {(pil_package_dir / '_imaging.so').exists()}")
                print(f"[Pillow Debug] _imaging.pyd exists: {(pil_package_dir / '_imaging.pyd').exists()}")
            else:
                print("[Pillow Debug] package contents: PACKAGE DIR NOT FOUND")
                print("[Pillow Debug] _imaging.so exists: False")
                print("[Pillow Debug] _imaging.pyd exists: False")
        except Exception as pil_error:
            print(f"[Pillow Debug] PIL import: {repr(pil_error)}")

        try:
            from PIL import _imaging
            print("[Pillow Debug] _imaging import: SUCCESS")
        except Exception as imaging_error:
            print(f"[Pillow Debug] _imaging import: {repr(imaging_error)}")

        try:
            from PIL import Image as pillow_image
            Image = pillow_image
            PIL_IMPORT_ERROR = None
            print("[Pillow Debug] Image import: SUCCESS")
        except ImportError as image_error:
            Image = None
            PIL_IMPORT_ERROR = image_error
            print(f"[Pillow Debug] Image import: {repr(image_error)}")
            print(f"[Pillow Debug] Original Exception: {repr(image_error)}")

        if Image is None:
            raise RuntimeError(
                "Build Failed: Pillow is required to generate images. "
                f"Original import error: {PIL_IMPORT_ERROR}"
            )

        self._validate_source_image(self.home_hero_image_path, "Hero image")
        self._validate_source_image(self.hero_image_path, "Content body image")

        if not self._seo_source_paths():
            raise RuntimeError(
                f"Build Failed: SEO image source directory has no images: {self.image_root}"
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
            self.seo_assets.append(asset)

    def _build_home_asset(self):
        self._validate_source_image(self.home_hero_image_path, "Hero image")

        output_path = self.output_dir / "assets" / "images" / "home" / "home-hero.webp"
        public_path = "assets/images/home/home-hero.webp"

        with Image.open(self.home_hero_image_path) as image:
            hero = image.copy()
            if hero.mode not in {"RGB", "RGBA"}:
                hero = hero.convert("RGB")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            hero.save(output_path, "WEBP", quality=84, method=6)

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
        self._validate_source_image(self.hero_image_path, "Content body image")

        original_output = (
            self.output_dir
            / "assets"
            / "images"
            / "original"
            / f"body{self.hero_image_path.suffix.lower()}"
        )
        original_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.hero_image_path, original_output)

        display_output = self.output_dir / "assets" / "images" / "content" / "body.webp"
        display_public = "assets/images/content/body.webp"

        with Image.open(self.hero_image_path) as image:
            display_image = image.copy()
            if display_image.mode not in {"RGB", "RGBA"}:
                display_image = display_image.convert("RGB")

            display_output.parent.mkdir(parents=True, exist_ok=True)
            display_image.save(display_output, "WEBP", quality=84, method=6)

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

    def _clear_image_outputs(self):
        image_dir = self.output_dir / "assets" / "images"
        for name in ("home", "content", "original", "seo"):
            target = image_dir / name
            if target.exists() and target.is_dir():
                shutil.rmtree(target)

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
        self._validate_source_image(source_path, "SEO image")

        width, height = self._image_size(source_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, output_path)
        return ImageAsset(
            source_path=source_path,
            output_path=output_path,
            public_path=public_path,
            width=width,
            height=height,
            variants=self._create_webp_variants(
                source_path,
                output_path,
                public_path,
                width,
                height,
            ),
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

        return variants

    def _validate_source_image(self, path, label):
        path = Path(path)
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"Build Failed: {label} source image is missing: {path}")

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise RuntimeError(f"Build Failed: {label} has unsupported extension: {path}")

    def _relative_src(self, page, public_path):
        depth = len([part for part in page.url.strip("/").split("/") if part])
        prefix = "../" * depth
        src = f"{prefix}{public_path}"
        if not self.build_version:
            return src

        separator = "&" if "?" in src else "?"
        return f"{src}{separator}v={self.build_version}"

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
