#!/usr/bin/env python3
"""Launch CosyVoice train.py without pandas or TorchCodec.

Patches happen before the upstream module is executed:
- torchaudio.load reads wav bytes with soundfile
- parquet_opener yields rows with pyarrow (no DataFrame.to_pandas)
The pretrained checkpoint is only read. model_dir is whatever train.py was given.
"""

from __future__ import annotations

import logging
import os
import runpy
import sys
from io import BytesIO


def _install() -> None:
    import numpy as np
    import pyarrow.parquet as pq
    import soundfile as sf
    import torch
    import torchaudio
    import cosyvoice.dataset.processor as processor

    def load(source, *args, **kwargs):
        del args, kwargs
        if isinstance(source, (bytes, bytearray, memoryview)):
            source = BytesIO(bytes(source))
        data, sample_rate = sf.read(source, dtype="float32", always_2d=True)
        audio = torch.from_numpy(np.ascontiguousarray(data.T))
        return audio, int(sample_rate)

    torchaudio.load = load

    import torch.utils.data as data_mod

    real_loader = data_mod.DataLoader

    class _DataLoader(real_loader):
        def __init__(self, *args, **kwargs):
            if int(kwargs.get("num_workers") or 0) == 0:
                kwargs.pop("prefetch_factor", None)
            super().__init__(*args, **kwargs)

    data_mod.DataLoader = _DataLoader

    def parquet_opener(data, mode="train"):
        del mode
        for sample in data:
            url = sample["src"]
            try:
                parquet = pq.ParquetFile(url)
                for batch in parquet.iter_batches(batch_size=64):
                    columns = batch.to_pydict()
                    if not columns:
                        continue
                    count = len(next(iter(columns.values())))
                    for index in range(count):
                        row = {key: columns[key][index] for key in columns}
                        yield {**sample, **row}
            except Exception as exc:
                logging.warning("parquet open failed for %s (%s)", url, type(exc).__name__)

    processor.parquet_opener = parquet_opener

    import torch.distributed as dist
    import cosyvoice.utils.train_utils as train_utils

    def cosyvoice_join(group_join, info_dict):
        # Single-GPU torch in this environment has no ProcessGroup.options.
        # The upstream join only matters when ranks see different batch counts.
        world_size = int(os.environ.get("WORLD_SIZE", "1"))
        if world_size <= 1 or info_dict.get("batch_idx") == 0:
            return False
        try:
            dist.monitored_barrier(group=group_join)
        except RuntimeError:
            return True
        return False

    train_utils.cosyvoice_join = cosyvoice_join


def main() -> None:
    train_py = os.environ.get("COSYVOICE_TRAIN_PY", "")
    if not train_py:
        sys.stderr.write("COSYVOICE_TRAIN_PY is required\n")
        raise SystemExit(2)
    _install()
    runpy.run_path(train_py, run_name="__main__")


if __name__ == "__main__":
    main()
