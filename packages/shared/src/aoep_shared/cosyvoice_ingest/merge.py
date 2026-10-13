"""Merge CosyVoice Kaldi recipe dirs into one train handoff set.

Each channel/job keeps its own ``output/cosyvoice_*`` tree. Every ingest run
also rebuilds a combined recipe (default ``output/cosyvoice_<lang>_merged``)
so training always points at one merged corpus.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from .export import build_spk2utt, render_train_handoff


@dataclass
class MergeReport:
    ok: bool
    dest_dir: str
    sources: List[str]
    utterances: int
    speakers: int
    collisions_renamed: int
    train_handoff: str = ""
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "dest_dir": self.dest_dir,
            "sources": list(self.sources),
            "utterances": self.utterances,
            "speakers": self.speakers,
            "collisions_renamed": self.collisions_renamed,
            "train_handoff": self.train_handoff,
            "errors": list(self.errors),
        }


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


def _safe_prefix(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "src").strip()).strip("._-")
    return (cleaned or "src")[:48]


def _channel_root_name(recipe_dir: Path) -> str:
    """``…/cosyvoice_km_dara/04_cosyvoice/train`` → ``cosyvoice_km_dara``."""
    if recipe_dir.parent.name == "04_cosyvoice":
        return recipe_dir.parent.parent.name
    return recipe_dir.name


def _matches_language(recipe_dir: Path, language: str) -> bool:
    """Keep channel trees for this language (name or utt2lang / meta)."""
    lang = (language or "").strip().lower()
    if not lang:
        return True
    name = _channel_root_name(recipe_dir).lower()
    if name == f"cosyvoice_{lang}" or name.startswith(f"cosyvoice_{lang}_"):
        return True
    if f"_{lang}_" in f"_{name}_":
        return True
    # Fallback: majority language in utt2lang / meta.json
    lang_map = _read_kaldi_map(recipe_dir / "utt2lang")
    if lang_map:
        vals = list(lang_map.values())
        return sum(1 for v in vals if v.strip().lower() == lang) >= max(1, len(vals) // 2)
    meta_p = recipe_dir / "meta.json"
    if meta_p.is_file():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            return str(meta.get("language") or "").strip().lower() == lang
        except (OSError, json.JSONDecodeError):
            return False
    return False


def discover_recipe_dirs(
    roots: Sequence[Path | str],
    *,
    split_name: str = "train",
    exclude: Optional[Path] = None,
    language: str = "",
) -> List[Path]:
    """Find ``*/04_cosyvoice/<split>`` (or bare recipe dirs with wav.scp) under roots."""
    found: List[Path] = []
    exclude_res = exclude.resolve() if exclude else None
    seen: set[Path] = set()
    for root in roots:
        base = Path(root)
        if not base.exists():
            continue
        candidates: List[Path] = []
        if (base / "wav.scp").is_file():
            candidates.append(base)
        candidates.extend(base.glob(f"*/04_cosyvoice/{split_name}"))
        candidates.extend(base.glob(f"04_cosyvoice/{split_name}"))
        if base.name == split_name and (base / "wav.scp").is_file():
            candidates.append(base)
        for cand in candidates:
            if not (cand / "wav.scp").is_file():
                continue
            res = cand.resolve()
            if exclude_res and res == exclude_res:
                continue
            if res in seen:
                continue
            # Skip the merged tree's own recipe when scanning a parent that contains it
            if exclude_res and exclude_res in res.parents:
                continue
            if language and not _matches_language(cand, language):
                continue
            # Never treat another language's ``*_merged`` tree as a source
            if _channel_root_name(cand).endswith("_merged"):
                continue
            seen.add(res)
            found.append(cand)
    return sorted(found, key=lambda p: str(p.resolve()))


def merge_cosyvoice_recipes(
    sources: Sequence[Path | str],
    dest_dir: Path | str,
    *,
    split_name: str = "train",
    language: str = "km",
    cosyvoice_repo: Optional[Path] = None,
    source_labels: Optional[Mapping[Path, str]] = None,
) -> MergeReport:
    """Union Kaldi lists from ``sources`` into ``dest_dir / split_name``.

    On utt_id collision, rename to ``<source_prefix>__<utt_id>`` so parallel
    channel jobs never clobber each other.
    """
    dest_root = Path(dest_dir)
    if dest_root.name != split_name:
        dest_root = dest_root / split_name
    dest_root.mkdir(parents=True, exist_ok=True)

    wav: Dict[str, str] = {}
    text: Dict[str, str] = {}
    utt2spk: Dict[str, str] = {}
    utt2lang: Dict[str, str] = {}
    used_sources: List[str] = []
    collisions = 0
    errors: List[str] = []

    for src in sources:
        src_path = Path(src)
        if src_path.name != split_name and (src_path / split_name / "wav.scp").is_file():
            src_path = src_path / split_name
        if not (src_path / "wav.scp").is_file():
            errors.append(f"skip_missing_wav_scp:{src_path}")
            continue
        if src_path.resolve() == dest_root.resolve():
            continue

        label = (source_labels or {}).get(Path(src), "")
        if not label:
            # output/cosyvoice_km_dara/04_cosyvoice/train → cosyvoice_km_dara
            label = src_path.parent.parent.name if src_path.parent.name == "04_cosyvoice" else src_path.name
        prefix = _safe_prefix(label)

        src_wav = _read_kaldi_map(src_path / "wav.scp")
        src_text = _read_kaldi_map(src_path / "text")
        src_spk = _read_kaldi_map(src_path / "utt2spk")
        src_lang = _read_kaldi_map(src_path / "utt2lang")
        if not src_wav:
            errors.append(f"empty:{src_path}")
            continue

        used_sources.append(str(src_path.resolve()))
        for utt_id, wav_path in src_wav.items():
            transcript = (src_text.get(utt_id) or "").strip()
            if not transcript:
                continue
            if not Path(wav_path).is_file():
                # still keep absolute path from source; train machine may resolve later
                pass
            new_id = utt_id
            if new_id in wav and wav[new_id] != wav_path:
                new_id = f"{prefix}__{utt_id}"
                collisions += 1
                while new_id in wav:
                    new_id = f"{prefix}__{utt_id}_{collisions}"
            elif new_id in wav:
                # identical path — skip duplicate
                continue
            wav[new_id] = wav_path
            text[new_id] = transcript
            utt2spk[new_id] = (src_spk.get(utt_id) or prefix).replace(" ", "_")
            utt2lang[new_id] = src_lang.get(utt_id) or language

    spk2utt = build_spk2utt(utt2spk)

    def _write_map(path: Path, mapping: Mapping[str, str]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for k in sorted(mapping):
                f.write(f"{k} {mapping[k]}\n")

    _write_map(dest_root / "wav.scp", wav)
    _write_map(dest_root / "text", text)
    _write_map(dest_root / "utt2spk", utt2spk)
    _write_map(dest_root / "utt2lang", utt2lang)
    with (dest_root / "spk2utt").open("w", encoding="utf-8") as f:
        for spk in sorted(spk2utt):
            f.write(f"{spk} {' '.join(spk2utt[spk])}\n")

    meta = {
        "format": "cosyvoice_kaldi_lists_merged",
        "split": split_name,
        "language": language,
        "utterance_count": len(wav),
        "speaker_count": len(spk2utt),
        "sources": used_sources,
        "collisions_renamed": collisions,
        "note": "Merged on each ingest run; train against this directory.",
    }
    (dest_root / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    handoff = dest_root / "TRAIN_HANDOFF.txt"
    handoff.write_text(
        render_train_handoff(
            data_dir=dest_root,
            cosyvoice_repo=cosyvoice_repo,
            split_name=split_name,
            has_instruct=False,
        ),
        encoding="utf-8",
    )

    ok = len(wav) > 0
    if not ok:
        errors.append("merge_empty: no utterances with transcripts in sources")

    return MergeReport(
        ok=ok,
        dest_dir=str(dest_root.resolve()),
        sources=used_sources,
        utterances=len(wav),
        speakers=len(spk2utt),
        collisions_renamed=collisions,
        train_handoff=str(handoff.resolve()),
        errors=errors,
    )


def default_merge_into(language: str) -> Path:
    lang = (language or "und").strip().lower() or "und"
    return Path("output") / f"cosyvoice_{lang}_merged"


def merge_dest_recipe(merge_into: Path | str, *, split_name: str = "train") -> Path:
    """Canonical combined recipe path: ``<merge_into>/04_cosyvoice/<split>``."""
    dest = Path(merge_into)
    if dest.name == split_name and dest.parent.name == "04_cosyvoice":
        return dest
    if dest.name == "04_cosyvoice":
        return dest / split_name
    return dest / "04_cosyvoice" / split_name


def pool_prefix_from_merge_into(merge_into: Path | str) -> str:
    """``output/cosyvoice_zh_tw_merged`` → ``cosyvoice_zh_tw``."""
    name = Path(merge_into).name
    if name.endswith("_merged"):
        return name[: -len("_merged")]
    return name


def merge_language_pool(
    *,
    language: str,
    merge_into: Path | str,
    scan_roots: Sequence[Path | str],
    current_recipe: Optional[Path] = None,
    split_name: str = "train",
    cosyvoice_repo: Optional[Path] = None,
) -> MergeReport:
    """Discover channel recipes under ``scan_roots`` and merge into ``merge_into``.

    When ``merge_into`` is named ``cosyvoice_<pool>_merged``, only channel trees
    whose names start with ``cosyvoice_<pool>`` are included — so ``zh_tw`` and
    ``zh`` (or ``en_gb`` / ``en``) stay separate dialect pools even if Whisper
    ASR language is the same.
    """
    dest_recipe = merge_dest_recipe(merge_into, split_name=split_name)
    pool_prefix = pool_prefix_from_merge_into(merge_into)

    sources = discover_recipe_dirs(
        scan_roots,
        split_name=split_name,
        exclude=dest_recipe,
        language=language,
    )
    if pool_prefix.startswith("cosyvoice_"):
        filtered: List[Path] = []
        for src in sources:
            root = _channel_root_name(src)
            if root == pool_prefix or root.startswith(pool_prefix + "_"):
                filtered.append(src)
        sources = filtered

    if current_recipe is not None:
        cur = Path(current_recipe)
        if cur.name != split_name and (cur / split_name / "wav.scp").is_file():
            cur = cur / split_name
        if (cur / "wav.scp").is_file() and cur.resolve() not in {p.resolve() for p in sources}:
            sources.append(cur)

    return merge_cosyvoice_recipes(
        sources,
        dest_recipe,
        split_name=split_name,
        language=language,
        cosyvoice_repo=cosyvoice_repo,
    )
