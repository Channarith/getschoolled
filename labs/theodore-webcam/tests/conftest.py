"""Pytest fixtures for the Theodore webcam lab.

Puts ``src`` on the path so ``import theodore_webcam.*`` resolves without an
install, and exposes the synthetic scene helpers plus a controllable clock so
presence timing is tested deterministically instead of with sleeps.
"""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
for _p in (_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _scene import empty_room, person_scene  # noqa: E402


class FakeClock:
    """Monotonic clock the tests advance by hand."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += float(seconds)
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def scene():
    return {"empty_room": empty_room, "person_scene": person_scene}
