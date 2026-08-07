"""Persistent page verdicts + free-form training comments."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from .corpus import default_data_dir
from .types import PageReview, PageVerdict, ReviewComment


class ReviewStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or default_data_dir()
        self._root = self._data_dir / "reviews"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._pages_path = self._root / "page_reviews.json"
        self._comments_path = self._root / "comments.json"
        self._pages: dict[str, PageReview] = {}
        self._comments: list[ReviewComment] = []
        self._load()

    @staticmethod
    def page_key(source_id: str, page_index: int) -> str:
        return f"{source_id}::{page_index}"

    def _load(self) -> None:
        if self._pages_path.is_file():
            raw = json.loads(self._pages_path.read_text(encoding="utf-8"))
            for row in raw.get("pages", []):
                review = PageReview.model_validate(row)
                self._pages[self.page_key(review.source_id, review.page_index)] = review
        if self._comments_path.is_file():
            raw = json.loads(self._comments_path.read_text(encoding="utf-8"))
            self._comments = [ReviewComment.model_validate(r) for r in raw.get("comments", [])]

    def _save_pages(self) -> None:
        payload = {
            "updated_at_ms": int(time.time() * 1000),
            "pages": [p.model_dump(mode="json") for p in self._pages.values()],
        }
        self._pages_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _save_comments(self) -> None:
        payload = {
            "updated_at_ms": int(time.time() * 1000),
            "comments": [c.model_dump(mode="json") for c in self._comments],
        }
        self._comments_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def set_page_verdict(
        self,
        *,
        source_id: str,
        page_index: int,
        marked_reject: bool,
        comment: str = "",
    ) -> PageReview:
        with self._lock:
            verdict = PageVerdict.DISLIKE if marked_reject else PageVerdict.LIKE
            review = PageReview(
                source_id=source_id,
                page_index=page_index,
                verdict=verdict,
                marked_reject=marked_reject,
                comment=comment,
                updated_at_ms=int(time.time() * 1000),
            )
            self._pages[self.page_key(source_id, page_index)] = review
            self._save_pages()
            return review

    def get_page(self, source_id: str, page_index: int) -> PageReview | None:
        return self._pages.get(self.page_key(source_id, page_index))

    def pages_for(self, source_id: str) -> list[PageReview]:
        rows = [p for p in self._pages.values() if p.source_id == source_id]
        return sorted(rows, key=lambda p: p.page_index)

    def add_comment(
        self,
        *,
        source_id: str,
        body: str,
        author: str = "reviewer",
        page_index: int | None = None,
        course_id: str | None = None,
        slide_index: int | None = None,
        tags: list[str] | None = None,
    ) -> ReviewComment:
        with self._lock:
            comment = ReviewComment(
                comment_id=str(uuid.uuid4()),
                source_id=source_id,
                page_index=page_index,
                course_id=course_id,
                slide_index=slide_index,
                author=author,
                body=body.strip(),
                tags=list(tags or []),
                created_at_ms=int(time.time() * 1000),
            )
            self._comments.append(comment)
            self._save_comments()
            return comment

    def comments_for(
        self,
        *,
        source_id: str | None = None,
        course_id: str | None = None,
    ) -> list[ReviewComment]:
        rows = self._comments
        if source_id:
            rows = [c for c in rows if c.source_id == source_id]
        if course_id:
            rows = [c for c in rows if c.course_id == course_id]
        return sorted(rows, key=lambda c: c.created_at_ms, reverse=True)
