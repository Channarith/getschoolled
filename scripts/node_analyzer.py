#!/usr/bin/env python3
"""Read-only node analyzer: why are some nodes unusable, and what do they cost?

  python3 scripts/node_analyzer.py             # table + advice (uses kubectl; Vultr API if VULTR_API_KEY is set)
  python3 scripts/node_analyzer.py --json      # machine-readable
  python3 scripts/node_analyzer.py --strict    # exit 1 if any billed node is unusable or any stale node exists
It never changes the cluster.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared", "src"))
from aoep_shared.node_analyzer import analyze, render  # noqa: E402


def kubectl(*args: str) -> dict:
    return json.loads(subprocess.run(["kubectl", *args, "-o", "json"], check=True, capture_output=True, text=True).stdout)


def vultr_instance_ids(cluster_label: str | None) -> set[str] | None:
    key = os.environ.get("VULTR_API_KEY")
    if not key:
        return None
    req = urllib.request.Request("https://api.vultr.com/v2/kubernetes/clusters", headers={"Authorization": f"Bearer {key}"})
    clusters = json.load(urllib.request.urlopen(req, timeout=20))["vke_clusters"]
    ids: set[str] = set()
    for cluster in clusters:
        if cluster_label and cluster["label"] != cluster_label:
            continue
        for pool in cluster["node_pools"]:
            ids.update(node["id"] for node in pool["nodes"])
    return ids


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--cluster", default="salareen-prod", help="Vultr cluster label (default salareen-prod)")
    ap.add_argument("--node-price", type=float, default=20.0, help="USD per node per month (vc2-2c-4gb)")
    args = ap.parse_args()
    nodes = kubectl("get", "nodes")["items"]
    pods = kubectl("get", "pods", "-A")["items"]
    report = analyze(nodes, pods, vultr_instance_ids(args.cluster), args.node_price)
    print(json.dumps(report, indent=2) if args.json else render(report))
    s = report["summary"]
    return 1 if args.strict and (s["billed_unusable"] or s["stale"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
