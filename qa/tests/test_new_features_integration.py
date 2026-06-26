"""Cross-service smoke tests for recently shipped features.

These tests exercise shared libraries and lightweight HTTP surfaces without
requiring a full docker stack. They complement per-service unit/API suites.
"""

from fastapi.testclient import TestClient

from aoep_shared.audio_courses import build_catalog
from aoep_shared.games import GameType, make_round, score_round
from aoep_shared.lesson_depth import TARGET_MIN_MINUTES, duration_minutes
from aoep_shared.plan_pricing import STANDARD_PRICE_USD, VIP_PRICE_USD, price_usd_for_tier
from billing.main import app as billing_app
from identity.main import app as identity_app
from orchestrator.curriculum import CurriculumStore
from orchestrator.main import app as orchestrator_app


def test_pricing_and_onboarding_membership_flow():
    ic = TestClient(identity_app)
    signup = ic.post("/auth/signup", json={
        "email": "smoke-onboard@example.com",
        "password": "S3cretpass",
        "display_name": "Smoke",
    }).json()
    tok = signup["token"]
    h = {"Authorization": f"Bearer {tok}"}

    ic.post("/onboarding/billing", headers=h, json={
        "line1": "1 Main St", "city": "Austin", "state": "TX", "postal_code": "78701",
        "country": "US", "card_number": "4242424242424242", "exp_month": 12,
        "exp_year": 2030, "cvv": "123",
    })
    plan = ic.post("/onboarding/plan", headers=h, json={"tier": "premium"}).json()
    assert plan["membership_class"] == "vip"

    bc = TestClient(billing_app)
    consumer = bc.get("/plans/consumer").json()
    assert consumer["basic"]["price_usd"] == STANDARD_PRICE_USD
    assert consumer["premium"]["price_usd"] == VIP_PRICE_USD
    assert price_usd_for_tier("premium") == VIP_PRICE_USD


def test_deep_lesson_and_director_adaptation_smoke():
    store = CurriculumStore()
    lesson = store.get("intro-to-photosynthesis")
    assert lesson is not None
    assert duration_minutes(lesson.slides) >= TARGET_MIN_MINUTES

    oc = TestClient(orchestrator_app)
    plan = oc.post("/director/plan", json={
        "class_type": "group",
        "slides_total": len(lesson.slides),
        "slide_index": 2,
        "pending_questions": 0,
        "attention": 0.6,
        "slides_since_quiz": 2,
        "topic_mastery": 0.4,
        "quiz_accuracy": 0.5,
        "avg_response_latency_s": 12.0,
        "attention_trend": 0.6,
        "question_rate": 0.0,
        "declared_pace": "slow",
        "adaptation": {"observed_pace": "slow"},
    }).json()
    assert plan["pacing"] == "slow"


def test_drive_mode_and_marathon_games_smoke():
    sample = build_catalog()[0]
    assert sample.duration_min >= 20
    assert any(s.kind in ("quiz", "reinforcement", "narration") for s in sample.segments)

    rnd = make_round("biology", GameType.MARATHON, seed=42)
    answers = {m.id: m.answer_index for m in rnd.mcqs}
    res = score_round(rnd, answers, elapsed_s=90)
    assert res.total == 15
    assert res.points > 0


def test_adaptation_profile_roundtrip():
    ic = TestClient(identity_app)
    signup = ic.post("/auth/signup", json={
        "email": "smoke-adapt@example.com",
        "password": "S3cretpass",
        "display_name": "Adapt",
    }).json()
    tok = signup["token"]
    h = {"Authorization": f"Bearer {tok}"}
    sid = ic.get("/students", headers=h).json()["students"][0]["id"]

    ic.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "trigger",
        "payload": {"trigger": "too fast", "reason": "overwhelmed"},
    })
    ic.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "strategy_failure",
        "payload": {"strategy": "socratic", "topic": "algebra", "reason": "confused"},
    })
    profile = ic.get(f"/students/{sid}/adaptation", headers=h).json()
    assert profile["adaptation"]["known_triggers"]
    assert profile["adaptation"]["failed_approaches"]
