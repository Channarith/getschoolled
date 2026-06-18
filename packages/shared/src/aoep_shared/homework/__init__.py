"""Homework subtool: generate, scan/OCR, AI-vs-human detection, autograde."""

from .authorship import AuthorshipVerdict, detect_authorship
from .generate import assignment_from_slides, generate_assignment
from .ingest import Submission, ocr_to_submission, segment_answers
from .models import Assignment, Question, QuestionType

__all__ = [
    "Assignment",
    "Question",
    "QuestionType",
    "generate_assignment",
    "assignment_from_slides",
    "Submission",
    "ocr_to_submission",
    "segment_answers",
    "AuthorshipVerdict",
    "detect_authorship",
]
