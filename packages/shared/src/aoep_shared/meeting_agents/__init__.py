"""Offline multi-agent lab for group video teaching (Meet / Zoom / Teams).

Simulates harvest → teach → bridge → multi-agent classroom without vendor SDKs.
"""

from .lab import MeetingAgentsLabResult, run_meeting_agents_lab

__all__ = ["MeetingAgentsLabResult", "run_meeting_agents_lab"]
