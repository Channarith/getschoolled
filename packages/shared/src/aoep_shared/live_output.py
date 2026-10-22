"""Skip speakers and browser windows during tests and headless runs."""

from __future__ import annotations

import os


def live_output_suppressed() -> bool:
    """True when a presenter must not speak or open a browser.

    ``HEADLESS`` is the explicit switch. Pytest sets ``PYTEST_CURRENT_TEST``
    on every test, and those runs were still opening the slide deck and
    speaking lessons because nothing exported ``HEADLESS``.
    """
    return bool(os.environ.get("HEADLESS") or os.environ.get("PYTEST_CURRENT_TEST"))
