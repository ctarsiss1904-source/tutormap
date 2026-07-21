from hashlib import sha256

from generator.page_type import PageType


class InternalLinkBuilder:
    RECOMMENDATION_TITLES = [
        "함께 많이 찾는 페이지",
        "이 지역에서 자주 보는 정보",
        "비슷한 학습 정보",
        "추천 학습 페이지",
        "관련 과외 정보",
        "인근 지역 정보",
        "학년별 추천 정보",
        "과목별 추천 정보",
        "학교별 참고 페이지",
        "다음에 볼 만한 페이지",
        "연결해서 보면 좋은 정보",
        "학습 계획에 도움 되는 페이지",
        "주변 지역 과외 정보",
        "같이 비교하면 좋은 페이지",
        "맞춤 학습 추천 링크",
    ]

    def build(self, page):
        if not hasattr(page, "parent"):
            return {}

        all_pages = self._flatten(page)
        self._build_page_links(page, all_pages)
        return page.internal_links

    def _build_page_links(self, page, all_pages):
        page.internal_links = {
            "parent": self._parent_link(page),
            "children": self._child_links(page),
            "siblings": self._sibling_links(page),
            "related": self._related_links(page),
            "recommended": self._recommended_links(page, all_pages),
        }
        page.recommendation_title = self._recommendation_title(page)

        for child in page.children:
            self._build_page_links(child, all_pages)

    def _parent_link(self, page):
        if page.parent is None:
            return None

        return self._link(page.parent)

    def _child_links(self, page):
        return [self._link(child) for child in page.children]

    def _sibling_links(self, page):
        if page.parent is None:
            return []

        return [
            self._link(sibling)
            for sibling in page.parent.children
            if sibling is not page
        ]

    def _related_links(self, page):
        links = []

        if page.parent is not None:
            links.append(self._link(page.parent))

        links.extend(self._sibling_links(page)[:5])
        links.extend(self._child_links(page)[:5])
        return self._unique_links(links)

    def _recommended_links(self, page, all_pages):
        candidates = []
        for candidate in all_pages:
            if candidate is page or not getattr(candidate, "url", None):
                continue

            score = self._recommendation_score(page, candidate)
            if score <= 0:
                continue

            candidates.append((score, self._stable_order(page, candidate), candidate))

        candidates.sort(key=lambda item: (-item[0], item[1]))
        links = [self._link(candidate) for _, _, candidate in candidates]
        links = self._unique_links(links)
        if len(links) < 6:
            links.extend(self._fallback_links(page, all_pages, seen={link["url"] for link in links}))
            links = self._unique_links(links)

        return links[:12]

    def _recommendation_score(self, page, candidate):
        if page.page_type == PageType.DONG:
            return self._dong_score(page, candidate)
        if page.page_type == PageType.SCHOOL:
            return self._school_score(page, candidate)
        if page.page_type == PageType.SUBJECT:
            return self._subject_score(page, candidate)
        if page.page_type == PageType.GRADE:
            return self._grade_score(page, candidate)
        if page.page_type in {PageType.PROVINCE, PageType.CITY, PageType.DISTRICT}:
            return self._region_score(page, candidate)

        return self._default_score(page, candidate)

    def _dong_score(self, page, candidate):
        score = self._relationship_score(page, candidate)
        if candidate.page_type == PageType.DONG and self._same_region(page, candidate, "district"):
            score += 120
        elif candidate.page_type == PageType.DONG and self._same_region(page, candidate, "city"):
            score += 90
        elif candidate.page_type in {PageType.SUBJECT, PageType.GRADE, PageType.SCHOOL} and self._is_descendant(candidate, page):
            score += 80
        elif candidate.page_type in {PageType.CITY, PageType.DISTRICT} and self._is_ancestor(candidate, page):
            score += 70
        return score

    def _school_score(self, page, candidate):
        score = self._relationship_score(page, candidate)
        if candidate.page_type == PageType.SCHOOL and self._same_region(page, candidate, "dong"):
            score += 120
        elif candidate.page_type == PageType.GRADE and self._shares_ancestor_type(page, candidate, PageType.SUBJECT):
            score += 100
        elif candidate.page_type == PageType.SUBJECT and self._same_region(page, candidate, "dong"):
            score += 90
        elif candidate.page_type == PageType.SCHOOL and self._same_region(page, candidate, "city"):
            score += 70
        return score

    def _subject_score(self, page, candidate):
        score = self._relationship_score(page, candidate)
        if candidate.page_type == PageType.SUBJECT and self._same_region(page, candidate, "dong"):
            score += 120
        elif candidate.page_type == PageType.GRADE and self._is_descendant(candidate, page):
            score += 100
        elif candidate.page_type == PageType.SCHOOL and self._is_descendant(candidate, page):
            score += 80
        elif candidate.page_type == PageType.DONG and self._same_region(page, candidate, "city"):
            score += 60
        return score

    def _grade_score(self, page, candidate):
        score = self._relationship_score(page, candidate)
        if candidate.page_type == PageType.GRADE and self._shares_ancestor_type(page, candidate, PageType.SUBJECT):
            score += 120
        elif candidate.page_type == PageType.SCHOOL and self._is_descendant(candidate, page):
            score += 100
        elif candidate.page_type == PageType.SUBJECT and self._is_ancestor(candidate, page):
            score += 90
        elif candidate.page_type == PageType.GRADE and self._same_region(page, candidate, "city"):
            score += 70
        return score

    def _region_score(self, page, candidate):
        score = self._relationship_score(page, candidate)
        if candidate.page_type == page.page_type and self._same_region(page, candidate, "province"):
            score += 100
        elif self._is_descendant(candidate, page):
            score += 90
        elif candidate.page_type in {PageType.PROVINCE, PageType.CITY, PageType.DISTRICT, PageType.DONG} and self._same_region(page, candidate, "city"):
            score += 70
        return score

    def _default_score(self, page, candidate):
        return self._relationship_score(page, candidate)

    def _relationship_score(self, page, candidate):
        if candidate.parent is page:
            return 80
        if page.parent is candidate:
            return 70
        if page.parent is not None and candidate.parent is page.parent:
            return 65
        if self._is_descendant(candidate, page):
            return 55
        if self._is_ancestor(candidate, page):
            return 50
        return 0

    def _fallback_links(self, page, all_pages, seen):
        candidates = [
            candidate
            for candidate in all_pages
            if candidate is not page
            and getattr(candidate, "url", None)
            and candidate.url not in seen
            and candidate.page_type != PageType.NATION
        ]
        candidates.sort(key=lambda candidate: self._stable_order(page, candidate))
        return [self._link(candidate) for candidate in candidates[:12]]

    def _recommendation_title(self, page):
        index = self._stable_index(page.url or page.title, len(self.RECOMMENDATION_TITLES))
        return self.RECOMMENDATION_TITLES[index]

    def _same_region(self, page, candidate, depth):
        attrs_by_depth = {
            "province": ("province",),
            "city": ("province", "city"),
            "district": ("province", "city", "district"),
            "dong": ("province", "city", "district", "dong"),
        }
        attrs = attrs_by_depth[depth]
        return all(
            self._region_value(page, attr)
            and self._region_value(page, attr) == self._region_value(candidate, attr)
            for attr in attrs
        )

    def _shares_ancestor_type(self, page, candidate, page_type):
        return self._ancestor_of_type(page, page_type) is self._ancestor_of_type(candidate, page_type)

    def _ancestor_of_type(self, page, page_type):
        current = page
        while current is not None:
            if current.page_type == page_type:
                return current
            current = current.parent
        return None

    def _is_ancestor(self, candidate, page):
        current = page.parent
        while current is not None:
            if current is candidate:
                return True
            current = current.parent
        return False

    def _is_descendant(self, candidate, page):
        return self._is_ancestor(page, candidate)

    def _region_value(self, page, attr):
        return getattr(getattr(page, "region", None), attr, "")

    def _stable_order(self, page, candidate):
        key = f"{page.url}|{candidate.url}|recommendation"
        digest = sha256(key.encode("utf-8")).hexdigest()
        return int(digest[:16], 16)

    def _stable_index(self, value, length):
        digest = sha256(str(value).encode("utf-8")).hexdigest()
        return int(digest[:12], 16) % length

    def _flatten(self, page):
        pages = []
        self._walk(page, pages)
        return pages

    def _walk(self, page, pages):
        pages.append(page)
        for child in getattr(page, "children", []):
            self._walk(child, pages)

    def _unique_links(self, links):
        unique_links = []
        seen = set()
        for link in links:
            if not link:
                continue

            url = link["url"]
            if url in seen:
                continue

            seen.add(url)
            unique_links.append(link)

        return unique_links

    def _link(self, page):
        return {
            "title": page.title,
            "url": page.url,
        }
