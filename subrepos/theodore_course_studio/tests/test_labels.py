from __future__ import annotations

from theodore_course_studio.labels import (
    normalize_category,
    parse_quality_label,
    should_incorporate,
    title_guess_from_filename,
)
from theodore_course_studio.types import CategoryId, QualityLabel


def test_parse_quality_with_underscores_and_spaces():
    assert parse_quality_label("Comm#1_Good_Effective Communication_PDF.pdf") is QualityLabel.GOOD
    assert parse_quality_label("S.Harassment#1_ Bad_Resource_PDF.pdf") is QualityLabel.BAD
    assert parse_quality_label("Leadership#14_Better_ effective leadership_PDF.pdf") is QualityLabel.BETTER
    assert parse_quality_label("Leadership#6_Moderate_Teacher leadership_PDF.pdf") is QualityLabel.MODERATE
    assert parse_quality_label("random_notes.pdf") is QualityLabel.UNLABELED


def test_incorporate_policy():
    assert should_incorporate(QualityLabel.GOOD) is True
    assert should_incorporate(QualityLabel.BETTER) is True
    assert should_incorporate(QualityLabel.MODERATE) is False
    assert should_incorporate(QualityLabel.BAD) is False


def test_category_aliases():
    assert normalize_category("3. Communication") is CategoryId.COMMUNICATION
    assert normalize_category("Leadership") is CategoryId.LEADERSHIP
    assert normalize_category("Sexual Harassment") is CategoryId.SEXUAL_HARASSMENT
    assert normalize_category("Driver Education") is CategoryId.DRIVER_EDUCATION
    assert normalize_category("CA DMV") is CategoryId.DRIVER_EDUCATION
    assert normalize_category("Food Safety") is CategoryId.FOOD_SAFETY
    assert normalize_category("Food Handler") is CategoryId.FOOD_SAFETY
    assert normalize_category("Alameda Food") is CategoryId.FOOD_SAFETY


def test_title_guess_strips_catalog_noise():
    title = title_guess_from_filename("Comm#1_Good_Effective Communication (2015)_WHO_PDF.pdf")
    assert "Good" not in title
    assert "Effective" in title or "Communication" in title
