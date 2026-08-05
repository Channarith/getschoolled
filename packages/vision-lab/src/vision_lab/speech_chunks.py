"""Pure Python streaming speech chunker for low-latency voice responses."""

from __future__ import annotations

from dataclasses import dataclass
import re

_PUNCT = re.compile(r"[.!?,;:]$")
_WORD = re.compile(r"\S+")


@dataclass
class ChunkOptions:
    first_chunk_words: int = 3
    min_words: int = 4
    max_words: int = 9


class SpeechChunker:
    """Cut streamed LLM deltas into short chunks that TTS can speak quickly."""

    def __init__(self, opts: ChunkOptions | None = None) -> None:
        self.opts = opts or ChunkOptions()
        self._buf = ""
        self._emitted = 0

    def feed(self, delta: str) -> list[str]:
        self._buf += delta or ""
        out: list[str] = []
        while True:
            chunk = self._take()
            if chunk is None:
                break
            out.append(chunk)
        return out

    def flush(self) -> str | None:
        rest = self._buf.strip()
        self._buf = ""
        if rest:
            self._emitted += 1
        return rest or None

    def _words(self) -> list[re.Match[str]]:
        return list(_WORD.finditer(self._buf))

    def _cut(self, words: list[re.Match[str]], idx: int) -> str:
        end = words[idx].end()
        chunk = self._buf[:end].strip()
        self._buf = self._buf[end:]
        self._emitted += 1
        return chunk

    def _take(self) -> str | None:
        words = self._words()
        if not words:
            return None
        first_words = max(1, int(self.opts.first_chunk_words or 3))
        min_words = max(1, int(self.opts.min_words or 4))
        max_words = max(min_words, int(self.opts.max_words or 9))

        if self._emitted == 0:
            limit = min(first_words, len(words))
            for idx in range(limit):
                if _PUNCT.search(words[idx].group(0)):
                    return self._cut(words, idx)
            if len(words) >= first_words:
                return self._cut(words, first_words - 1)
            return None

        for idx in range(min_words - 1, len(words)):
            if _PUNCT.search(words[idx].group(0)):
                return self._cut(words, idx)
        if len(words) >= max_words:
            return self._cut(words, max_words - 1)
        return None
