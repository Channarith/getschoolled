"""Personalized notifications feed endpoint."""

from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_default_feed_has_daily_reminder_and_new_class():
    body = client.get("/notifications/feed").json()
    assert body["student_id"] == "guest"
    kinds = {i["kind"] for i in body["items"]}
    assert "reminder" in kinds
    assert "new_class" in kinds
    assert all("created_at" in i and "title" in i for i in body["items"])


def test_streak_and_in_progress_render():
    body = client.get(
        "/notifications/feed",
        params={
            "student_id": "ana",
            "interests": "spanish,history",
            "streak_days": 5,
            "in_progress": "lang-es-phrases,lang-fr-phrases",
        },
    ).json()
    kinds = [i["kind"] for i in body["items"]]
    assert "streak" in kinds
    assert kinds.count("continue") >= 1
    streak = next(i for i in body["items"] if i["kind"] == "streak")
    assert "5-day" in streak["title"]


def test_unread_excludes_reminder_and_streak():
    body = client.get(
        "/notifications/feed",
        params={"interests": "spanish", "streak_days": 3},
    ).json()
    new_recs = sum(1 for i in body["items"]
                   if i["kind"] in {"new_class", "continue", "recommended"})
    assert body["unread"] == new_recs


def test_deep_links_for_drive_mode():
    body = client.get("/notifications/feed").json()
    drive_links = [i["deep_link"] for i in body["items"] if i["deep_link"]]
    assert any(link.startswith("aiclassroom://drive") for link in drive_links)


def test_limit_caps_items():
    body = client.get("/notifications/feed", params={"limit": 3}).json()
    assert len(body["items"]) <= 3


def test_locale_param_translates_feed():
    es = client.get("/notifications/feed",
                    params={"locale": "es", "interests": "spanish"}).json()
    titles = " ".join(i["title"] for i in es["items"])
    assert "Nueva clase" in titles or "Tu clase diaria" in titles

    ja = client.get("/notifications/feed", params={"locale": "ja"}).json()
    assert any("クラス" in i["title"] or "ドライブ" in i["body"] for i in ja["items"])


def test_locales_endpoint_lists_supported_languages():
    body = client.get("/notifications/locales").json()
    assert "en" in body["locales"]
    assert "es" in body["locales"]


def test_unknown_locale_falls_back_cleanly():
    body = client.get("/notifications/feed", params={"locale": "zz"}).json()
    titles = " ".join(i["title"] for i in body["items"])
    assert "Your daily class is ready" in titles
