"""Harvester entrypoint smoke (offline, MockFetcher)."""

import io
import json
from contextlib import redirect_stdout

from harvester.run import main


def test_run_once_ingests_seed_demo():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["--once"])
    assert rc == 0
    out = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert out["ingested"] >= 2
    assert out["catalog_size"] >= 2
