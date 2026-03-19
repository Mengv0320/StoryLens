from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


CHAPTER_TITLE_RE = re.compile(
    r"(第[0-9零一二三四五六七八九十百千万两〇]+[章回节卷篇部集话][^\n]{0,40}|Chapter\s+\d+[^\n]{0,40})",
    re.IGNORECASE,
)
LIKELY_CONTENT_RE = re.compile(r"(content|article|chapter|text|read|main|entry|post)", re.IGNORECASE)
NOISE_RE = re.compile(r"(nav|menu|header|footer|comment|share|tool|login|sign|ad|banner|copyright)", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class ChapterLink:
    title: str
    url: str


@dataclass
class CrawledChapter:
    chapter_id: str
    title: str
    url: str
    text: str


@dataclass
class ChapterPreview:
    chapter_id: str
    index: int
    title: str
    url: str


@dataclass
class CrawledBook:
    title: str
    author: str | None
    source_url: str
    chapters: list[CrawledChapter]


@dataclass
class BookPreview:
    title: str
    author: str | None
    source_url: str
    chapters: list[ChapterPreview]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        self._href = attr_map.get("href")
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        text = clean_text("".join(self._parts))
        self.links.append((self._href, text))
        self._href = None
        self._parts = []


class ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._stack: list[dict[str, str]] = []
        self._title_parts: list[str] = []
        self._in_title = False
        self._body_chunks: list[tuple[float, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        node = {
            "tag": tag,
            "id": attr_map.get("id", ""),
            "class": attr_map.get("class", ""),
        }
        self._stack.append(node)
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = clean_text(data)
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        score = self._score_current_path()
        if score > 0:
            self._body_chunks.append((score, text))

    def title(self) -> str:
        return clean_text(" ".join(self._title_parts))

    def content_text(self) -> str:
        if not self._body_chunks:
            return ""
        max_score = max(score for score, _ in self._body_chunks)
        chosen = [text for score, text in self._body_chunks if score >= max_score - 0.5]
        return collapse_lines(chosen)

    def _score_current_path(self) -> float:
        score = 0.0
        for node in self._stack:
            tag = node["tag"]
            marker = f'{node["id"]} {node["class"]}'
            if tag in {"article", "main"}:
                score += 3.0
            if tag in {"p", "div", "section"}:
                score += 0.5
            if LIKELY_CONTENT_RE.search(marker):
                score += 2.0
            if NOISE_RE.search(marker):
                score -= 2.5
        return score


def fetch_html(url: str, encoding: str | None = None, user_agent: str | None = None, timeout: int = 20) -> str:
    headers = {
        "User-Agent": user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        detected = encoding or response.headers.get_content_charset() or "utf-8"
    return raw.decode(detected, errors="ignore")


def extract_chapter_links(index_url: str, html: str, same_host_only: bool = True) -> list[ChapterLink]:
    parser = LinkParser()
    parser.feed(html)

    base_host = urlparse(index_url).netloc
    seen: set[str] = set()
    links: list[ChapterLink] = []

    for href, text in parser.links:
        if not href:
            continue
        absolute_url = urljoin(index_url, href)
        parsed = urlparse(absolute_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if same_host_only and parsed.netloc != base_host:
            continue
        if not CHAPTER_TITLE_RE.search(text):
            continue
        normalized = parsed._replace(fragment="").geturl()
        if normalized in seen:
            continue
        seen.add(normalized)
        links.append(ChapterLink(title=text, url=normalized))

    return links


def extract_chapter_content(html: str, fallback_title: str) -> tuple[str, str]:
    parser = ArticleParser()
    parser.feed(html)
    title = parser.title() or fallback_title
    text = parser.content_text()
    if not text:
        # Last-resort fallback: strip tags crudely.
        text = clean_text(re.sub(r"<[^>]+>", "\n", html))
    return title, text


def crawl_novel(
    index_url: str,
    limit: int | None = None,
    encoding: str | None = None,
    user_agent: str | None = None,
    timeout: int = 20,
) -> list[CrawledChapter]:
    return crawl_novel_book(
        index_url=index_url,
        limit=limit,
        encoding=encoding,
        user_agent=user_agent,
        timeout=timeout,
    ).chapters


def crawl_novel_book(
    index_url: str,
    limit: int | None = None,
    encoding: str | None = None,
    user_agent: str | None = None,
    timeout: int = 20,
) -> CrawledBook:
    special = try_crawl_bqg_family(index_url, limit=limit, encoding=encoding, user_agent=user_agent, timeout=timeout)
    if special is not None:
        return special

    index_html = fetch_html(index_url, encoding=encoding, user_agent=user_agent, timeout=timeout)
    chapter_links = extract_chapter_links(index_url, index_html)
    if limit is not None:
        chapter_links = chapter_links[:limit]

    chapters: list[CrawledChapter] = []
    for idx, link in enumerate(chapter_links, start=1):
        chapter_html = fetch_html(link.url, encoding=encoding, user_agent=user_agent, timeout=timeout)
        title, text = extract_chapter_content(chapter_html, fallback_title=link.title)
        chapters.append(
            CrawledChapter(
                chapter_id=f"chapter_{idx:03d}",
                title=title,
                url=link.url,
                text=text,
            )
        )
    return CrawledBook(
        title=extract_index_title(index_html) or "Unknown Novel",
        author=None,
        source_url=index_url,
        chapters=chapters,
    )


def inspect_novel_book(
    index_url: str,
    limit: int | None = None,
    encoding: str | None = None,
    user_agent: str | None = None,
    timeout: int = 20,
) -> BookPreview:
    special = try_inspect_bqg_family(index_url, limit=limit, encoding=encoding, user_agent=user_agent, timeout=timeout)
    if special is not None:
        return special

    index_html = fetch_html(index_url, encoding=encoding, user_agent=user_agent, timeout=timeout)
    chapter_links = extract_chapter_links(index_url, index_html)
    if limit is not None:
        chapter_links = chapter_links[:limit]
    chapters = [
        ChapterPreview(
            chapter_id=f"chapter_{idx:03d}",
            index=idx,
            title=link.title,
            url=link.url,
        )
        for idx, link in enumerate(chapter_links, start=1)
    ]
    return BookPreview(
        title=extract_index_title(index_html) or "Unknown Novel",
        author=None,
        source_url=index_url,
        chapters=chapters,
    )


BQG_ORIGIN_HOSTS = {"bqg128.cc", "bqg403.top"}
BQG_MIRROR_RE = re.compile(r"bqg\d+\.\w+")


def _is_bqg_family(host: str) -> bool:
    h = host.lower().removeprefix("www.")
    if h in BQG_ORIGIN_HOSTS:
        return True
    return bool(BQG_MIRROR_RE.search(h))


def _is_bqg_mirror(host: str) -> bool:
    h = host.lower().removeprefix("www.")
    return h not in BQG_ORIGIN_HOSTS and bool(BQG_MIRROR_RE.search(h))


def try_crawl_bqg_family(
    index_url: str,
    limit: int | None = None,
    encoding: str | None = None,
    user_agent: str | None = None,
    timeout: int = 20,
) -> CrawledBook | None:
    parsed = urlparse(index_url)
    host = parsed.netloc.lower()
    if not _is_bqg_family(host):
        return None

    original_book_id = parse_bqg_book_id(parsed.path)
    if original_book_id is None:
        # Also try hash fragment pattern: /#/book/12345/
        fragment_match = re.search(r"/book/(\d+)", parsed.fragment)
        if fragment_match:
            original_book_id = int(fragment_match.group(1))
        else:
            return None

    mirror_base, mirror_book_id, book_meta, chapter_names = load_bqg_book_preview(
        index_url=index_url,
        original_book_id=original_book_id,
        encoding=encoding,
        user_agent=user_agent,
        timeout=timeout,
    )
    if limit is not None:
        chapter_names = chapter_names[:limit]

    title = str(book_meta.get("title", "")).strip()
    chapters: list[CrawledChapter] = []
    for idx, chapter_name in enumerate(chapter_names, start=1):
        chapter_data = fetch_bqg_json(
            f"{mirror_base}/api/chapter?id={mirror_book_id}&chapterid={idx}",
            referer=f"{mirror_base}/#/book/{mirror_book_id}/{idx}.html",
            encoding=encoding,
            user_agent=user_agent,
            timeout=timeout,
        )
        text = str(chapter_data.get("txt", "")).strip()
        resolved_title = str(chapter_data.get("chaptername", "")).strip() or str(chapter_name).strip()
        chapters.append(
            CrawledChapter(
                chapter_id=f"chapter_{idx:03d}",
                title=resolved_title,
                url=f"{mirror_base}/#/book/{mirror_book_id}/{idx}.html",
                text=text,
            )
        )
    if not chapters and title:
        raise RuntimeError(f"No chapters returned for {title}.")
    return CrawledBook(
        title=title or "Unknown Novel",
        author=str(book_meta.get("author", "")).strip() or None,
        source_url=index_url,
        chapters=chapters,
    )


def try_inspect_bqg_family(
    index_url: str,
    limit: int | None = None,
    encoding: str | None = None,
    user_agent: str | None = None,
    timeout: int = 20,
) -> BookPreview | None:
    parsed = urlparse(index_url)
    host = parsed.netloc.lower()
    if not _is_bqg_family(host):
        return None

    original_book_id = parse_bqg_book_id(parsed.path)
    if original_book_id is None:
        fragment_match = re.search(r"/book/(\d+)", parsed.fragment)
        if fragment_match:
            original_book_id = int(fragment_match.group(1))
        else:
            return None

    mirror_base, mirror_book_id, book_meta, chapter_names = load_bqg_book_preview(
        index_url=index_url,
        original_book_id=original_book_id,
        encoding=encoding,
        user_agent=user_agent,
        timeout=timeout,
    )
    if limit is not None:
        chapter_names = chapter_names[:limit]
    chapters = [
        ChapterPreview(
            chapter_id=f"chapter_{idx:03d}",
            index=idx,
            title=str(chapter_name).strip(),
            url=f"{mirror_base}/#/book/{mirror_book_id}/{idx}.html",
        )
        for idx, chapter_name in enumerate(chapter_names, start=1)
    ]
    return BookPreview(
        title=str(book_meta.get("title", "")).strip() or "Unknown Novel",
        author=str(book_meta.get("author", "")).strip() or None,
        source_url=index_url,
        chapters=chapters,
    )


def parse_bqg_book_id(path: str) -> int | None:
    match = re.search(r"/book/(\d+)/?", path)
    if not match:
        return None
    return int(match.group(1))


def resolve_bqg_mirror(index_url: str, original_book_id: int, user_agent: str | None = None, timeout: int = 20) -> tuple[str, int]:
    parsed = urlparse(index_url)
    host = parsed.netloc.lower()
    # If the URL is already a mirror site (e.g. bqg475.cc), use it directly
    if _is_bqg_mirror(host):
        mirror_base = f"{parsed.scheme}://{parsed.netloc}"
        return mirror_base, original_book_id

    verify_url = f"https://www.bqg128.cc/userverify/book/{original_book_id}/1.html"
    request = Request(
        verify_url,
        headers={"User-Agent": user_agent or "Mozilla/5.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
    match = re.search(r"(https://[^/]+)/#/book/(\d+)/1\.html", final_url)
    if not match:
        raise RuntimeError(f"Failed to resolve mirror book id from redirect: {final_url}")
    return match.group(1), int(match.group(2))


def load_bqg_book_preview(
    index_url: str,
    original_book_id: int,
    encoding: str | None = None,
    user_agent: str | None = None,
    timeout: int = 20,
) -> tuple[str, int, dict, list[str]]:
    mirror_base, mirror_book_id = resolve_bqg_mirror(index_url, original_book_id, user_agent=user_agent, timeout=timeout)
    book_meta = fetch_bqg_json(
        f"{mirror_base}/api/book?id={mirror_book_id}",
        referer=f"{mirror_base}/#/book/{mirror_book_id}",
        encoding=encoding,
        user_agent=user_agent,
        timeout=timeout,
    )
    book_list = fetch_bqg_json(
        f"{mirror_base}/api/booklist?id={mirror_book_id}",
        referer=f"{mirror_base}/#/book/{mirror_book_id}",
        encoding=encoding,
        user_agent=user_agent,
        timeout=timeout,
    )
    chapter_names = book_list.get("list") or []
    if not isinstance(chapter_names, list):
        raise RuntimeError("Unexpected bqg book list payload.")
    return mirror_base, mirror_book_id, book_meta, chapter_names


def fetch_bqg_json(
    url: str,
    referer: str,
    encoding: str | None = None,
    user_agent: str | None = None,
    timeout: int = 20,
) -> dict:
    headers = {
        "User-Agent": user_agent or "Mozilla/5.0",
        "Referer": referer,
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    detected = encoding or "utf-8"
    return json.loads(raw.decode(detected, errors="ignore"))


def save_crawled_chapters(
    chapters: Iterable[CrawledChapter],
    output_path: Path,
    json_output_path: Path | None = None,
) -> None:
    chapter_list = list(chapters)
    lines: list[str] = []
    for chapter in chapter_list:
        lines.append(chapter.title)
        lines.append(chapter.text)
        lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps([asdict(chapter) for chapter in chapter_list], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def select_chapters(
    chapters: list[CrawledChapter],
    start: int | None = None,
    end: int | None = None,
    context_before: int = 0,
) -> tuple[list[CrawledChapter], list[CrawledChapter]]:
    total = len(chapters)
    if total == 0:
        return [], []
    if start is None and end is None:
        return [], chapters
    start_index = max(1, start or 1)
    end_index = min(total, end or total)
    if start_index > end_index:
        raise RuntimeError(f"Invalid chapter range: start={start_index}, end={end_index}")

    context_start = max(1, start_index - max(0, context_before))
    context = chapters[context_start - 1:start_index - 1]
    selected = chapters[start_index - 1:end_index]
    return context, selected


def extract_index_title(html: str) -> str:
    parser = ArticleParser()
    parser.feed(html)
    return parser.title()


def format_chapter_listing(book: CrawledBook) -> str:
    lines = [f"Book: {book.title}"]
    if book.author:
        lines.append(f"Author: {book.author}")
    lines.append(f"Chapters: {len(book.chapters)}")
    for idx, chapter in enumerate(book.chapters, start=1):
        lines.append(f"{idx:04d}. {chapter.title}")
    return "\n".join(lines)


def save_selected_chapters(
    book: CrawledBook,
    context_chapters: list[CrawledChapter],
    selected_chapters: list[CrawledChapter],
    output_path: Path,
    json_output_path: Path | None = None,
) -> None:
    lines = [f"# {book.title}"]
    if book.author:
        lines.append(f"# Author: {book.author}")
    lines.append(f"# Source: {book.source_url}")
    lines.append("")

    if context_chapters:
        lines.append("[Context Chapters]")
        for chapter in context_chapters:
            lines.append(chapter.title)
            lines.append(chapter.text)
            lines.append("")

    lines.append("[Selected Chapters]")
    for chapter in selected_chapters:
        lines.append(chapter.title)
        lines.append(chapter.text)
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    if json_output_path is not None:
        payload = {
            "title": book.title,
            "author": book.author,
            "source_url": book.source_url,
            "context_chapters": [asdict(chapter) for chapter in context_chapters],
            "selected_chapters": [asdict(chapter) for chapter in selected_chapters],
        }
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", unescape(text)).strip()


def collapse_lines(parts: list[str]) -> str:
    merged: list[str] = []
    previous = ""
    for part in parts:
        text = clean_text(part)
        if not text or text == previous:
            continue
        previous = text
        merged.append(text)
    return "\n".join(merged)
