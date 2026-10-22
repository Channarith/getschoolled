"""What is allowed to start again after a reboot on this Spark.

The last reboot brought Khmer CosyVoice back from the base weights and
started three ingest workers beside the STEM exam. That is the interruption
this policy refuses. STEM training and the 222-course translation resume.
Khmer stays held until the hold file is removed. Ingest stays at one worker
while the exam is alive.
"""

from __future__ import annotations

HOLD_FILENAME = "hold-voice-train"
# Two ingest workers only when the exam is idle and this much RAM is free.
INGEST_ROOMY_MB = 40960


def ingest_workers(free_mb: int, training_alive: bool) -> int:
    """How many CosyVoice ingest workers may run.

    Three workers after a reboot exhausted memory and killed the exam.
    One worker is the cap while STEM training is alive, or while free
    memory is under 40 GB. Two is the ceiling even when the machine is idle.
    """
    if training_alive or int(free_mb) < INGEST_ROOMY_MB:
        return 1
    return 2


def voice_train_allowed(hold_present: bool) -> bool:
    """Khmer fine-tune may load weights only when the hold file is absent."""
    return not hold_present
