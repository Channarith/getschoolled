"""Run NLLB and MADLAD together and keep the cleaner sentence.

Both models translate the line. Each result is translated back to the source
language, and the one whose round trip is closer to the original is kept.
When the scores are close, MADLAD wins, because its sentences are the cleaner
of the two at the same fidelity. One model is enough when the other is not
loaded.
"""

from __future__ import annotations

import difflib
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

_last = threading.local()
# One merged translation at a time. NLLB 3.3B and MADLAD 10B share one GPU;
# overlapping requests queue here instead of all generating at once and
# outliving the client's timeout.
_infer_lock = threading.Lock()


@dataclass(frozen=True)
class MergedTranslation:
    text: str
    chosen: str
    nllb_text: str
    madlad_text: str
    nllb_score: float
    madlad_score: float

    def to_dict(self) -> dict:
        return asdict(self)


def last_merge() -> MergedTranslation | None:
    return getattr(_last, "result", None)


def round_trip_score(source: str, back: str) -> float:
    left = " ".join((source or "").casefold().split())
    right = " ".join((back or "").casefold().split())
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def choose_translation(
    source: str,
    *,
    nllb_text: str,
    madlad_text: str,
    nllb_back: str,
    madlad_back: str,
) -> MergedTranslation:
    nllb_score = round_trip_score(source, nllb_back) if nllb_text else 0.0
    madlad_score = round_trip_score(source, madlad_back) if madlad_text else 0.0
    nllb_text = (nllb_text or "").strip()
    madlad_text = (madlad_text or "").strip()
    if nllb_text and not madlad_text:
        chosen, text = "nllb", nllb_text
    elif madlad_text and not nllb_text:
        chosen, text = "madlad", madlad_text
    elif not nllb_text and not madlad_text:
        raise RuntimeError("neither NLLB nor MADLAD returned a sentence")
    elif madlad_score + 0.03 >= nllb_score:
        chosen, text = "madlad", madlad_text
    else:
        chosen, text = "nllb", nllb_text
    result = MergedTranslation(
        text=text,
        chosen=chosen,
        nllb_text=nllb_text,
        madlad_text=madlad_text,
        nllb_score=round(nllb_score, 4),
        madlad_score=round(madlad_score, 4),
    )
    _last.result = result
    return result


def _safe_call(fn, text: str, source: str, target: str) -> str:
    try:
        return (fn(text, source=source, target=target) or "").strip()
    except Exception:
        return ""


def merged_translate(text: str, *, source: str, target: str) -> MergedTranslation:
    """Translate with both models at once, then round-trip both results."""
    clean = " ".join((text or "").split())
    if not clean:
        raise ValueError("translation text is empty")
    with _infer_lock:
        return _merged_translate_locked(clean, source=source, target=target)


def _merged_translate_locked(clean: str, *, source: str, target: str) -> MergedTranslation:
    from . import madlad, nllb

    _last.result = None
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="mt") as pool:
        nllb_future = pool.submit(_safe_call, nllb.translate_text, clean, source, target)
        madlad_future = pool.submit(_safe_call, madlad.translate_text, clean, source, target)
        nllb_text = nllb_future.result()
        madlad_text = madlad_future.result()
        back_nllb = pool.submit(
            _safe_call, nllb.translate_text, nllb_text, target, source
        ) if nllb_text else None
        back_madlad = pool.submit(
            _safe_call, madlad.translate_text, madlad_text, target, source
        ) if madlad_text else None
        nllb_back = back_nllb.result() if back_nllb is not None else ""
        madlad_back = back_madlad.result() if back_madlad is not None else ""
    return choose_translation(
        clean,
        nllb_text=nllb_text,
        madlad_text=madlad_text,
        nllb_back=nllb_back,
        madlad_back=madlad_back,
    )
