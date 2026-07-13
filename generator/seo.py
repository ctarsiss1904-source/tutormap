from dataclasses import dataclass

from config import BASE_URL, IMAGE_URL, SITE_NAME
from generator.page_type import PageType


@dataclass
class SEOMeta:
    title: str
    description: str
    canonical: str
    og_title: str
    og_description: str
    og_url: str
    og_type: str
    og_site_name: str
    og_locale: str
    og_image: str
    twitter_card: str
    twitter_title: str
    twitter_description: str
    twitter_image: str
    robots: str


class SEOBuilder:
    def build(self, page):
        if not hasattr(page, "title"):
            return None

        title = self.title(page)
        description = self.description(page)
        canonical = self.canonical(page)

        page.meta = SEOMeta(
            title=title,
            description=description,
            canonical=canonical,
            og_title=title,
            og_description=description,
            og_url=canonical,
            og_type="website",
            og_site_name=SITE_NAME,
            og_locale="ko_KR",
            og_image=IMAGE_URL,
            twitter_card="summary_large_image",
            twitter_title=title,
            twitter_description=description,
            twitter_image=IMAGE_URL,
            robots="index, follow",
        )

        for child in page.children:
            self.build(child)

        return page.meta

    def title(self, page):
        if page.page_type == PageType.NATION:
            return SITE_NAME

        return page.title

    def description(self, page):
        if page.page_type == PageType.NATION:
            return "TutorMap은 전국 지역 기반 과외 정보를 쉽고 편리하게 찾을 수 있도록 구성된 교육 정보 플랫폼입니다."

        return f"{page.title} 전문 과외 정보"

    def canonical(self, page):
        if not page.url:
            return ""

        base_url = BASE_URL.rstrip("/")
        if not base_url:
            return page.url

        return f"{base_url}{page.url}"
