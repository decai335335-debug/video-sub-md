"""Standalone Coursera course subtitle downloader.

This module uses Coursera's course material APIs to list lectures and fetch SRT
subtitle assets for the account that is currently available to the HTTP session.
It does not bypass login or paid-course permissions.
"""

from __future__ import annotations

import json
import re
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests

from config import FILENAME_BAD_CHARS
from core.naming import add_date_prefix
from core.coursera.extractor import build_lecture_url, extract_collection_slug, extract_course_slug
from core.coursera.formatter import course_to_markdown, parse_srt
from core.coursera.models import CourseraCourse, CourseraDownloadResult, CourseraLecture


COURSERA_ORIGIN = "https://www.coursera.org"
COURSERA_API = "https://api.coursera.org/api"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": COURSERA_ORIGIN,
}


class CourseraDownloader:
    def __init__(
        self,
        cookie: str = "",
        cookies_file: str | Path | None = None,
        cookies_from_browser: str = "",
        timeout: int = 30,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        if cookie:
            self.session.headers["Cookie"] = cookie
        if cookies_file:
            self._load_cookies_file(Path(cookies_file))
        if cookies_from_browser:
            self._load_browser_cookies(cookies_from_browser)

    def _load_cookies_file(self, path: Path) -> None:
        jar = MozillaCookieJar(str(path))
        jar.load(ignore_discard=True, ignore_expires=True)
        self.session.cookies.update(jar)

    def _load_browser_cookies(self, browser: str) -> None:
        try:
            import browser_cookie3
        except ImportError as exc:
            raise RuntimeError(
                "browser-cookie3 is not installed. Run: pip install browser-cookie3"
            ) from exc

        browser = browser.lower()
        loaders = {
            "chrome": browser_cookie3.chrome,
            "edge": browser_cookie3.edge,
            "firefox": browser_cookie3.firefox,
            "brave": browser_cookie3.brave,
        }
        loader = loaders.get(browser)
        if not loader:
            raise ValueError(f"Unsupported browser for cookies: {browser}")
        self.session.cookies.update(loader(domain_name=".coursera.org"))

    def expand_to_course_slugs(self, url_or_slug: str) -> list[str]:
        """Resolve a Coursera course/specialization/certificate URL to course slugs."""
        value = (url_or_slug or "").strip()
        if not value:
            return []

        parsed = urlparse(value if "://" in value else f"https://www.coursera.org/learn/{value}")
        if parsed.path.startswith("/search"):
            query = parse_qs(parsed.query).get("query") or parse_qs(parsed.query).get("q")
            search_query = query[0] if query else ""
            if search_query:
                return self.search_course_slugs(search_query, limit=5)
            return self.course_slugs_from_search_page(value, limit=20)

        if "://" not in value and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
            return self.search_course_slugs(value, limit=1)

        try:
            return [extract_course_slug(value)]
        except ValueError:
            pass

        kind, slug = extract_collection_slug(value)
        try:
            data = self._get_json(
                f"{COURSERA_API}/onDemandSpecializations.v1/",
                params={"q": "slug", "slug": slug, "fields": "name,slug,courseIds"},
            )
        except Exception:
            return self.search_course_slugs(slug.replace("-", " "), limit=5)
        elements = data.get("elements") or []
        if not elements:
            raise RuntimeError(f"Coursera {kind} not found or not accessible: {slug}")

        course_ids = elements[0].get("courseIds") or []
        course_slugs = []
        for course_id in course_ids:
            try:
                course_slug = self._get_course_slug_by_id(course_id)
            except Exception:
                continue
            if course_slug:
                course_slugs.append(course_slug)
        course_slugs = self.filter_accessible_slugs(course_slugs)
        return course_slugs or self.search_course_slugs(slug.replace("-", " "), limit=5)

    def search_course_slugs(self, query: str, limit: int = 5) -> list[str]:
        """Search Coursera's public search page and return likely course slugs."""
        cleaned = clean_coursera_query(query)
        if not cleaned:
            raise ValueError(
                "Coursera search pages need a query. Paste a course URL or a searchable course title."
            )

        html = self._get_text(
            f"{COURSERA_ORIGIN}/search?query={requests.utils.quote(cleaned)}"
        )
        slugs = extract_learn_slugs_from_html(html)
        ranked = self.filter_accessible_slugs(rank_slugs_for_query(slugs, cleaned))
        if not ranked:
            raise RuntimeError(
                f"Coursera search found no course links for: {cleaned}. "
                "Open the search result in a browser and paste a /learn/... course URL."
            )
        return ranked[:limit]

    def filter_accessible_slugs(self, slugs: list[str]) -> list[str]:
        accessible = []
        for slug in slugs:
            try:
                self._get_course_materials(slug)
            except Exception:
                continue
            accessible.append(slug)
        return accessible or slugs

    def course_slugs_from_search_page(self, url: str, limit: int = 20) -> list[str]:
        html = self._get_text(url)
        slugs = extract_learn_slugs_from_html(html)
        if not slugs:
            raise RuntimeError(
                "Coursera search page has no course links. Paste a course, specialization, "
                "professional certificate, or a search URL with a query= parameter."
            )
        return slugs[:limit]

    def get_course(self, url_or_slug: str, preferred_lang: str = "en") -> CourseraCourse:
        slug = extract_course_slug(url_or_slug)
        data = self._get_course_materials(slug)
        elements = data.get("elements") or []
        if not elements:
            raise RuntimeError(f"Coursera course not found or not accessible: {slug}")

        course_id = elements[0]["id"]
        linked = data.get("linked") or {}
        modules = {
            item["id"]: item
            for item in linked.get("onDemandCourseMaterialModules.v1", [])
        }
        lessons = {
            item["id"]: item
            for item in linked.get("onDemandCourseMaterialLessons.v1", [])
        }
        items = {
            item["id"]: item
            for item in linked.get("onDemandCourseMaterialItems.v2", [])
        }

        lectures: list[CourseraLecture] = []
        non_video_items: list[CourseraLecture] = []
        index = 1
        for module_id in elements[0].get("moduleIds", []):
            module = modules.get(module_id, {})
            for lesson_id in module.get("lessonIds", []):
                lesson = lessons.get(lesson_id, {})
                for item_id in lesson.get("itemIds", []):
                    item = items.get(item_id, {})
                    item_slug = item.get("slug") or item_id
                    item_title = clean_title(item.get("name") or item_id)
                    if not self._is_lecture(item):
                        content_type = ((item.get("contentSummary") or {}).get("typeName") or "non-video")
                        non_video_items.append(CourseraLecture(
                            index=len(non_video_items) + 1,
                            course_id=course_id,
                            module_id=module_id,
                            module_name=clean_title(module.get("name") or f"Module {len(non_video_items) + 1}"),
                            lesson_id=lesson_id,
                            lesson_name=clean_title(lesson.get("name") or ""),
                            item_id=item_id,
                            item_slug=item_slug,
                            title=item_title,
                            url=f"{COURSERA_ORIGIN}/learn/{slug}/supplement/{item_id}/{item_slug}",
                            duration_ms=int(item.get("timeCommitment") or 0),
                            subtitles={},
                            selected_lang="",
                            error=f"Non-video Coursera item: {content_type}",
                        ))
                        continue
                    subtitles, selected_lang = self._get_lecture_subtitles(
                        course_id, item_id, preferred_lang
                    )
                    lectures.append(CourseraLecture(
                        index=index,
                        course_id=course_id,
                        module_id=module_id,
                        module_name=clean_title(module.get("name") or f"Module {len(lectures) + 1}"),
                        lesson_id=lesson_id,
                        lesson_name=clean_title(lesson.get("name") or ""),
                        item_id=item_id,
                        item_slug=item_slug,
                        title=item_title,
                        url=build_lecture_url(slug, item_id, item_slug),
                        duration_ms=int(item.get("timeCommitment") or 0),
                        subtitles=subtitles,
                        selected_lang=selected_lang,
                    ))
                    index += 1

        if not lectures and non_video_items:
            lectures = non_video_items

        return CourseraCourse(
            slug=slug,
            course_id=course_id,
            title=clean_title(self._get_course_title(slug) or self._course_title_from_slug(slug)),
            url=f"{COURSERA_ORIGIN}/learn/{slug}",
            lectures=lectures,
        )

    def download_course_markdown(
        self,
        url_or_slug: str,
        output_dir: Path,
        preferred_lang: str = "en",
    ) -> CourseraDownloadResult:
        course = self.get_course(url_or_slug, preferred_lang)
        success = skipped = failed = 0
        for lecture in course.lectures:
            subtitle_url = lecture.subtitles.get(lecture.selected_lang) if lecture.selected_lang else ""
            if not subtitle_url:
                lecture.error = f"No subtitle found for language preference: {preferred_lang}"
                skipped += 1
                continue
            try:
                subtitle_text = self._get_text(urljoin(COURSERA_ORIGIN, subtitle_url))
                lecture.segments = parse_srt(subtitle_text)
                if lecture.segments:
                    success += 1
                else:
                    lecture.error = "Subtitle file parsed empty"
                    skipped += 1
            except Exception as exc:
                lecture.error = str(exc)
                failed += 1

        output_dir.mkdir(parents=True, exist_ok=True)
        filename = add_date_prefix(safe_filename(course.title or course.slug)) + ".md"
        output_path = unique_path(output_dir / filename)
        output_path.write_text(course_to_markdown(course, preferred_lang), encoding="utf-8")

        return CourseraDownloadResult(
            course=course,
            output_path=output_path,
            success_count=success,
            skipped_count=skipped,
            failed_count=failed,
        )

    def _get_course_materials(self, slug: str) -> dict[str, Any]:
        params = {
            "q": "slug",
            "slug": slug,
            "showLockedItems": "true",
            "includes": "modules,lessons,items",
            "fields": (
                "moduleIds,"
                "onDemandCourseMaterialModules.v1(name,description,lessonIds,slug,timeCommitment),"
                "onDemandCourseMaterialLessons.v1(name,itemIds,slug,timeCommitment),"
                "onDemandCourseMaterialItems.v2(name,contentSummary,slug,timeCommitment)"
            ),
        }
        return self._get_json(f"{COURSERA_API}/onDemandCourseMaterials.v2/", params=params)

    def _get_course_title(self, slug: str) -> str:
        try:
            data = self._get_json(
                f"{COURSERA_API}/onDemandCourses.v1/",
                params={"q": "slug", "slug": slug, "fields": "name,slug"},
            )
            elements = data.get("elements") or []
            return str(elements[0].get("name") or "").strip() if elements else ""
        except Exception:
            return ""

    def _get_course_slug_by_id(self, course_id: str) -> str:
        data = self._get_json(
            f"{COURSERA_API}/courses.v1/{course_id}",
            params={"fields": "name,slug"},
        )
        elements = data.get("elements") or []
        return str(elements[0].get("slug") or "").strip() if elements else ""

    def _get_lecture_subtitles(
        self, course_id: str, item_id: str, preferred_lang: str
    ) -> tuple[dict[str, str], str]:
        data = self._get_json(
            f"{COURSERA_API}/onDemandLectureVideos.v1/{course_id}~{item_id}",
            params={"fields": "videoId,subtitles", "includes": "video"},
        )
        videos = (data.get("linked") or {}).get("onDemandVideos.v1", [])
        subtitles = videos[0].get("subtitles", {}) if videos else {}
        return subtitles, choose_language(subtitles, preferred_lang)

    def _get_json(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Expected JSON but got: {resp.text[:300]}") from exc

    def _get_text(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.timeout)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.content.decode("utf-8-sig", errors="replace")

    @staticmethod
    def _is_lecture(item: dict[str, Any]) -> bool:
        content_type = ((item.get("contentSummary") or {}).get("typeName") or "").lower()
        return content_type == "lecture"

    @staticmethod
    def _course_title_from_slug(slug: str) -> str:
        return re.sub(r"[-_]+", " ", slug).strip().title() or slug


def choose_language(subtitles: dict[str, str], preferred_lang: str) -> str:
    if not subtitles:
        return ""
    preferred = (preferred_lang or "").strip()
    candidates = []
    if preferred:
        candidates.extend([preferred, preferred.lower()])
        if "-" in preferred:
            candidates.append(preferred.split("-", 1)[0])
    candidates.extend(["en", "zh-CN", "zh-TW", "zh", "ja"])

    lower_map = {key.lower(): key for key in subtitles}
    for candidate in candidates:
        if candidate in subtitles:
            return candidate
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return next(iter(subtitles))


def safe_filename(value: str) -> str:
    safe = clean_title(value or "coursera-course")
    for char in FILENAME_BAD_CHARS:
        safe = safe.replace(char, "_")
    safe = safe.replace("#", "_")
    safe = re.sub(r"\s+", " ", safe).strip(" ._")
    return (safe or "coursera-course")[:120]


def clean_title(value: str) -> str:
    return re.sub(r"[\u2028\u2029\r\n\t]+", " ", str(value or "")).strip()


def clean_coursera_query(value: str) -> str:
    query = unquote(str(value or "")).strip()
    query = re.sub(r"^coursera\s+", "", query, flags=re.IGNORECASE).strip()
    query = re.sub(r"\s+", " ", query)
    return query


def extract_learn_slugs_from_html(html: str) -> list[str]:
    slugs = []
    seen = set()
    for match in re.finditer(r"/learn/([A-Za-z0-9_-]+)", html or ""):
        slug = match.group(1)
        if slug not in seen:
            seen.add(slug)
            slugs.append(slug)
    return slugs


def rank_slugs_for_query(slugs: list[str], query: str) -> list[str]:
    query_tokens = slug_tokens(query)

    def score(slug: str) -> tuple[int, int, int]:
        tokens = slug_tokens(slug)
        overlap = len(query_tokens & tokens)
        phrase_bonus = 1 if "-".join(query_tokens) in slug.lower() else 0
        generic_penalty = 1 if slug in {"ai-for-everyone", "prompt-engineering", "financial-markets-global"} else 0
        return (overlap + phrase_bonus * 2 - generic_penalty, overlap, -len(slug))

    ranked = sorted(slugs, key=score, reverse=True)
    return [slug for slug in ranked if score(slug)[0] > 0] or ranked


def slug_tokens(value: str) -> set[str]:
    stopwords = {"coursera", "course", "project", "the", "and", "for", "your", "you", "with"}
    return {
        token
        for token in re.split(r"[^a-z0-9]+", str(value or "").lower())
        if token and token not in stopwords
    }


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
