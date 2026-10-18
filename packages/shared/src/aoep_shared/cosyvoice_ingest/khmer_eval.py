"""Held-out scoring helpers for a Khmer CosyVoice candidate.

Character error rate, prompt pairing, and the win/keep decision are pure so
they can be tested without a GPU. Synthesis stays in
``scripts/spark_cosyvoice_khmer_eval.py``.
"""

from __future__ import annotations

import random
import unicodedata
from typing import Mapping, Sequence


# A clear win needs the CER to fall by at least this much. Smaller gaps stay
# on the previous candidate.
CER_MARGIN = 0.02
# Speaker cosine may dip by this much and still count as a win when CER drops.
SIM_FLOOR = 0.02
MIN_SCORED = 8


def normalize_cer_text(text: str) -> str:
    """Drop whitespace and punctuation. Keep letters so latin junk still counts."""
    chars: list[str] = []
    for ch in (text or "").casefold():
        if ch.isspace():
            continue
        if unicodedata.category(ch).startswith("P"):
            continue
        chars.append(ch)
    return "".join(chars)


def _levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    prev = list(range(len(right) + 1))
    for i, ca in enumerate(left, 1):
        cur = [i]
        for j, cb in enumerate(right, 1):
            insert = cur[j - 1] + 1
            delete = prev[j] + 1
            replace = prev[j - 1] + (ca != cb)
            cur.append(min(insert, delete, replace))
        prev = cur
    return prev[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    ref = normalize_cer_text(reference)
    hyp = normalize_cer_text(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / len(ref)


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values))


def metric_summary(rows: Sequence[Mapping]) -> dict:
    scored = [row for row in rows if row.get("ok")]
    cer_values = [float(row["cer"]) for row in scored]
    sim_values = [float(row["speaker_similarity"]) for row in scored]
    return {
        "scored": len(scored),
        "attempts": len(list(rows)),
        "cer": round(_mean(cer_values), 4) if scored else None,
        "speaker_similarity": round(_mean(sim_values), 4) if scored else None,
    }


def candidate_beats_baseline(baseline: Mapping, candidate: Mapping) -> dict:
    """True when CER drops by ``CER_MARGIN`` and similarity holds.

    Serving stays unchanged here. The live sidecar is CosyVoice-300M-SFT with
    enrolled speakers. This candidate is a CosyVoice-300M zero-shot LLM and
    has no ``spk2info``. Pointing the sidecar at it would make speaker-id
    ``/tts`` fail, so a metric win does not rewrite the serving config.
    """
    base_cer = baseline.get("cer")
    cand_cer = candidate.get("cer")
    base_sim = baseline.get("speaker_similarity")
    cand_sim = candidate.get("speaker_similarity")
    base_n = int(baseline.get("scored") or 0)
    cand_n = int(candidate.get("scored") or 0)
    reasons: list[str] = []
    if base_cer is None or cand_cer is None or base_sim is None or cand_sim is None:
        reasons.append("missing_metric")
    if base_n < MIN_SCORED or cand_n < MIN_SCORED:
        reasons.append("too_few_scored")
    elif cand_n < int(0.8 * base_n):
        reasons.append("candidate_scored_fewer")
    wins = False
    if not reasons:
        cer_ok = float(cand_cer) <= float(base_cer) - CER_MARGIN
        sim_ok = float(cand_sim) >= float(base_sim) - SIM_FLOOR
        wins = cer_ok and sim_ok
        if not cer_ok:
            reasons.append("cer_margin")
        if not sim_ok:
            reasons.append("similarity_drop")
    return {
        "wins": wins,
        "reasons": reasons,
        "cer_before": base_cer,
        "cer_after": cand_cer,
        "speaker_similarity_before": base_sim,
        "speaker_similarity_after": cand_sim,
        "promote_serving": False,
        "serving_config": "unchanged",
    }


def choose_prompts(
    train_ids: Sequence[str],
    holdout_ids: Sequence[str],
    utt2spk: Mapping[str, str],
    durations: Mapping[str, float],
    *,
    min_sec: float = 3.0,
    max_sec: float = 12.0,
    seed: int = 17,
) -> list[dict]:
    """Pair each held-out line with a different same-speaker prompt."""
    by_speaker: dict[str, list[str]] = {}
    for utt in train_ids:
        by_speaker.setdefault(str(utt2spk.get(utt, "")), []).append(utt)
    rng = random.Random(seed)
    pairs: list[dict] = []
    for utt in holdout_ids:
        speaker = str(utt2spk.get(utt, ""))
        pool = [
            prompt
            for prompt in by_speaker.get(speaker, [])
            if prompt != utt and min_sec <= float(durations.get(prompt, 0.0)) <= max_sec
        ]
        if not pool:
            pool = [prompt for prompt in by_speaker.get(speaker, []) if prompt != utt]
        if not pool:
            continue
        prompt = rng.choice(pool)
        pairs.append({"utt": utt, "prompt_utt": prompt, "speaker": speaker})
    return pairs


def choose_sample_utts(pairs: Sequence[Mapping], *, limit: int = 8, seed: int = 17) -> list[str]:
    """Spread a short listening set across speakers, then fill at random."""
    rng = random.Random(seed)
    by_speaker: dict[str, list[str]] = {}
    for pair in pairs:
        by_speaker.setdefault(str(pair.get("speaker") or ""), []).append(str(pair["utt"]))
    chosen: list[str] = []
    speakers = sorted(by_speaker)
    rng.shuffle(speakers)
    for speaker in speakers:
        if len(chosen) >= limit:
            break
        utt = rng.choice(by_speaker[speaker])
        if utt not in chosen:
            chosen.append(utt)
    rest = [str(pair["utt"]) for pair in pairs if str(pair["utt"]) not in chosen]
    rng.shuffle(rest)
    for utt in rest:
        if len(chosen) >= limit:
            break
        chosen.append(utt)
    return chosen[:limit]
