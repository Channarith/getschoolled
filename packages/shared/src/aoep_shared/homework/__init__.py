"""Homework subtool: generate, scan/OCR, AI-vs-human detection, autograde."""

from .authorship import AuthorshipVerdict, detect_authorship
from .generate import assignment_from_slides, generate_assignment
from .grade import HomeworkGrade, ItemGrade, grade_submission
from .ingest import Submission, ocr_to_submission, segment_answers
from .models import Assignment, Question, QuestionType
from .sources import restrict_to_domains, trusted_domains_for

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
    "HomeworkGrade",
    "ItemGrade",
    "grade_submission",
    "trusted_domains_for",
    "restrict_to_domains",
]
