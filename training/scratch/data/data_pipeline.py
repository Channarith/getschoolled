#!/usr/bin/env python3
"""Track A.1 - frontier data pipeline + tokenizer (pure Python, offline-testable).

Same algorithms used at trillion-token scale on the lab cluster; here they run on
sample shards and in CI. Stages:
  clean -> quality filter -> MinHash/LSH dedup -> eval decontamination ->
  shard -> train tokenizer.

These are transparent reference implementations; the cluster swaps in
SentencePiece/BPE + a Spark/Ray MinHash for scale (see training/RUNBOOK.txt), but
the contract (and the tests) stay identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[a-z0-9]+")
_BOILERPLATE = ("lorem ipsum", "all rights reserved", "click here", "cookie policy")


# --------------------------------------------------------------------------- #
# clean + quality filter
# --------------------------------------------------------------------------- #
def clean_text(text: str) -> str:
    return _WS.sub(" ", text).strip()


def quality_ok(text: str, *, min_chars: int = 200) -> bool:
    t = clean_text(text)
    if len(t) < min_chars:
        return False
    low = t.lower()
    if any(b in low for b in _BOILERPLATE):
        return False
    tokens = _TOKEN.findall(low)
    if not tokens:
        return False
    # Drop low-diversity spam (e.g. one token repeated many times).
    if len(set(tokens)) / len(tokens) < 0.1:
        return False
    return True


# --------------------------------------------------------------------------- #
# MinHash + LSH dedup
# --------------------------------------------------------------------------- #
def shingles(text: str, k: int = 5) -> Set[str]:
    toks = _TOKEN.findall(text.lower())
    if len(toks) < k:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i : i + k]) for i in range(len(toks) - k + 1)}


def minhash(sh: Set[str], num_perm: int = 32) -> Tuple[int, ...]:
    if not sh:
        return tuple([0] * num_perm)
    sig = []
    for i in range(num_perm):
        salt = str(i).encode()
        sig.append(min(int(hashlib.blake2b(salt + s.encode(), digest_size=8).hexdigest(), 16) for s in sh))
    return tuple(sig)


def jaccard_estimate(a: Tuple[int, ...], b: Tuple[int, ...]) -> float:
    if not a or not b:
        return 0.0
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def dedup(docs: Sequence[str], *, threshold: float = 0.8, num_perm: int = 32) -> List[str]:
    kept: List[str] = []
    sigs: List[Tuple[int, ...]] = []
    for doc in docs:
        sig = minhash(shingles(doc), num_perm)
        if any(jaccard_estimate(sig, s) >= threshold for s in sigs):
            continue
        kept.append(doc)
        sigs.append(sig)
    return kept


# --------------------------------------------------------------------------- #
# eval-set decontamination
# --------------------------------------------------------------------------- #
def _ngrams(text: str, n: int = 8) -> Set[str]:
    toks = _TOKEN.findall(text.lower())
    return {" ".join(toks[i : i + n]) for i in range(max(0, len(toks) - n + 1))}


def decontaminate(docs: Sequence[str], eval_texts: Sequence[str], *, n: int = 8) -> List[str]:
    """Drop training docs that share an n-gram with any eval example."""
    banned: Set[str] = set()
    for e in eval_texts:
        banned |= _ngrams(e, n)
    out = []
    for d in docs:
        if _ngrams(d, n) & banned:
            continue
        out.append(d)
    return out


# --------------------------------------------------------------------------- #
# sharding
# --------------------------------------------------------------------------- #
def shard(docs: Sequence[str], *, docs_per_shard: int) -> List[List[str]]:
    return [list(docs[i : i + docs_per_shard]) for i in range(0, len(docs), docs_per_shard)]


# --------------------------------------------------------------------------- #
# tokenizer training (toy word-frequency vocab; cluster uses BPE/SentencePiece)
# --------------------------------------------------------------------------- #
class WordTokenizer:
    SPECIALS = ["<pad>", "<unk>", "<bos>", "<eos>"]

    def __init__(self, vocab: Dict[str, int]):
        self.vocab = vocab
        self.inv = {i: t for t, i in vocab.items()}

    @classmethod
    def train(cls, corpus: Iterable[str], *, vocab_size: int = 1000) -> "WordTokenizer":
        counts: Counter = Counter()
        for doc in corpus:
            counts.update(_TOKEN.findall(doc.lower()))
        vocab = {t: i for i, t in enumerate(cls.SPECIALS)}
        for tok, _ in counts.most_common(max(0, vocab_size - len(cls.SPECIALS))):
            vocab[tok] = len(vocab)
        return cls(vocab)

    def encode(self, text: str) -> List[int]:
        unk = self.vocab["<unk>"]
        return [self.vocab.get(t, unk) for t in _TOKEN.findall(text.lower())]

    def decode(self, ids: Sequence[int]) -> str:
        return " ".join(self.inv.get(i, "<unk>") for i in ids)

    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.vocab), encoding="utf-8")


def run_pipeline(docs: Sequence[str], eval_texts: Sequence[str] | None = None, *,
                 min_chars: int = 200, dedup_threshold: float = 0.8,
                 docs_per_shard: int = 1000, vocab_size: int = 1000) -> dict:
    cleaned = [clean_text(d) for d in docs]
    filtered = [d for d in cleaned if quality_ok(d, min_chars=min_chars)]
    deduped = dedup(filtered, threshold=dedup_threshold)
    decontam = decontaminate(deduped, eval_texts or [])
    shards = shard(decontam, docs_per_shard=docs_per_shard)
    tokenizer = WordTokenizer.train(decontam, vocab_size=vocab_size)
    return {
        "in": len(docs), "kept": len(decontam), "shards": len(shards),
        "vocab_size": len(tokenizer.vocab), "tokenizer": tokenizer, "documents": decontam,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True, help="JSONL with {\"text\":...} rows")
    ap.add_argument("--eval", default=None, help="JSONL eval set for decontamination")
    ap.add_argument("--min-chars", type=int, default=200)
    ap.add_argument("--vocab-size", type=int, default=1000)
    ap.add_argument("--tokenizer-out", default=None)
    args = ap.parse_args(argv)

    def _load(p):
        return [json.loads(l)["text"] for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]

    docs = _load(args.inp)
    evals = _load(args.eval) if args.eval else []
    result = run_pipeline(docs, evals, min_chars=args.min_chars, vocab_size=args.vocab_size)
    if args.tokenizer_out:
        result["tokenizer"].save(args.tokenizer_out)
    print(json.dumps({k: v for k, v in result.items() if k not in ("tokenizer", "documents")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
