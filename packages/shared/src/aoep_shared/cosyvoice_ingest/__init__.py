"""Video → CosyVoice training-data ingestion pipeline.

Operator-supplied YouTube/Vimeo URL lists → cleaned utterance WAVs + Kaldi-style
manifests (``wav.scp`` / ``text`` / ``utt2spk`` / ``spk2utt``) matching
FunAudioLLM CosyVoice ``examples/*/local/prepare_data.py``.

Distinct from ``llm_training`` (text JSONL / QLoRA) and dictionary gold audio;
reuses ``dictionary_audio.clean_audio_file`` for denoise/QC.
"""

from __future__ import annotations

from .export import CosyVoiceUtterance, write_cosyvoice_recipe
from .pipeline import IngestConfig, IngestReport, run_ingest
from .segment import Segment, segment_pcm16
from .urls import load_url_list

__all__ = [
    "CosyVoiceUtterance",
    "IngestConfig",
    "IngestReport",
    "Segment",
    "load_url_list",
    "run_ingest",
    "segment_pcm16",
    "write_cosyvoice_recipe",
]
