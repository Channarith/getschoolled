"""KSB framework for corporate courses (numpy-backed occupational standards)."""

from .framework import (
    DUTY_DTYPE,
    KSB_DTYPE,
    KSBStandard,
    load_all,
)

__all__ = ["KSB_DTYPE", "DUTY_DTYPE", "KSBStandard", "load_all"]
