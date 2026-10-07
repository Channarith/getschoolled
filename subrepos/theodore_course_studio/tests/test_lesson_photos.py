"""Lesson photographs replace geometric storyboards on the stage."""

from theodore_course_studio.lesson_photos import photo_plate


def test_stop_sign_uses_the_stop_photograph():
    plate = photo_plate(
        title="Stop signs",
        body="A red octagon means stop.",
        category="driver_education",
        index=2,
    )
    assert plate["file"] == "lesson-stop.jpg"
    assert plate["url"].endswith("/lesson_photos/lesson-stop.jpg")
    assert plate["transition"] == "wipe"


def test_handwashing_uses_the_sink_photograph():
    plate = photo_plate(
        title="Wash your hands",
        body="Soap and warm water before you touch food.",
        category="food_safety",
        index=0,
    )
    assert plate["file"] == "lesson-handwash.jpg"
    assert plate["transition"] == "fade"


def test_unknown_slide_uses_a_classroom_or_course_default():
    classroom = photo_plate(title="One", body="Alpha point.", category="leadership", index=0)
    assert classroom["file"] == "lesson-classroom.jpg"
    assert classroom["transition"] == "fade"
    driving = photo_plate(title="Welcome", body="Today we begin.", category="driver_education", index=4)
    assert driving["file"] == "lesson-intersection.jpg"
    assert driving["transition"] == "cover"
    kitchen = photo_plate(title="Welcome", body="Today we begin.", category="food_safety", index=5)
    assert kitchen["file"] == "lesson-kitchen.jpg"
    assert kitchen["transition"] == "split"
