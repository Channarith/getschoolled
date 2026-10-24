#!/usr/bin/env python3
"""Refuse to deploy when the cluster cannot take a rollout. Reads `scripts/node_analyzer.py --json` on stdin.

Usage: capacity_gate.py [max_cpu_pct=90] [max_mem_pct=90] [min_healthy=3]
Exit 0 = ok, 1 = refuse (message on stdout). Only 4 nodes are usable today, so the thresholds are strict.
"""
import json
import sys


def check(report: dict, max_cpu: int = 90, max_mem: int = 90, min_healthy: int = 3) -> list:
    problems = []
    nodes = [n for n in report.get("nodes", []) if n.get("state") == "healthy"]
    s = report.get("summary", {})
    if len(nodes) < min_healthy:
        problems.append(f"only {len(nodes)} healthy node(s), need {min_healthy}")
    if s.get("notready"):
        problems.append(f"{s['notready']} node(s) not ready")
    cpu = s.get("healthy_cpu_request_pct")
    if cpu is not None and cpu > max_cpu:
        problems.append(f"CPU requested {cpu}% > {max_cpu}%")
    mem_alloc = sum(n.get("mem_allocatable_mi", 0) for n in nodes)
    mem_req = sum(n.get("mem_request_mi", 0) for n in nodes)
    if mem_alloc and 100 * mem_req / mem_alloc > max_mem:
        problems.append(f"memory requested {round(100 * mem_req / mem_alloc)}% > {max_mem}%")
    return problems


def main(argv: list) -> int:
    nums = [int(x) for x in argv[1:4]]
    max_cpu = nums[0] if len(nums) > 0 else 90
    max_mem = nums[1] if len(nums) > 1 else 90
    min_healthy = nums[2] if len(nums) > 2 else 3
    probs = check(json.load(sys.stdin), max_cpu, max_mem, min_healthy)
    if probs:
        print("capacity gate: REFUSE - " + "; ".join(probs))
        return 1
    print("capacity gate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
