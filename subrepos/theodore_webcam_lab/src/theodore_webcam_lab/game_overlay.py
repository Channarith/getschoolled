"""Client-side game overlay constants mirrored in monitor_page.js.

The browser draws finger trails and AR costumes on the webcam canvas; this
module exists so tests can pin the tunable durations and costume ids without
scraping embedded JavaScript strings alone.
"""

from __future__ import annotations

# Visible index-fingertip trail fade window on the mirrored webcam overlay (ms).
FINGER_TRAIL_DURATION_MS = 1_500

# MediaPipe hand landmark index for the index fingertip.
INDEX_FINGER_TIP = 8

# Kid-safe AR costume ids cycled during webcam games (order matches monitor JS).
GAME_COSTUME_IDS: tuple[str, ...] = (
    "none",
    "glasses",
    "party_hat",
    "makeup",
    "cat_ears",
    "pumpkin",
    "wizard",
    "sunglasses",
)
