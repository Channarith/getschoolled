"""Authenticate, find a lesson, and start a solo teaching session."""

from __future__ import annotations

import os

from aoep_sdk import AOEPClient, AOEPError


def main() -> None:
    client = AOEPClient()
    email = os.environ["AOEP_EXAMPLE_EMAIL"]
    password = os.environ["AOEP_EXAMPLE_PASSWORD"]

    try:
        account = client.authenticate(email, password)["account"]
        lessons = client.orchestrator.list_lessons(language="en")
        if not lessons:
            print("No English lessons are currently available.")
            return

        lesson = lessons[0]
        view = client.orchestrator.start_session(
            lesson["lesson_id"],
            class_type="solo",
            student_id=account.get("id"),
        )
        session_id = view["session"]["session_id"]
        answer = client.orchestrator.ask(
            session_id,
            "What will I learn in this lesson?",
        )
        print(f"Signed in as: {account.get('email', email)}")
        print(f"Lesson: {lesson['title']}")
        print(f"Session: {session_id}")
        print(f"Theodore: {answer['text']}")
    except AOEPError as exc:
        print(f"AOEP request failed: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
