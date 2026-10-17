"""Asynchronous identification training.

Workers embed views concurrently and fold them into the gallery. Capture stays
on the caller; this only trains.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Sequence

import numpy as np

from .embed import embed_rgb
from .gallery import ObjectGallery
from .types import TrainReport, TrainSample


async def train_samples(
    gallery: ObjectGallery,
    samples: Sequence[TrainSample],
    *,
    workers: int = 4,
) -> TrainReport:
    """Enroll ``samples`` on a pool of ``workers`` threads."""
    if not samples:
        return TrainReport(views=0, objects=len(gallery), labels=gallery.labels())
    worker_count = max(1, min(int(workers), len(samples)))
    queue: asyncio.Queue[Optional[TrainSample]] = asyncio.Queue()
    for sample in samples:
        queue.put_nowait(sample)
    for _ in range(worker_count):
        queue.put_nowait(None)

    async def worker() -> None:
        while True:
            sample = await queue.get()
            try:
                if sample is None:
                    return
                embedding = await asyncio.to_thread(embed_rgb, np.asarray(sample.image))
                gallery.enroll(
                    sample.label,
                    embedding,
                    maker=sample.maker,
                    year=sample.year,
                    kind=sample.kind,
                    heat_c=sample.heat_c,
                    smell=sample.smell,
                    smell_intensity=sample.smell_intensity,
                    texture=sample.texture,
                    force_n=sample.force_n,
                )
            finally:
                queue.task_done()

    await asyncio.gather(*(asyncio.create_task(worker()) for _ in range(worker_count)))
    return TrainReport(
        views=len(samples),
        objects=len(gallery),
        labels=gallery.labels(),
    )


def train_samples_blocking(
    gallery: ObjectGallery,
    samples: Sequence[TrainSample],
    *,
    workers: int = 4,
) -> TrainReport:
    return asyncio.run(train_samples(gallery, samples, workers=workers))
