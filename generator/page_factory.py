from generator.page_definition import create_default_registry
from generator.page import Page
from generator.page_type import PageType


class PageFactory:
    def __init__(self, page_registry=None):
        self.page_registry = page_registry or create_default_registry()

    def create(self, context):
        region = context.region
        keyword = context.keyword
        parent = getattr(context, "parent", None)
        page_definition = self.page_registry.get(keyword.page_type)

        if not page_definition:
            return None

        region_names = {
            PageType.PROVINCE: region.province,
            PageType.CITY: region.city,
            PageType.DISTRICT: region.district,
            PageType.DONG: region.dong,
        }
        region_name = region_names.get(page_definition.page_type, region.dong)
        title = f"{region_name}{keyword.suffix}"

        return Page(
            id=title,
            title=title,
            url_segment=title,
            region=region,
            keyword=keyword,
            page_type=page_definition.page_type,
            parent=parent,
            url=None,
            template=None,
            meta=None,
            schema=None,
            is_hub=True,
        )

    def create_children(self, page):
        pass
