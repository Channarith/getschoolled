"""Canonical learnable content document for unified browse/search."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class LearnableItem(BaseModel):
    """One searchable learning asset across catalog, audio, live, languages, etc."""

    id: str
    source: str
    source_id: str
    title: str
    subtitle: str = ""
    category: str = ""
    subject: str = ""
    format: str = "video"
    level: str = "beginner"
    language: str = "en"
    duration_min: int = 0
    tags: List[str] = Field(default_factory=list)
    maturity_rating: str = "all"
    audiences: List[str] = Field(default_factory=list)
    hands_on: bool = False
    drive_safe: bool = False
    access_tier: str = "free"
    preview: str = ""
    deep_link: str = ""
    popularity: int = 0

    def catalog_media_format(self) -> str:
        """Map to legacy CatalogStore media_format values."""
        mapping = {
            "audio": "audio",
            "live_class": "interactive",
            "interactive": "interactive",
            "program": "text",
            "game": "interactive",
            "video": "video",
        }
        return mapping.get(self.format, self.format)
