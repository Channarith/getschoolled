"""Convert CosyVoice ingest output into other TTS trainers' formats, with provenance.

Input is what scripts/cosyvoice_ingest.py writes under OUTPUT/04_cosyvoice/<split>/:
wav.scp, text, utt2spk, spk2utt, utt2lang and a meta.json whose "utterances" carry
source_url, duration_sec, snr_db and asr_engine (see cosyvoice_ingest/export.py).

Every clip keeps its source and a license status. Sources are third-party
YouTube/Vimeo channels with no recorded license or consent unless they are in the
allowlist (urls/licensed_sources.txt). Nothing unlicensed may ship: a clip is
``ship_ok`` only when allowlisted, and ``only_licensed`` drops the rest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import wave
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

THIRD_PARTY_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "m.youtube.com", "www.youtube.com")
STATEMENT = (
    "Audio from third-party YouTube/Vimeo channels. No license or consent is recorded for it. "
    "It is for internal experiments only and must not ship in the product unless the source "
    "appears in the licensed allowlist."
)


@dataclass
class Filters:
    min_seconds: float = 1.0
    max_seconds: float = 20.0
    min_snr_db: Optional[float] = 8.0
    min_asr_confidence: Optional[float] = None
    min_chars_per_second: float = 1.5
    max_chars_per_second: float = 45.0
    require_duration: bool = False
    dedupe_audio: bool = False
    only_licensed: bool = False
    val_fraction: float = 0.05


@dataclass
class Allowlist:
    entries: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Optional[Path]) -> "Allowlist":
        """Lines: source<TAB>license<TAB>note. ``source`` is a speaker/channel slug, a URL
        prefix, or a dataset marker such as ``fleurs``. ``#`` starts a comment."""
        out = cls()
        if not path or not Path(path).is_file():
            return out
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = [p.strip() for p in line.split("\t")]
            if parts and parts[0]:
                out.entries.append({"source": parts[0], "license": parts[1] if len(parts) > 1 else "", "note": parts[2] if len(parts) > 2 else ""})
        return out

    def match(self, clip: Dict[str, Any]) -> Optional[Dict[str, str]]:
        hay = " ".join(str(clip.get(k) or "") for k in ("source_url", "speaker", "channel", "audio_path")).lower()
        for entry in self.entries:
            key = entry["source"].lower()
            if key and (clip.get("speaker", "").lower() == key or clip.get("channel", "").lower() == key
                        or str(clip.get("source_url") or "").lower().startswith(key) or key in hay):
                return entry
        return None


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "x"


def wav_seconds(path: Path) -> Optional[float]:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (OSError, EOFError, wave.Error):
        return None


def discover_splits(paths: Iterable[Path]) -> List[Path]:
    """Directories that contain wav.scp (a ``train`` dir), searching below each input."""
    found: List[Path] = []
    for base in paths:
        base = Path(base).expanduser()
        if (base / "wav.scp").is_file():
            found.append(base)
        else:
            found.extend(sorted(p.parent for p in base.rglob("wav.scp")))
    seen, out = set(), []
    for p in found:
        if p.resolve() not in seen:
            seen.add(p.resolve())
            out.append(p)
    return out


def _read_kaldi(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                key, _, value = line.partition(" ")
                out[key] = value.strip()
    return out


def channel_of(split_dir: Path) -> str:
    """e.g. output/cosyvoice_zh_tw_gushitw/04_cosyvoice/train -> zh_tw_gushitw."""
    for part in reversed(split_dir.parts):
        if part.startswith("cosyvoice_"):
            return part[len("cosyvoice_"):]
    return split_dir.parent.parent.name or split_dir.name


def load_split(split_dir: Path) -> List[Dict[str, Any]]:
    wavs, texts = _read_kaldi(split_dir / "wav.scp"), _read_kaldi(split_dir / "text")
    spks, langs = _read_kaldi(split_dir / "utt2spk"), _read_kaldi(split_dir / "utt2lang")
    meta: Dict[str, Dict[str, Any]] = {}
    meta_path = split_dir / "meta.json"
    if meta_path.is_file():
        try:
            for u in json.loads(meta_path.read_text(encoding="utf-8")).get("utterances") or []:
                meta[str(u.get("utt_id"))] = u
        except ValueError:
            pass
    channel = channel_of(split_dir)
    rows = []
    for utt, wav in wavs.items():
        m = meta.get(utt, {})
        audio = Path(wav)
        if not audio.is_absolute():
            audio = (split_dir / audio)
        rows.append({
            "id": utt,
            "audio_path": str(audio),
            "text": texts.get(utt, m.get("text", "")),
            "lang": langs.get(utt) or m.get("language") or "",
            "speaker": spks.get(utt) or m.get("spk_id") or channel,
            "channel": channel,
            "duration_sec": m.get("duration_sec") or None,
            "snr_db": m.get("snr_db"),
            "asr_engine": m.get("asr_engine", ""),
            "asr_confidence": m.get("asr_confidence"),
            "source_url": m.get("source_url", ""),
            "split_dir": str(split_dir),
        })
    return rows


def source_kind(clip: Dict[str, Any]) -> str:
    host = (urlparse(clip.get("source_url") or "").hostname or "").lower()
    if host and any(host == h or host.endswith("." + h) for h in THIRD_PARTY_HOSTS):
        return "third_party_video"
    if "fleurs" in (clip.get("source_url") or "").lower() or "fleurs" in clip.get("audio_path", "").lower():
        return "public_corpus"
    return "unknown"


def _norm_text(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _file_sha(path: str) -> Optional[str]:
    try:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def filter_clips(clips: List[Dict[str, Any]], flt: Filters, allow: Allowlist) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept, rejected = [], []
    seen_text: set = set()
    seen_audio: set = set()
    for clip in clips:
        reasons: List[str] = []
        entry = allow.match(clip)
        clip["source_kind"] = source_kind(clip)
        clip["license_status"] = "allowlisted" if entry else "unconfirmed"
        clip["license"] = entry["license"] if entry else ""
        clip["consent"] = "see allowlist entry" if entry else "none recorded"
        clip["ship_ok"] = bool(entry)
        if flt.only_licensed and not entry:
            reasons.append("not_licensed")
        text = (clip.get("text") or "").strip()
        if not text:
            reasons.append("empty_text")
        if not os.path.isfile(clip["audio_path"]):
            reasons.append("missing_audio")
        dur = clip.get("duration_sec")
        if not dur and os.path.isfile(clip["audio_path"]):
            dur = wav_seconds(Path(clip["audio_path"]))
            clip["duration_sec"] = dur
        if dur is None:
            if flt.require_duration:
                reasons.append("unknown_duration")
        else:
            if dur < flt.min_seconds:
                reasons.append("too_short")
            if dur > flt.max_seconds:
                reasons.append("too_long")
            if text and dur > 0 and not (flt.min_chars_per_second <= len(text) / dur <= flt.max_chars_per_second):
                reasons.append("text_length_vs_duration")
        snr = clip.get("snr_db")
        if flt.min_snr_db is not None and snr is not None and snr < flt.min_snr_db:
            reasons.append("low_snr")
        conf = clip.get("asr_confidence")
        if flt.min_asr_confidence is not None and conf is not None and conf < flt.min_asr_confidence:
            reasons.append("low_asr_confidence")
        key = (clip["speaker"], _norm_text(text))
        if text and key in seen_text:
            reasons.append("duplicate_text")
        if flt.dedupe_audio and not reasons:
            sha = _file_sha(clip["audio_path"])
            if sha and sha in seen_audio:
                reasons.append("duplicate_audio")
            elif sha:
                seen_audio.add(sha)
        if reasons:
            rejected.append({"id": clip["id"], "speaker": clip["speaker"], "reasons": reasons})
        else:
            seen_text.add(key)
            kept.append(clip)
    return kept, rejected


def assign_split(clips: List[Dict[str, Any]], val_fraction: float) -> Dict[str, Any]:
    """Hold out whole speakers (channels) for validation; utterance-level if there is only one."""
    by_lang: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for c in clips:
        by_lang[c["lang"] or "unknown"][c["speaker"]].append(c)
    notes: List[str] = []
    for lang, speakers in by_lang.items():
        total = sum(len(v) for v in speakers.values())
        target = max(1, int(round(total * val_fraction))) if val_fraction > 0 and total >= 4 else 0
        if len(speakers) >= 2 and target:
            held = held_speakers = 0
            for spk in sorted(speakers, key=lambda s: hashlib.sha1(s.encode()).hexdigest()):
                if held >= target or held_speakers >= len(speakers) - 1:
                    break
                for c in speakers[spk]:
                    c["split"] = "val"
                held += len(speakers[spk])
                held_speakers += 1
        elif target:
            notes.append(f"{lang}: one speaker only, validation is an utterance-level hash split")
            for clip in speakers[next(iter(speakers))]:
                if int(hashlib.sha1(clip["id"].encode()).hexdigest(), 16) % 1000 < val_fraction * 1000:
                    clip["split"] = "val"
        for v in speakers.values():
            for c in v:
                c.setdefault("split", "train")
    return {"notes": notes}


def write_outputs(clips: List[Dict[str, Any]], rejected: List[Dict[str, Any]], out: Path, audio: str = "link") -> Dict[str, Any]:
    """manifest.jsonl, train/val.jsonl, fish/<split>/<speaker>/<utt>.wav|.lab, provenance."""
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as m, (out / "train.jsonl").open("w", encoding="utf-8") as tr, (out / "val.jsonl").open("w", encoding="utf-8") as va:
        for c in clips:
            rec = {
                "id": c["id"], "path": c["audio_path"], "text": c["text"], "lang": c["lang"], "speaker": c["speaker"],
                "channel": c["channel"], "split": c["split"], "duration_sec": c["duration_sec"], "snr_db": c["snr_db"],
                "asr_engine": c["asr_engine"], "source_url": c["source_url"],
                "provenance": {"source_kind": c["source_kind"], "license_status": c["license_status"], "license": c["license"],
                               "consent": c["consent"], "ship_ok": c["ship_ok"]},
            }
            line = json.dumps(rec, ensure_ascii=False) + "\n"
            m.write(line)
            (va if c["split"] == "val" else tr).write(line)
    (out / "rejected.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rejected[:50000]), encoding="utf-8")

    if audio != "none":
        for c in clips:
            folder = out / "fish" / c["split"] / safe_name(c["speaker"])
            folder.mkdir(parents=True, exist_ok=True)
            stem = safe_name(c["id"])
            (folder / f"{stem}.lab").write_text(c["text"].strip() + "\n", encoding="utf-8")
            dest = folder / f"{stem}.wav"
            if dest.exists() or dest.is_symlink():
                continue
            if audio == "copy":
                shutil.copyfile(c["audio_path"], dest)
            else:
                os.symlink(os.path.abspath(c["audio_path"]), dest)

    per_source: Dict[str, Dict[str, Any]] = {}
    for c in clips:
        d = per_source.setdefault(c["channel"] + "/" + c["speaker"], {
            "channel": c["channel"], "speaker": c["speaker"], "lang": c["lang"], "clips": 0, "seconds": 0.0,
            "source_kind": c["source_kind"], "license_status": c["license_status"], "license": c["license"],
            "source_urls": set()})
        d["clips"] += 1
        d["seconds"] += float(c["duration_sec"] or 0)
        if c["source_url"] and len(d["source_urls"]) < 3:
            d["source_urls"].add(c["source_url"])
    for d in per_source.values():
        d["hours"] = round(d["seconds"] / 3600, 3)
        d["source_urls"] = sorted(d["source_urls"])
    ship = [c for c in clips if c["ship_ok"]]
    report = {
        "statement": STATEMENT,
        "clips_kept": len(clips),
        "hours_kept": round(sum(float(c["duration_sec"] or 0) for c in clips) / 3600, 3),
        "clips_ship_ok": len(ship),
        "hours_ship_ok": round(sum(float(c["duration_sec"] or 0) for c in ship) / 3600, 3),
        "by_license_status": dict(Counter(c["license_status"] for c in clips)),
        "by_language": dict(Counter(c["lang"] or "unknown" for c in clips)),
        "by_split": dict(Counter(c["split"] for c in clips)),
        "rejected_by_reason": dict(Counter(r for x in rejected for r in x["reasons"])),
        "sources": sorted(per_source.values(), key=lambda d: -d["clips"]),
    }
    (out / "provenance.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "provenance.txt").write_text(render_provenance(report), encoding="utf-8")
    return report


def render_provenance(report: Dict[str, Any]) -> str:
    lines = [
        "VOICE DATASET PROVENANCE",
        report["statement"],
        "",
        f"kept {report['clips_kept']} clips, {report['hours_kept']} h; safe to ship: {report['clips_ship_ok']} clips, {report['hours_ship_ok']} h",
        f"licence status: {report['by_license_status']}",
        f"languages: {report['by_language']}   split: {report['by_split']}",
        f"rejected: {report['rejected_by_reason']}",
        "",
        f"{'CHANNEL/SPEAKER':<42} {'LANG':<6} {'CLIPS':>6} {'HOURS':>7} STATUS",
    ]
    for d in report["sources"][:60]:
        name = f"{d['channel']}/{d['speaker']}"
        lines.append(f"{name[:42]:<42} {d['lang'] or '-':<6} {d['clips']:>6} {d['hours']:>7} {d['license_status']} {d['license']}")
    return "\n".join(lines) + "\n"


def convert(
    inputs: Iterable[Path],
    out: Path,
    flt: Filters,
    allowlist: Optional[Path] = None,
    audio: str = "link",
) -> Dict[str, Any]:
    splits = discover_splits(inputs)
    if not splits:
        raise SystemExit("no wav.scp found under the given input(s)")
    out = Path(out)
    out_r = out.resolve()
    for s in splits:
        if out_r == s.resolve() or out_r in s.resolve().parents:
            raise SystemExit(f"refusing: output {out} would contain the input {s}")
    clips: List[Dict[str, Any]] = []
    for s in splits:
        clips.extend(load_split(s))
    allow = Allowlist.load(allowlist)
    kept, rejected = filter_clips(clips, flt, allow)
    split_notes = assign_split(kept, flt.val_fraction)
    report = write_outputs(kept, rejected, out, audio)
    report.update({"inputs": [str(s) for s in splits], "clips_seen": len(clips), "split_notes": split_notes["notes"]})
    (out / "provenance.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report
