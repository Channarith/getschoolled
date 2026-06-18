"""Homework subtool: generate, scan/OCR, AI-vs-human detection, autograde."""

from .generate import assignment_from_slides, generate_assignment
from .models import Assignment, Question, QuestionType

__all__ = [
    "Assignment",
    "Question",
    "QuestionType",
    "generate_assignment",
    "assignment_from_slides",
]
