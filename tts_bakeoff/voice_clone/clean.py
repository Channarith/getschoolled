"""Clean cloned-voice audio without damaging the voice. numpy only (ffmpeg is used only to read non-wav input).

  python3 -m tts_bakeoff.voice_clone.clean --in a.wav --out a.clean.wav [--mode synthesis|reference]
  python3 -m tts_bakeoff.voice_clone.clean --dir runs/2026-10-25-clones [--force]     # in place, raw kept in .raw/

Three places use it (all opt-out: GS_CLONE_CLEAN=0, --no-clean, --takes 1):
  reference   enrollment: high-pass, mains-hum notch, de-click, MILD spectral gate. The cleaned copy is kept only if it
              did not lose SNR, add clicks or shift the voice's tone colour (band profile within 1.5 dB); else the original stays.
  synthesis   clone output: gentle high-pass, hum notch, de-click, light gate, fades, loudness normalize (same safety check, 2.5 dB).
  best-of-N   synthesize N takes per sentence, keep the one with the lowest noise score; scores go to a sidecar JSON.

Non-destructive: the file before cleaning is kept at <folder>/.raw/<name>.wav (dot folders are hidden from the listening lab).
Noise score (lower is better) = 2*clicks + 1000*clipped_fraction + 0.15*(noise_floor_dBFS+80) + 2*gap_flatness + 0.1*(hum_dB-10)
[+ 10*word_error_rate when GS_CLONE_ASR=1 and openai-whisper is installed; that path is written but NOT run in CI].
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HOLD = ".raw"
VERSION = 1
BANDS = (125, 250, 500, 1000, 2000, 4000, 8000)
TIMBRE_LIMIT_DB = {"reference": 1.5, "synthesis": 2.5}


def enabled() -> bool:
    return os.environ.get("GS_CLONE_CLEAN", "1").strip().lower() not in ("0", "off", "no", "false")


def default_takes() -> int:
    try:
        return max(1, min(8, int(os.environ.get("GS_CLONE_TAKES", "3"))))
    except ValueError:
        return 3


# ---------------------------------------------------------------- framing / spectrum helpers
def _frame_db(x, rate: int, ms: float = 20.0):
    size = max(8, int(rate * ms / 1000))
    k = len(x) // size
    if k == 0:
        return np.zeros(0)
    f = x[: k * size].reshape(k, size).astype("float64")
    return 10 * np.log10((f**2).mean(axis=1) + 1e-12)


def _fft_size(rate: int) -> int:
    return int(2 ** round(np.log2(max(64, rate * 0.0213))))


def _stft(x, n: int, hop: int):
    w = np.hanning(n + 1)[:-1]
    xp = np.concatenate([np.zeros(n), x.astype("float64"), np.zeros(n + hop)])
    frames = 1 + (len(xp) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    return np.fft.rfft(xp[idx] * w, axis=1), w, len(xp)


def _istft(S, w, n: int, hop: int, total: int, length: int):
    fr = np.fft.irfft(S, n=n, axis=1) * w
    out, norm = np.zeros(total), np.zeros(total)
    for i in range(len(fr)):
        out[i * hop: i * hop + n] += fr[i]
        norm[i * hop: i * hop + n] += w**2
    out = out / np.maximum(norm, 1e-8)
    return out[n: n + length].astype("float32")


def _band_profile(x, rate: int):
    """Noise-corrected long-term spectrum per band (dB, level removed) from the loudest frames minus the quietest ones,
    plus which bands stand clearly (4x) above the noise. Removing noise therefore does not count as changing the voice."""
    n = _fft_size(rate)
    S, _, _ = _stft(x, n, n // 2)
    p = np.abs(S) ** 2
    e = p.sum(axis=1)
    core = np.arange(len(e))
    core = core[(core >= 2) & (core < len(e) - 2) & (e > 1e-9)]
    if len(core) < 10:
        return np.zeros(len(BANDS) - 1), np.zeros(len(BANDS) - 1, dtype=bool)
    order = core[np.argsort(e[core])]
    loud = p[order[int(0.6 * len(order)):]].mean(axis=0)
    quiet = p[order[: max(3, len(order) // 10)]].mean(axis=0)
    f = np.fft.rfftfreq(n, 1 / rate)
    vals, ok = [], []
    for lo, hi in zip(BANDS[:-1], BANDS[1:]):
        m = (f >= lo) & (f < min(hi, rate / 2))
        if not m.any():
            vals.append(np.nan)
            ok.append(False)
            continue
        lv, qv = loud[m].mean(), quiet[m].mean()
        vals.append(10 * np.log10(max(lv - qv, 1e-3 * lv) + 1e-14))
        ok.append(bool(lv > 4 * qv))
    return np.array(vals), np.array(ok)


def timbre_shift_db(a, b, rate: int) -> float:
    pa, ok = _band_profile(a, rate)
    pb, _ = _band_profile(b, rate)
    use = ok & np.isfinite(pa) & np.isfinite(pb)
    if use.sum() < 2:
        return 0.0
    return float(np.abs((pa[use] - pa[use].mean()) - (pb[use] - pb[use].mean())).max())


# ---------------------------------------------------------------- hum, high-pass
def detect_hum(x, rate: int):
    """(base_hz or None, prominence_dB of the fundamental, [harmonics worth notching]). Needs >= 1 s of audio."""
    if len(x) < rate:
        return None, 0.0, []
    P = np.abs(np.fft.rfft(x.astype("float64") * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / rate)

    def prom(f0):
        band = (f >= f0 - 1) & (f <= f0 + 1)
        ring = ((f >= f0 - 12) & (f < f0 - 4)) | ((f > f0 + 4) & (f <= f0 + 12))
        if not band.any() or not ring.any():
            return 0.0
        return float(10 * np.log10(P[band].max() / (np.median(P[ring]) + 1e-20)))

    best = max((50, 60), key=lambda b: prom(b))
    db = prom(best)
    if db < 15:
        return None, db, []
    return best, db, [best * k for k in (1, 2, 3, 4) if best * k < rate / 2 and prom(best * k) >= 10]


def _fft_filter(x, rate: int, hp_hz: float, notches=()):
    X = np.fft.rfft(x.astype("float64"))
    f = np.fft.rfftfreq(len(x), 1 / rate)
    h = 1 / np.sqrt(1 + (hp_hz / np.maximum(f, 1e-3)) ** 8) if hp_hz else np.ones_like(f)
    for f0 in notches:
        h = h * (1 - 0.95 * np.exp(-0.5 * ((f - f0) / 1.2) ** 2))
    return np.fft.irfft(X * h, n=len(x)).astype("float32")


# ---------------------------------------------------------------- clicks
def _runs(mask):
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return np.where(d == 1)[0], np.where(d == -1)[0]


def find_clicks(x, rate: int):
    """Short, isolated impulses: residual against a 7-sample median far above the local residual level."""
    if len(x) < 64:
        return []
    xp = np.pad(x.astype("float64"), 3, mode="edge")
    med = np.median(np.lib.stride_tricks.sliding_window_view(xp, 7), axis=1)
    a = np.abs(x - med)
    blk = max(64, int(rate * 0.005))
    nb = len(a) // blk
    if nb == 0:
        return []
    m = np.median(a[: nb * blk].reshape(nb, blk), axis=1)
    m = np.maximum(m, np.maximum(np.roll(m, 1), np.roll(m, -1)))
    sig = np.concatenate([np.repeat(m, blk), np.full(len(a) - nb * blk, m[-1])])
    peak = a[: nb * blk].reshape(nb, blk).max(axis=1)
    ctx = np.median(np.stack([np.roll(peak, k) for k in range(-3, 4)]), axis=0)
    ctx = np.concatenate([np.repeat(ctx, blk), np.full(len(a) - nb * blk, ctx[-1])])
    # an extra spike: far above the noise level AND 3x the usual peak of the blocks around it (voice pulses repeat, clicks do not)
    mask = (a > 8 * 1.4826 * sig + 0.03) & (a > 3 * ctx)
    mask = np.convolve(mask.astype(np.int8), np.ones(5, np.int8), "same") > 0
    s, e = _runs(mask)
    return [(int(i), int(j)) for i, j in zip(s, e) if j - i <= 12 and (i > 0 and j < len(x))]


def declick(x, rate: int):
    ev = find_clicks(x, rate)
    if not ev:
        return x, 0
    bad = np.zeros(len(x), dtype=bool)
    for i, j in ev:
        bad[i:j] = True
    idx = np.arange(len(x))
    y = x.copy()
    y[bad] = np.interp(idx[bad], idx[~bad], x[~bad]).astype(x.dtype)
    return y, len(ev)


# ---------------------------------------------------------------- spectral gate
def spectral_gate(x, rate: int, strength: float, floor_db: float):
    """Mild spectral subtraction: noise profile from the quietest frames, gain never below floor_db (so timbre survives)."""
    n = _fft_size(rate)
    hop = n // 4
    S, w, total = _stft(x, n, hop)
    mag = np.abs(S)
    e = (mag**2).mean(axis=1)
    core = np.arange(len(e))
    core = core[(core >= 4) & (core < len(e) - 4) & (e > 1e-9)]
    if len(core) < 16:
        return x
    quiet = core[np.argsort(e[core])[: max(8, len(core) // 10)]]
    noise = np.sqrt((mag[quiet] ** 2).mean(axis=0))
    noise = np.convolve(noise, np.ones(3) / 3, mode="same")
    gain = np.clip(1 - strength * noise[None, :] / (mag + 1e-9), 10 ** (floor_db / 20), 1.0)
    g = np.pad(gain, ((1, 1), (0, 0)), mode="edge")
    gain = (g[:-2] + g[1:-1] + g[2:]) / 3
    return _istft(S * gain, w, n, hop, total, len(x))


# ---------------------------------------------------------------- metrics
def _gap_flatness(x, rate: int) -> float:
    n = 512
    k = len(x) // n
    if k < 8:
        return 0.0
    fr = x[: k * n].reshape(k, n).astype("float64")
    e = (fr**2).mean(axis=1)
    live = np.where(e > 1e-9)[0]
    if len(live) == 0:
        return 0.0
    pick = live[np.argsort(e[live])[: max(2, int(0.15 * len(live)))]]
    P = np.abs(np.fft.rfft(fr[pick] * np.hanning(n), axis=1)) ** 2
    P = P[:, max(1, int(100 / (rate / n))):] + 1e-18
    flat = np.exp(np.log(P).mean(axis=1)) / P.mean(axis=1)
    return float(flat.mean())


def error_rate(ref: str, hyp: str, chars: bool = False) -> float:
    norm = lambda s: re.sub(r"[^\w\s]", "", s.casefold())  # noqa: E731
    r, h = norm(ref), norm(hyp)
    r, h = (list(r.replace(" ", "")), list(h.replace(" ", ""))) if chars else (r.split(), h.split())
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, a in enumerate(r, 1):
        cur = [i]
        for j, b in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a != b)))
        prev = cur
    return prev[-1] / len(r)


_ASR: dict = {}


def asr_wer(path, text: str, lang: str):
    """Optional round-trip check; off unless GS_CLONE_ASR=1 and openai-whisper imports. None when unavailable."""
    if os.environ.get("GS_CLONE_ASR", "0") != "1":
        return None
    try:
        import whisper
    except Exception:  # noqa: BLE001
        return None
    model = _ASR.setdefault("m", whisper.load_model(os.environ.get("GS_CLONE_ASR_MODEL", "base")))
    hyp = model.transcribe(str(path), language=lang)["text"]
    return error_rate(text, hyp, chars=lang in ("zh", "yue", "ja", "th", "km"))


def analyze(x, rate: int, wer: float | None = None) -> dict:
    from .enroll import snr_db

    db = _frame_db(x, rate)
    floor = float(np.percentile(db, 10)) if len(db) >= 10 else (float(db.min()) if len(db) else -120.0)
    clicks = len(find_clicks(x, rate))
    clip = float((np.abs(x) >= 0.99).mean()) if len(x) else 0.0
    flat = _gap_flatness(x, rate)
    hum = detect_hum(x, rate)[1]
    score = (2 * clicks + 1000 * clip + 0.15 * max(0.0, floor + 80) + 2 * flat + 0.1 * max(0.0, hum - 10)
             + (10 * wer if wer is not None else 0.0))
    out = {"snr_db": round(snr_db(x, rate), 1), "noise_floor_dbfs": round(floor, 1), "clicks": clicks,
           "clip_pct": round(100 * clip, 3), "gap_flatness": round(flat, 3), "hum_db": round(max(0.0, hum), 1),
           "score": round(score, 2)}
    if wer is not None:
        out["wer"] = round(wer, 3)
    return out


# ---------------------------------------------------------------- the two cleaners
def _normalize(x, target_dbfs: float = -20.0):
    rms = float(np.sqrt((x.astype("float64") ** 2).mean()) + 1e-9)
    gain = min(10 ** (target_dbfs / 20) / rms, 0.97 / (float(np.abs(x).max()) + 1e-9))
    return (x * gain).astype("float32")


def _clean(x, rate: int, mode: str):
    x = np.asarray(x, dtype="float32")
    before = analyze(x, rate)
    base, _, notches = detect_hum(x, rate)
    hp, strength, floor = (70, 0.8, -8.0) if mode == "reference" else (60, 0.6, -6.0)
    y = _fft_filter(x, rate, hp, notches)
    y, fixed = declick(y, rate)
    y = spectral_gate(y, rate, strength, floor)
    steps = [f"high-pass {hp} Hz"] + ([f"hum notch {base} Hz x{len(notches)}"] if notches else []) + \
            [f"de-click ({fixed} fixed)", f"gate {strength}/{floor:g} dB"]
    if mode == "synthesis":
        fi, fo = int(rate * 0.008), int(rate * 0.025)
        if len(y) > fi + fo:
            y[:fi] *= (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fi))).astype("float32")
            y[-fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo))).astype("float32")
        y = _normalize(y)
        steps += ["fades 8/25 ms", "normalize -20 dBFS"]
    after = analyze(y, rate)
    shift = timbre_shift_db(x, y, rate)
    reasons = []
    if after["snr_db"] < before["snr_db"] - 0.5:
        reasons.append(f"SNR fell {before['snr_db']} -> {after['snr_db']} dB")
    if after["clicks"] > before["clicks"]:
        reasons.append("more clicks after cleaning")
    if shift > TIMBRE_LIMIT_DB[mode]:
        reasons.append(f"tone colour moved {shift:.1f} dB (limit {TIMBRE_LIMIT_DB[mode]})")
    kept = not reasons
    return (y if kept else x), {"mode": mode, "kept_cleaned": kept, "reasons": reasons, "steps": steps,
                                "timbre_shift_db": round(shift, 2), "before": before, "after": after if kept else before}


def clean_reference(x, rate: int):
    return _clean(x, rate, "reference")


def clean_synthesis(x, rate: int):
    return _clean(x, rate, "synthesis")


# ---------------------------------------------------------------- files
def load_audio(path):
    from .enroll import read_wav

    try:
        return read_wav(Path(path))
    except Exception:  # noqa: BLE001 - not a 16-bit pcm wav: let ffmpeg convert
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t) / "in.wav"
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-sample_fmt", "s16", str(tmp)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"cannot read {path}: {r.stderr[:200]}")
            return read_wav(tmp)


def raw_path(p: Path) -> Path:
    return p.parent / HOLD / p.name


def sidecar_path(p: Path) -> Path:
    return p.parent / HOLD / (p.stem + ".clean.json")


def clean_file(src, dst=None, mode: str = "synthesis", force: bool = False) -> dict:
    """Clean src. With no dst (or dst == src) the file is replaced in place and the original kept in .raw/ (re-runs start from it)."""
    from tts_bakeoff.adapters.base import write_wav

    src = Path(src)
    in_place = dst is None or Path(dst) == src
    dst = src if in_place else Path(dst)
    read_from = src
    if in_place:
        hold = raw_path(src)
        if not hold.exists():
            hold.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, hold)
        elif sidecar_path(src).exists() and not force:
            return {"skipped": True, "file": str(src)}
        read_from = hold
    x, rate = load_audio(read_from)
    y, rep = _clean(x, rate, mode)
    write_wav(dst, y, rate)
    rep.update({"file": str(src), "sample_rate": rate, "version": VERSION})
    if in_place:
        sidecar_path(src).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    return rep


def clean_dir(root, mode: str = "synthesis", force: bool = False) -> dict:
    tot = {"files": 0, "cleaned": 0, "kept_original": 0, "skipped": 0, "clicks_fixed": 0}
    root = Path(root)
    for p in sorted(root.rglob("*.wav")):
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        tot["files"] += 1
        rep = clean_file(p, mode=mode, force=force)
        if rep.get("skipped"):
            tot["skipped"] += 1
            continue
        tot["cleaned" if rep["kept_cleaned"] else "kept_original"] += 1
        tot["clicks_fixed"] += max(0, rep["before"]["clicks"] - rep["after"]["clicks"])
        print(f"{'cleaned' if rep['kept_cleaned'] else 'KEPT ORIGINAL'} {p.relative_to(root)}  score {rep['before']['score']} -> "
              f"{rep['after']['score']}" + ("" if rep["kept_cleaned"] else "  (" + "; ".join(rep["reasons"]) + ")"), flush=True)
    return tot


# ---------------------------------------------------------------- synthesis with best-of-N
def synthesize_best_of(adapter, text: str, lang: str, out_wav, takes: int | None = None, clean: bool | None = None) -> dict:
    """adapter.synthesize() N times, keep the cleanest take, then clean it. takes=1 and clean=False is the plain old call."""
    out = Path(out_wav)
    takes = default_takes() if takes is None else max(1, takes)
    clean = enabled() if clean is None else clean
    if takes == 1 and not clean:
        return adapter.synthesize(text, lang, out)
    hold = out.parent / HOLD
    hold.mkdir(parents=True, exist_ok=True)
    results, scores, last_exc = [], [], None
    for k in range(takes):
        tmp = hold / f"{out.stem}.take{k}.wav"
        try:
            r = adapter.synthesize(text, lang, tmp)
        except Exception as exc:  # noqa: BLE001 - one bad take is fine while another works
            last_exc = exc
            continue
        x, rate = load_audio(tmp)
        wer = asr_wer(tmp, text, lang) if takes > 1 else None
        results.append((k, tmp, r))
        scores.append({"take": k, **analyze(x, rate, wer)})
    if not results:
        raise last_exc  # type: ignore[misc]
    best = min(range(len(results)), key=lambda i: scores[i]["score"])
    k, tmp, row = results[best]
    row = dict(row)
    row.update({"takes": len(results), "chosen_take": k, "noise_score": scores[best]["score"]})
    rep = {"takes": scores, "chosen": k, "version": VERSION}
    if clean:
        shutil.move(str(tmp), str(raw_path(out)))
        rep.update(clean_file(out, mode="synthesis", force=True))
        row["noise_score_cleaned"] = rep["after"]["score"]
        row["cleaned"] = rep["kept_cleaned"]
    else:
        shutil.move(str(tmp), str(out))
    for _, t, _ in results:
        t.unlink(missing_ok=True)
    sidecar_path(out).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    return row


# ---------------------------------------------------------------- CLI
def format_report(rep: dict) -> str:
    b, a = rep["before"], rep["after"]
    rows = [("SNR (dB)", "snr_db"), ("noise floor (dBFS)", "noise_floor_dbfs"), ("clicks", "clicks"), ("clipped (%)", "clip_pct"),
            ("gap flatness", "gap_flatness"), ("hum (dB)", "hum_db"), ("noise score (lower is better)", "score")]
    lines = [f"{rep.get('file', '')}  [{rep['mode']}]  {'CLEANED' if rep['kept_cleaned'] else 'ORIGINAL KEPT'}",
             f"{'metric':32}{'before':>10}{'after':>10}"]
    lines += [f"{name:32}{b[key]:>10}{a[key]:>10}" for name, key in rows]
    lines.append("steps: " + ", ".join(rep["steps"]) + f";  tone-colour shift {rep['timbre_shift_db']} dB")
    if rep["reasons"]:
        lines.append("kept the original because: " + "; ".join(rep["reasons"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src")
    ap.add_argument("--out")
    ap.add_argument("--dir", help="clean every .wav under this folder in place (originals kept in .raw/)")
    ap.add_argument("--mode", choices=("synthesis", "reference"), default="synthesis")
    ap.add_argument("--force", action="store_true", help="redo files that were already cleaned (starts again from .raw/)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.dir:
        tot = clean_dir(a.dir, a.mode, a.force)
        print(json.dumps(tot) if a.json else "done: " + ", ".join(f"{k} {v}" for k, v in tot.items()))
        return 0
    if not a.src:
        ap.error("give --in FILE (and --out FILE) or --dir FOLDER")
    rep = clean_file(a.src, a.out, a.mode, a.force)
    if rep.get("skipped"):
        print(f"{a.src}: already cleaned (use --force to redo)")
        return 0
    print(json.dumps(rep, indent=1) if a.json else format_report(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
