"""Client-side game overlay constants mirrored in monitor_page.js."""

from __future__ import annotations

from .themed_games import GAME_THEME_IDS, WAND_SPELLS

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

# Extra props for the Am I Cute Enough studio (accessory slot).
GAME_ACCESSORY_IDS: tuple[str, ...] = (
    "none",
    "wand",
    "heart_wand",
    "hero_hammer",
    "flower_bouquet",
)

__all__ = [
    "FINGER_TRAIL_DURATION_MS",
    "GAME_ACCESSORY_IDS",
    "GAME_COSTUME_IDS",
    "GAME_THEME_IDS",
    "INDEX_FINGER_TIP",
    "WAND_SPELLS",
]
