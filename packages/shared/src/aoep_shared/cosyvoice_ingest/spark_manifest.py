"""Point-in-time CosyVoice training manifests for the Spark box.

Scans channel ``report.json`` files. A channel is passing only when the
top-level ``ok`` field is true. The scan root is never written. Duplicate
waveforms (same sha256) are dropped so mirrored channels are not trained twice.

Salane / Sala is the live class voice id, not an ingest language pool. A
speaker counts only when its id is ``sala`` or ``salane`` (optional suffix).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .export import build_spk2utt, render_train_handoff
from .merge import merge_cosyvoice_recipes

# LibriTTS-scale CosyVoice recipes train for hours, not minutes. Below this
# floor a run cannot learn a speaker; Khmer still gets one epoch as a
# pipeline proof, Salane does not.
MEANINGFUL_MIN_UTTERANCES = 100
MEANINGFUL_MIN_SECONDS = 20 * 60

_SALANE_SPEAKER = re.compile(r"^(?:sala|salane)(?:[_.-].*)?$", re.IGNORECASE)
_COMPOUND_LANGS = (
    "zh_yue",
    "zh_tw",
    "zh_cn",
    "en_au",
    "en_gb",
    "en_us",
    "pt_br",
)


@dataclass
class ChannelRecord:
    name: str
    ok: bool
    utterances: int
    language: str
    recipe_dir: str
    report_path: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ok": self.ok,
            "utterances": self.utterances,
            "language": self.language,
            "recipe_dir": self.recipe_dir,
            "report_path": self.report_path,
        }


def is_salane_speaker(speaker_id: str) -> bool:
    return bool(_SALANE_SPEAKER.match((speaker_id or "").strip()))


def training_decision(name: str, utterances: int, seconds: float) -> dict:
    """Khmer always attempts one epoch. Salane trains only above the floor."""
    meaningful = (
        int(utterances) >= MEANINGFUL_MIN_UTTERANCES
        and float(seconds) >= MEANINGFUL_MIN_SECONDS
    )
    run = meaningful or name == "km"
    if utterances <= 0 or seconds <= 0:
        run = False
    return {
        "name": name,
        "utterances": int(utterances),
        "seconds": round(float(seconds), 3),
        "meaningful": meaningful,
        "run": run,
        "min_utterances": MEANINGFUL_MIN_UTTERANCES,
        "min_seconds": MEANINGFUL_MIN_SECONDS,
    }


def wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            if rate <= 0:
                return 0.0
            return handle.getnframes() / float(rate)
    except (wave.Error, EOFError, OSError):
        return 0.0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_kaldi_map(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            continue
        out[parts[0]] = parts[1]
    return out


def _write_kaldi_map(path: Path, mapping: Mapping[str, str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for key in sorted(mapping):
            handle.write(f"{key} {mapping[key]}\n")


def _language_from_name(name: str) -> str:
    rest = name[len("cosyvoice_") :] if name.startswith("cosyvoice_") else name
    for compound in _COMPOUND_LANGS:
        if rest == compound or rest.startswith(compound + "_"):
            return compound
    token = rest.split("_", 1)[0].strip().lower()
    return token or "und"


def _recipe_language(recipe_dir: Path, channel_name: str) -> str:
    meta_path = recipe_dir / "meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            lang = str(meta.get("language") or "").strip().lower()
            if lang:
                return lang
        except (OSError, json.JSONDecodeError):
            pass
    return _language_from_name(channel_name)


def _recipe_dir_for(channel_dir: Path, report: Mapping[str, object]) -> Optional[Path]:
    raw = str(report.get("recipe_dir") or "").strip()
    if raw:
        candidate = Path(raw)
        if (candidate / "wav.scp").is_file():
            return candidate
    fallback = channel_dir / "04_cosyvoice" / "train"
    if (fallback / "wav.scp").is_file():
        return fallback
    return None


def scan_channel_reports(scan_root: Path) -> tuple[List[ChannelRecord], int]:
    """Read ``cosyvoice_*/report.json``. Skip ``*_merged``. Return (rows, unreadable)."""
    rows: List[ChannelRecord] = []
    unreadable = 0
    root = Path(scan_root)
    for report_path in sorted(root.glob("cosyvoice_*/report.json")):
        channel_dir = report_path.parent
        if channel_dir.name.endswith("_merged"):
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            unreadable += 1
            continue
        if not isinstance(report, dict):
            unreadable += 1
            continue
        recipe = _recipe_dir_for(channel_dir, report)
        recipe_s = str(recipe.resolve()) if recipe else ""
        try:
            utterances = int(report.get("utterances") or 0)
        except (TypeError, ValueError):
            utterances = 0
        if recipe is not None:
            listed = len(_read_kaldi_map(recipe / "wav.scp"))
            if listed:
                utterances = listed
        language = _recipe_language(recipe, channel_dir.name) if recipe else _language_from_name(
            channel_dir.name
        )
        rows.append(
            ChannelRecord(
                name=channel_dir.name,
                ok=report.get("ok") is True,
                utterances=utterances,
                language=language,
                recipe_dir=recipe_s,
                report_path=str(report_path.resolve()),
            )
        )
    return rows, unreadable


def dedupe_recipe_by_audio_hash(recipe_dir: Path) -> dict:
    """Drop later utterances whose waveform sha256 was already kept.

    Missing files are dropped too. Rewrites the Kaldi lists in place.
    """
    recipe = Path(recipe_dir)
    wav = _read_kaldi_map(recipe / "wav.scp")
    text = _read_kaldi_map(recipe / "text")
    utt2spk = _read_kaldi_map(recipe / "utt2spk")
    utt2lang = _read_kaldi_map(recipe / "utt2lang")
    kept_wav: Dict[str, str] = {}
    kept_text: Dict[str, str] = {}
    kept_spk: Dict[str, str] = {}
    kept_lang: Dict[str, str] = {}
    seen: Dict[str, str] = {}
    dropped_dup = 0
    dropped_missing = 0
    seconds = 0.0
    for utt_id in sorted(wav):
        transcript = (text.get(utt_id) or "").strip()
        if not transcript:
            dropped_missing += 1
            continue
        audio = Path(wav[utt_id])
        if not audio.is_file():
            dropped_missing += 1
            continue
        digest = _sha256_file(audio)
        if digest in seen:
            dropped_dup += 1
            continue
        seen[digest] = utt_id
        kept_wav[utt_id] = str(audio.resolve())
        kept_text[utt_id] = transcript
        kept_spk[utt_id] = utt2spk.get(utt_id) or "spk"
        kept_lang[utt_id] = utt2lang.get(utt_id) or "und"
        seconds += wav_duration_seconds(audio)
    _write_lists(recipe, kept_wav, kept_text, kept_spk, kept_lang)
    return {
        "utterances": len(kept_wav),
        "speakers": len(build_spk2utt(kept_spk)),
        "seconds": round(seconds, 3),
        "dropped_duplicate_audio": dropped_dup,
        "dropped_missing": dropped_missing,
    }


def _write_lists(
    recipe: Path,
    wav: Mapping[str, str],
    text: Mapping[str, str],
    utt2spk: Mapping[str, str],
    utt2lang: Mapping[str, str],
) -> None:
    recipe.mkdir(parents=True, exist_ok=True)
    _write_kaldi_map(recipe / "wav.scp", wav)
    _write_kaldi_map(recipe / "text", text)
    _write_kaldi_map(recipe / "utt2spk", utt2spk)
    _write_kaldi_map(recipe / "utt2lang", utt2lang)
    spk2utt = build_spk2utt(dict(utt2spk))
    with (recipe / "spk2utt").open("w", encoding="utf-8") as handle:
        for spk in sorted(spk2utt):
            handle.write(f"{spk} {' '.join(spk2utt[spk])}\n")


def copy_recipe_audio(recipe_dir: Path, audio_dir: Path) -> int:
    """Copy referenced wavs next to the recipe and point wav.scp at the copies."""
    import shutil

    recipe = Path(recipe_dir)
    dest = Path(audio_dir)
    dest.mkdir(parents=True, exist_ok=True)
    wav = _read_kaldi_map(recipe / "wav.scp")
    rewritten: Dict[str, str] = {}
    copied = 0
    for utt_id, src in wav.items():
        source = Path(src)
        target = dest / f"{utt_id}.wav"
        if source.is_file():
            shutil.copyfile(source, target)
            copied += 1
            rewritten[utt_id] = str(target.resolve())
        else:
            rewritten[utt_id] = src
    _write_kaldi_map(recipe / "wav.scp", rewritten)
    return copied


def _rewrite_meta_and_handoff(
    recipe: Path,
    *,
    language: str,
    sources: Sequence[str],
    stats: Mapping[str, object],
    cosyvoice_repo: Optional[Path],
    note: str,
) -> str:
    meta = {
        "format": "cosyvoice_kaldi_lists_merged",
        "split": "train",
        "language": language,
        "utterance_count": stats.get("utterances", 0),
        "speaker_count": stats.get("speakers", 0),
        "duration_seconds": stats.get("seconds", 0),
        "dropped_duplicate_audio": stats.get("dropped_duplicate_audio", 0),
        "dropped_missing": stats.get("dropped_missing", 0),
        "sources": list(sources),
        "note": note,
    }
    (recipe / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    handoff = recipe / "TRAIN_HANDOFF.txt"
    handoff.write_text(
        render_train_handoff(
            data_dir=recipe,
            cosyvoice_repo=cosyvoice_repo,
            split_name="train",
            has_instruct=False,
        ),
        encoding="utf-8",
    )
    return str(handoff.resolve())


def _merge_group(
    sources: Sequence[Path],
    dest_recipe: Path,
    *,
    language: str,
    cosyvoice_repo: Optional[Path],
    copy_audio_to: Optional[Path],
    note: str,
) -> dict:
    report = merge_cosyvoice_recipes(
        sources,
        dest_recipe,
        split_name="train",
        language=language,
        cosyvoice_repo=cosyvoice_repo,
    )
    stats = dedupe_recipe_by_audio_hash(Path(report.dest_dir))
    if copy_audio_to is not None and stats["utterances"]:
        stats["audio_files_copied"] = copy_recipe_audio(Path(report.dest_dir), copy_audio_to)
    handoff = _rewrite_meta_and_handoff(
        Path(report.dest_dir),
        language=language,
        sources=report.sources,
        stats=stats,
        cosyvoice_repo=cosyvoice_repo,
        note=note,
    )
    return {
        "language": language,
        "channels": [Path(src).parent.parent.name for src in report.sources],
        "utterances": stats["utterances"],
        "speakers": stats["speakers"],
        "seconds": stats["seconds"],
        "dropped_duplicate_audio": stats["dropped_duplicate_audio"],
        "dropped_missing": stats["dropped_missing"],
        "recipe": str(Path(report.dest_dir).resolve()),
        "train_handoff": handoff,
        "audio_files_copied": stats.get("audio_files_copied", 0),
    }


def count_salane(scan_root: Path, voices_root: Optional[Path] = None) -> dict:
    utterances = 0
    seconds = 0.0
    speakers: set[str] = set()
    for recipe in _iter_recipe_dirs(scan_root):
        utt2spk = _read_kaldi_map(recipe / "utt2spk")
        wav = _read_kaldi_map(recipe / "wav.scp")
        for utt_id, spk in utt2spk.items():
            if not is_salane_speaker(spk):
                continue
            utterances += 1
            speakers.add(spk)
            audio = Path(wav.get(utt_id) or "")
            if audio.is_file():
                seconds += wav_duration_seconds(audio)
    voice_refs = 0
    if voices_root is not None and Path(voices_root).is_dir():
        for folder in ("sala", "salane"):
            base = Path(voices_root) / folder
            if not base.is_dir():
                continue
            voice_refs += sum(1 for path in base.rglob("*") if path.is_file())
    return {
        "training_utterances": utterances,
        "duration_seconds": round(seconds, 3),
        "speakers": sorted(speakers),
        "voice_reference_files": voice_refs,
        "note": (
            "Sala/Salane is the live class voice id, not a CosyVoice language pool. "
            "Zero utterances means there is no enrolled reference corpus to fine-tune."
        ),
    }


def _iter_recipe_dirs(scan_root: Path) -> Iterable[Path]:
    root = Path(scan_root)
    for wav_scp in sorted(root.glob("cosyvoice_*/04_cosyvoice/train/wav.scp")):
        if wav_scp.parents[2].name.endswith("_merged"):
            continue
        yield wav_scp.parent


def build_spark_manifests(
    scan_root: Path,
    dest_root: Path,
    *,
    cosyvoice_repo: Optional[Path] = None,
    voices_root: Optional[Path] = None,
) -> dict:
    """Merge passing channels per language and a deduped Khmer export set.

    Writes only under ``dest_root``. ``scan_root`` is read.
    """
    scan_root = Path(scan_root)
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    channels, unreadable = scan_channel_reports(scan_root)
    passing = [row for row in channels if row.ok and row.utterances > 0 and row.recipe_dir]
    exported = [row for row in channels if row.utterances > 0 and row.recipe_dir]
    by_lang: Dict[str, List[ChannelRecord]] = {}
    for row in passing:
        by_lang.setdefault(row.language or "und", []).append(row)

    passing_out: Dict[str, dict] = {}
    for language in sorted(by_lang):
        sources = [Path(row.recipe_dir) for row in by_lang[language]]
        dest = dest_root / "passing" / language / "04_cosyvoice" / "train"
        passing_out[language] = _merge_group(
            sources,
            dest,
            language=language,
            cosyvoice_repo=cosyvoice_repo,
            copy_audio_to=None,
            note="Passing channels only (top-level report ok true), deduped by audio sha256.",
        )

    km_rows = [
        row
        for row in exported
        if row.language == "km" or row.name.startswith("cosyvoice_km_")
    ]
    km_dest = dest_root / "km_exported" / "04_cosyvoice" / "train"
    km_summary = _merge_group(
        [Path(row.recipe_dir) for row in km_rows],
        km_dest,
        language="km",
        cosyvoice_repo=cosyvoice_repo,
        copy_audio_to=dest_root / "km_exported" / "audio",
        note=(
            "All Khmer channel trees with exported utterances, including report "
            "ok false. Deduped by audio sha256 and copied so a live ingest rewrite "
            "cannot change the training files. Not a promotion into the TTS server."
        ),
    )
    salane = count_salane(scan_root, voices_root)
    decision_km = training_decision("km", km_summary["utterances"], km_summary["seconds"])
    decision_salane = training_decision(
        "salane", salane["training_utterances"], float(salane["duration_seconds"])
    )
    false_rows = [row for row in exported if not row.ok]
    census = {
        "scan_root": str(scan_root.resolve()),
        "dest_root": str(dest_root.resolve()),
        "passing_definition": "top-level report.json ok is true and the recipe lists utterances",
        "channels_with_reports": len(channels),
        "unreadable_reports": unreadable,
        "passing_channels": len(passing),
        "passing_utterances_reported": sum(row.utterances for row in passing),
        "passing_utterances_deduped": sum(item["utterances"] for item in passing_out.values()),
        "passing_seconds_deduped": round(
            sum(item["seconds"] for item in passing_out.values()), 3
        ),
        "exported_channels": len(exported),
        "exported_utterances_reported": sum(row.utterances for row in exported),
        "exported_but_not_ok_channels": len(false_rows),
        "exported_but_not_ok_utterances": sum(row.utterances for row in false_rows),
        "by_language": passing_out,
        "km_exported": km_summary,
        "salane": salane,
        "decision": {"km": decision_km, "salane": decision_salane},
        "passing_channel_names": [row.name for row in passing],
    }
    (dest_root / "census.json").write_text(
        json.dumps(census, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_counts_txt(dest_root / "COUNTS.txt", census)
    return census


def _write_counts_txt(path: Path, census: Mapping[str, object]) -> None:
    lines = [
        "Spark CosyVoice manifest counts",
        "scan_root: {}".format(census.get("scan_root")),
        "passing_channels: {}".format(census.get("passing_channels")),
        "passing_utterances_reported: {}".format(census.get("passing_utterances_reported")),
        "passing_utterances_deduped: {}".format(census.get("passing_utterances_deduped")),
        "passing_seconds_deduped: {}".format(census.get("passing_seconds_deduped")),
        "exported_channels: {}".format(census.get("exported_channels")),
        "exported_utterances_reported: {}".format(census.get("exported_utterances_reported")),
        "exported_but_not_ok_channels: {}".format(census.get("exported_but_not_ok_channels")),
        "exported_but_not_ok_utterances: {}".format(census.get("exported_but_not_ok_utterances")),
        "",
        "passing by language (deduped):",
    ]
    by_language = census.get("by_language") or {}
    if isinstance(by_language, dict):
        for language in sorted(by_language):
            item = by_language[language]
            lines.append(
                "  {lang}: utterances={utt} speakers={spk} seconds={sec} handoff={handoff}".format(
                    lang=language,
                    utt=item.get("utterances"),
                    spk=item.get("speakers"),
                    sec=item.get("seconds"),
                    handoff=item.get("train_handoff"),
                )
            )
    km = census.get("km_exported") or {}
    salane = census.get("salane") or {}
    lines.extend(
        [
            "",
            "km_exported utterances={utt} seconds={sec} dropped_duplicate_audio={dup}".format(
                utt=km.get("utterances") if isinstance(km, dict) else None,
                sec=km.get("seconds") if isinstance(km, dict) else None,
                dup=km.get("dropped_duplicate_audio") if isinstance(km, dict) else None,
            ),
            "km recipe: {}".format(km.get("recipe") if isinstance(km, dict) else ""),
            "km TRAIN_HANDOFF: {}".format(km.get("train_handoff") if isinstance(km, dict) else ""),
            "salane training_utterances={utt} seconds={sec} speakers={spk} voice_reference_files={refs}".format(
                utt=salane.get("training_utterances") if isinstance(salane, dict) else None,
                sec=salane.get("duration_seconds") if isinstance(salane, dict) else None,
                spk=salane.get("speakers") if isinstance(salane, dict) else None,
                refs=salane.get("voice_reference_files") if isinstance(salane, dict) else None,
            ),
            "",
            "These manifests are not loaded by the live CosyVoice server.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_kaldi_holdout(
    src_dir: Path,
    train_dir: Path,
    dev_dir: Path,
    *,
    holdout: int = 4,
    seed: int = 17,
) -> dict:
    """Hold out a few utterances for the recipe's dev list.

    Fewer than 5 utterances: dev copies train and ``held_out`` is 0, because a
    split would leave an empty side. CosyVoice train.py requires both lists.
    """
    src = Path(src_dir)
    wav = _read_kaldi_map(src / "wav.scp")
    text = _read_kaldi_map(src / "text")
    utt2spk = _read_kaldi_map(src / "utt2spk")
    utt2lang = _read_kaldi_map(src / "utt2lang")
    ids = sorted(wav)
    rng = random.Random(seed)
    rng.shuffle(ids)
    n_hold = 0
    if len(ids) >= 5:
        n_hold = max(1, min(int(holdout), len(ids) // 5))
    dev_ids = ids[:n_hold]
    train_ids = ids[n_hold:] if n_hold else list(ids)
    if not train_ids:
        train_ids = list(ids)
        dev_ids = list(ids)
        n_hold = 0

    def _subset(id_list: Sequence[str]) -> tuple[dict, dict, dict, dict]:
        return (
            {i: wav[i] for i in id_list},
            {i: text[i] for i in id_list if i in text},
            {i: utt2spk[i] for i in id_list if i in utt2spk},
            {i: utt2lang[i] for i in id_list if i in utt2lang},
        )

    for folder, chosen in ((train_dir, train_ids), (dev_dir, dev_ids if n_hold else train_ids)):
        parts = _subset(chosen)
        _write_lists(Path(folder), *parts)
    return {
        "train_utterances": len(train_ids),
        "dev_utterances": len(dev_ids) if n_hold else len(train_ids),
        "held_out": n_hold,
        "dev_is_copy_of_train": n_hold == 0,
        "seed": seed,
    }


def patch_sft_yaml(
    text: str,
    *,
    language: str = "km",
    max_epoch: int = 1,
    token_max_length: int | None = None,
) -> str:
    """One-epoch CosyVoice-300M SFT overrides. Does not load the live server.

    train.py starts at epoch -1 when the pretrained llm.pt has no epoch key, so
    ``max_epoch: 1`` runs exactly one epoch (range(0, 1)).

    ``token_max_length`` raises the text-token filter. Khmer BPE on this pool
    sits around 250 tokens at the median, so the stock cap of 200 drops most
    utterances. Leave it unset to keep the stock line.
    """
    lang = (language or "km").strip().lower() or "km"
    out = text.replace("language: 'en'", f"language: '{lang}'")
    out = out.replace("use_spk_embedding: False # change to True during sft", "use_spk_embedding: True")
    out = out.replace("lr: 0.001 # change to 1e-5 during sft", "lr: 0.00001 # 1e-5 sft")
    out = out.replace("scheduler: warmuplr # change to constantlr during sft", "scheduler: constantlr")
    out = out.replace("max_epoch: 200", f"max_epoch: {int(max_epoch)}", 1)
    out = out.replace("accum_grad: 2", "accum_grad: 1", 1)
    out = out.replace("log_interval: 100", "log_interval: 1", 1)
    if token_max_length is not None:
        out = out.replace(
            "token_max_length: 200",
            f"token_max_length: {int(token_max_length)}",
            1,
        )
    return out


_CV_INFO = re.compile(
    r"Epoch (\S+) Step (\S+) CV info lr (\S+) (\d+) rank (.+)$"
)


def parse_cv_metrics(log_text: str) -> list[dict]:
    rows = []
    for line in log_text.splitlines():
        match = _CV_INFO.search(line)
        if not match:
            continue
        loss_bits = match.group(5).split()
        losses: Dict[str, float] = {}
        for idx in range(0, len(loss_bits) - 1, 2):
            try:
                losses[loss_bits[idx]] = float(loss_bits[idx + 1])
            except ValueError:
                continue
        rows.append(
            {
                "epoch": match.group(1),
                "step": match.group(2),
                "lr": match.group(3),
                "rank": int(match.group(4)),
                "losses": losses,
            }
        )
    return rows
