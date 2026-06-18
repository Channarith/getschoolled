"""Homework autograder tests (Phase 9)."""

from aoep_shared.homework import Assignment, Question, QuestionType, grade_submission
from aoep_shared.homework.authorship import AuthorshipVerdict
from aoep_shared.homework.sources import restrict_to_domains, trusted_domains_for
from aoep_shared.providers.base import SearchResult
from aoep_shared.providers.search import MockSearchProvider


def test_mcq_graded_against_key():
    q = Question(type=QuestionType.MCQ, prompt="Pick", options=["oxygen", "iron", "salt"], answer_index=0)
    a = Assignment(title="HW", questions=[q])
    g = grade_submission(a, ["plants release oxygen"])
    assert g.items[0].correct is True
    assert g.score == 1.0


def test_open_item_corroborated_by_catalog():
    q = Question(type=QuestionType.SHORT, prompt="Explain photosynthesis", answer_key="")
    a = Assignment(title="HW", subject="biology", questions=[q])
    passages = ["Photosynthesis: plants convert light water and carbon dioxide into glucose and oxygen."]
    g = grade_submission(
        a, ["Plants convert light water and carbon dioxide into glucose and oxygen."],
        context_passages=passages,
    )
    assert g.items[0].score == 1.0
    assert any(c.get("source") == "catalog" for c in g.items[0].citations)


def test_medical_open_item_corroborated_by_trusted_domain():
    q = Question(type=QuestionType.SHORT, prompt="What does ibuprofen treat?", answer_key="")
    a = Assignment(title="Med HW", subject="medical", questions=[q])
    answer = "Ibuprofen reduces pain inflammation and fever"
    canned = {answer: [SearchResult(
        title="Ibuprofen - WebMD", url="https://www.webmd.com/drugs/ibuprofen",
        snippet="Ibuprofen reduces pain inflammation and fever", engine="mock",
    )]}
    engines = [MockSearchProvider(canned=canned)]
    g = grade_submission(a, [answer], engines=engines, subject="medical")
    assert g.items[0].score == 1.0
    assert any("webmd.com" in (c.get("url") or "") for c in g.items[0].citations)


def test_unsupported_answer_flagged_for_review():
    q = Question(type=QuestionType.SHORT, prompt="Explain", answer_key="")
    a = Assignment(title="HW", subject="biology", questions=[q])
    g = grade_submission(a, ["completely unrelated gibberish zzz"], context_passages=["Photosynthesis: glucose."])
    assert g.items[0].score < 1.0


def test_trusted_domain_filter():
    domains = trusted_domains_for("medical")
    assert "webmd.com" in domains
    results = [
        SearchResult("a", "https://www.webmd.com/x", "s", "mock"),
        SearchResult("b", "https://randomblog.example/x", "s", "mock"),
    ]
    kept = restrict_to_domains(results, domains)
    assert len(kept) == 1 and "webmd.com" in kept[0].url


def test_ai_authorship_flag_propagates():
    q = Question(type=QuestionType.MCQ, prompt="p", options=["a", "b"], answer_index=0)
    a = Assignment(title="HW", questions=[q])
    av = AuthorshipVerdict(label="ai", ai_probability=0.9)
    g = grade_submission(a, ["a"], authorship=av)
    assert "possible_ai_authorship" in g.validity_flags
    assert g.authorship_label == "ai"
