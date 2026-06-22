#!/usr/bin/env python3
"""Sustained-load harness for AOEP services.

qa/stress.py runs a fixed number of requests per scenario as fast as it
can. That's good for SLA gating. This harness is different:

  * It runs at a *target sustained RPS* (open-loop rather than
    closed-loop) for a configurable duration, so you can answer
    "what does p95 look like at 500 rps for 60 seconds?".
  * It reports a latency histogram + percentiles + observed throughput,
    cache-hit ratio (304s vs 200s on cacheable endpoints), 429 ratio
    (rate-limit pressure), and 5xx ratio.
  * It exits zero on success, non-zero when the SLA is breached.

Stdlib only (urllib + threadpool). Run against a single replica or the
full LB-fronted stack; the only difference is the URL.

Examples
--------
  # 500 req/s for 60s against the curriculum service.
  python3 qa/loadtest.py http://localhost:8005/audio/categories \\
      --rps 500 --duration 60

  # Demonstrate the cache: hit a course detail repeatedly with a cached
  # ETag and watch 304s spike.
  python3 qa/loadtest.py http://localhost:8005/audio/courses?limit=20 \\
      --rps 200 --duration 30 --header 'If-None-Match: "abcd"'

  # Verify rate-limit kicks in (expect non-zero 429s).
  python3 qa/loadtest.py http://localhost:8005/notifications/feed \\
      --rps 50 --duration 20 --user-id loadtest-1
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def http_request(method: str, url: str, *, headers: dict[str, str],
                 body: bytes | None, timeout: float) -> tuple[int, float, int]:
    req = urllib.request.Request(url, method=method, data=body, headers=headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            n = len(resp.read())
            return resp.status, (time.perf_counter() - t0) * 1000.0, n
    except urllib.error.HTTPError as e:
        body = e.read() or b""
        return e.code, (time.perf_counter() - t0) * 1000.0, len(body)
    except Exception:  # noqa: BLE001
        return 0, (time.perf_counter() - t0) * 1000.0, 0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def histogram(values: list[float], buckets_ms: list[float]) -> list[tuple[str, int]]:
    """Group latencies into the given (right-edge) buckets."""
    edges = sorted(buckets_ms)
    out = [0] * (len(edges) + 1)
    for v in values:
        placed = False
        for i, e in enumerate(edges):
            if v <= e:
                out[i] += 1
                placed = True
                break
        if not placed:
            out[-1] += 1
    rows: list[tuple[str, int]] = []
    prev = 0.0
    for i, e in enumerate(edges):
        rows.append((f"{prev:.0f}-{e:.0f} ms", out[i]))
        prev = e
    rows.append((f">{prev:.0f} ms", out[-1]))
    return rows


def run(url: str, *, rps: float, duration: float, concurrency: int,
        method: str, headers: dict[str, str], body: bytes | None,
        timeout: float) -> dict:
    """Open-loop request generator: a single producer schedules a request
    every 1/rps seconds onto a thread pool. Concurrency caps the in-flight
    bound so a slow server can't unbounded-queue requests in our process."""
    total_target = max(1, int(rps * duration))
    interval = 1.0 / rps
    latencies: list[float] = []
    statuses: Counter[int] = Counter()
    bytes_total = 0
    skipped = 0
    lock = threading.Lock()

    def worker(scheduled_at: float) -> None:
        nonlocal bytes_total
        # Open-loop: if the worker started >100ms behind schedule we can
        # skip the request rather than chase the past, so a transient hang
        # doesn't avalanche into thousands of stale requests at the end.
        slack = scheduled_at - time.perf_counter()
        if slack < -0.1:
            with lock:
                nonlocal_skipped()
            return
        if slack > 0:
            time.sleep(slack)
        status, ms, n = http_request(method, url, headers=headers, body=body, timeout=timeout)
        with lock:
            statuses[status] += 1
            latencies.append(ms)
            bytes_total += n

    def nonlocal_skipped() -> None:
        nonlocal skipped
        skipped += 1

    pool = ThreadPoolExecutor(max_workers=concurrency)
    start = time.perf_counter()
    futures = []
    for i in range(total_target):
        scheduled_at = start + i * interval
        futures.append(pool.submit(worker, scheduled_at))
    for f in futures:
        f.result()
    pool.shutdown(wait=True)
    wall = time.perf_counter() - start

    counts = dict(statuses)
    n_2xx = sum(c for s, c in counts.items() if 200 <= s < 300)
    n_304 = counts.get(304, 0)
    n_429 = counts.get(429, 0)
    n_5xx = sum(c for s, c in counts.items() if 500 <= s < 600)
    n_err = counts.get(0, 0)
    total = sum(counts.values())
    cache_hit_ratio = (n_304 / max(total, 1))
    rate_limited_ratio = (n_429 / max(total, 1))
    error_ratio = ((n_5xx + n_err) / max(total, 1))

    return {
        "url": url,
        "method": method,
        "target_rps": rps,
        "duration_s": duration,
        "concurrency": concurrency,
        "wall_s": round(wall, 3),
        "requests_sent": total,
        "requests_skipped": skipped,
        "achieved_rps": round(total / wall, 1) if wall > 0 else 0.0,
        "bytes_total": bytes_total,
        "by_status": dict(sorted(counts.items())),
        "n_2xx": n_2xx,
        "n_304_cache_hits": n_304,
        "n_429_rate_limited": n_429,
        "n_5xx_errors": n_5xx,
        "n_connection_errors": n_err,
        "cache_hit_ratio": round(cache_hit_ratio, 4),
        "rate_limited_ratio": round(rate_limited_ratio, 4),
        "error_ratio": round(error_ratio, 4),
        "latency_ms": {
            "min":  round(min(latencies), 2) if latencies else 0,
            "p50":  round(percentile(latencies, 50), 2),
            "p90":  round(percentile(latencies, 90), 2),
            "p95":  round(percentile(latencies, 95), 2),
            "p99":  round(percentile(latencies, 99), 2),
            "p999": round(percentile(latencies, 99.9), 2),
            "max":  round(max(latencies), 2) if latencies else 0,
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0,
            "stdev": round(statistics.pstdev(latencies), 2) if len(latencies) > 1 else 0,
        },
        "histogram": histogram(latencies, [5, 10, 20, 50, 100, 200, 500, 1000, 2000]),
    }


def print_report(report: dict) -> None:
    p = report
    print(f"\nLOAD TEST  {p['method']} {p['url']}")
    print("-" * 78)
    print(f"  target rps      {p['target_rps']:.0f}     duration {p['duration_s']}s     concurrency {p['concurrency']}")
    print(f"  wall            {p['wall_s']}s")
    print(f"  requests sent   {p['requests_sent']}     achieved rps {p['achieved_rps']}")
    print(f"  bytes           {p['bytes_total']:,}")
    print(f"  by status       {p['by_status']}")
    print(f"  cache hits 304  {p['n_304_cache_hits']}  ({p['cache_hit_ratio']*100:.1f}%)")
    print(f"  rate limited    {p['n_429_rate_limited']}  ({p['rate_limited_ratio']*100:.1f}%)")
    print(f"  errors 5xx/conn {p['n_5xx_errors']}/{p['n_connection_errors']}  ({p['error_ratio']*100:.2f}%)")
    L = p['latency_ms']
    print(f"  latency ms     min={L['min']}  p50={L['p50']}  p90={L['p90']}  p95={L['p95']}  p99={L['p99']}  max={L['max']}")
    print(f"                 mean={L['mean']}  stdev={L['stdev']}")
    print("\n  histogram:")
    width = max(1, max(c for _, c in p["histogram"]) or 1)
    for label, count in p["histogram"]:
        bar = "#" * int(40 * count / width)
        print(f"    {label:<14}  {count:>7}  {bar}")
    print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--rps", type=float, default=200.0)
    ap.add_argument("--duration", type=float, default=15.0,
                    help="seconds of sustained load")
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--method", default="GET")
    ap.add_argument("--header", action="append", default=[],
                    help='extra header, e.g. --header "If-None-Match: \\"abc\\""')
    ap.add_argument("--user-id", default=None,
                    help="set X-User-Id so the rate-limiter buckets per identity")
    ap.add_argument("--body", default=None, help="raw request body")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--max-error-ratio", type=float, default=0.01)
    ap.add_argument("--max-p95-ms", type=float, default=300.0)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    headers = {"Accept": "application/json"}
    for h in args.header:
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()
    if args.user_id:
        headers["X-User-Id"] = args.user_id
    body = args.body.encode("utf-8") if args.body else None
    if body is not None:
        headers.setdefault("Content-Type", "application/json")

    report = run(
        args.url, rps=args.rps, duration=args.duration,
        concurrency=args.concurrency, method=args.method.upper(),
        headers=headers, body=body, timeout=args.timeout,
    )
    print_report(report)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"  report written to {args.json}")

    breaches: list[str] = []
    if report["error_ratio"] > args.max_error_ratio:
        breaches.append(f"error_ratio {report['error_ratio']} > {args.max_error_ratio}")
    if report["latency_ms"]["p95"] > args.max_p95_ms:
        breaches.append(f"p95 {report['latency_ms']['p95']}ms > {args.max_p95_ms}ms")
    if breaches:
        print("SLA breaches:")
        for b in breaches:
            print(f"  - {b}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
