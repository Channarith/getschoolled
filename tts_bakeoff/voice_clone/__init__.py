"""Consent-gated voice cloning for people at the company (owner and employees).

A voice can be enrolled and synthesized only if a consent record exists for that person, is not revoked, covers the
scope, and its audio still matches the hashes recorded at enrollment. Voices live in GS_VOICES_DIR (default ~/voices),
never in git. See docs/voice-cloning.txt.
"""
