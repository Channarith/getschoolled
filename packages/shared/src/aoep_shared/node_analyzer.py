"""Read-only analysis of Kubernetes nodes: which are usable, which are dead weight, and why.

Pure functions over kubectl JSON so they can be unit tested. The CLI is scripts/node_analyzer.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

UNINIT_TAINT = "node.cloudprovider.kubernetes.io/uninitialized"
DELETE_TAINT = "ToBeDeletedByClusterAutoscaler"

HEALTHY = "healthy"
UNINITIALIZED = "uninitialized"  # in the cluster and billed, but the cloud controller never finished it
STALE = "stale"  # Node object whose machine is gone
NOTREADY = "notready"
UNKNOWN = "unknown"


def _cpu_m(value: str | None) -> int:
    if not value:
        return 0
    return int(float(value[:-1])) if value.endswith("m") else int(float(value) * 1000)


def _mem_mi(value: str | None) -> int:
    if not value:
        return 0
    units = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024, "Ti": 1024 * 1024, "K": 1000 / 1048576, "M": 1000000 / 1048576, "G": 1e9 / 1048576}
    for suffix, factor in units.items():
        if value.endswith(suffix):
            return int(float(value[: -len(suffix)]) * factor)
    return int(float(value) / 1048576)


def _taint_keys(node: dict[str, Any]) -> set[str]:
    return {t.get("key", "") for t in node.get("spec", {}).get("taints") or []}


def _ready(node: dict[str, Any]) -> tuple[bool, str | None]:
    for cond in node.get("status", {}).get("conditions") or []:
        if cond.get("type") == "Ready":
            return cond.get("status") == "True", cond.get("lastTransitionTime")
    return False, None


def _age_minutes(stamp: str | None, now: datetime) -> float | None:
    if not stamp:
        return None
    then = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return (now - then).total_seconds() / 60


def provider_instance_id(node: dict[str, Any]) -> str | None:
    pid = node.get("spec", {}).get("providerID") or ""
    return pid.split("://", 1)[1] if pid.startswith("vultr://") else None


def classify_node(node: dict[str, Any], vultr_ids: set[str] | None, now: datetime | None = None) -> dict[str, Any]:
    """Return {state, reasons, billed}. vultr_ids is the set of instance ids Vultr says are in the pool (None = unknown)."""
    now = now or datetime.now(timezone.utc)
    ready, since = _ready(node)
    taints = _taint_keys(node)
    addresses = {a.get("type") for a in node.get("status", {}).get("addresses") or []}
    instance = provider_instance_id(node)
    in_pool = None if vultr_ids is None or instance is None else instance in vultr_ids
    reasons: list[str] = []

    if in_pool is False:
        reasons.append("Vultr has no instance for this node; the Node object is left over")
        return {"state": STALE, "reasons": reasons, "billed": False}
    if not ready and DELETE_TAINT in taints and in_pool is None:
        age = _age_minutes(since, now)
        reasons.append("marked for deletion by the autoscaler and NotReady" + (f" for {age:.0f} min" if age is not None else ""))
        return {"state": STALE, "reasons": reasons, "billed": False}

    if UNINIT_TAINT in taints:
        reasons.append("cloud controller never initialized it (uninitialized taint still present)")
    if "InternalIP" not in addresses:
        reasons.append("no InternalIP (calico-node cannot start; pods cannot be networked)")
    if reasons:
        return {"state": UNINITIALIZED, "reasons": reasons, "billed": in_pool is not False}

    if not ready:
        return {"state": NOTREADY, "reasons": ["kubelet is not reporting Ready"], "billed": in_pool is not False}
    return {"state": HEALTHY, "reasons": [], "billed": True}


def node_capacity(node: dict[str, Any], pods: list[dict[str, Any]]) -> dict[str, Any]:
    name = node["metadata"]["name"]
    alloc = node.get("status", {}).get("allocatable", {})
    cpu_alloc, mem_alloc = _cpu_m(alloc.get("cpu")), _mem_mi(alloc.get("memory"))
    cpu_req = mem_req = count = 0
    for pod in pods:
        if pod.get("spec", {}).get("nodeName") != name or pod.get("status", {}).get("phase") in ("Succeeded", "Failed"):
            continue
        count += 1
        for c in pod["spec"].get("containers", []):
            req = c.get("resources", {}).get("requests", {})
            cpu_req += _cpu_m(req.get("cpu"))
            mem_req += _mem_mi(req.get("memory"))
    return {
        "pods": count,
        "cpu_request_m": cpu_req,
        "cpu_allocatable_m": cpu_alloc,
        "cpu_request_pct": round(100 * cpu_req / cpu_alloc) if cpu_alloc else None,
        "mem_request_mi": mem_req,
        "mem_allocatable_mi": mem_alloc,
        "mem_request_pct": round(100 * mem_req / mem_alloc) if mem_alloc else None,
    }


def calico_status(node_name: str, pods: list[dict[str, Any]]) -> str:
    for pod in pods:
        if pod.get("spec", {}).get("nodeName") != node_name or pod["metadata"]["name"].startswith("calico-node") is False:
            continue
        for cs in pod.get("status", {}).get("containerStatuses") or []:
            waiting = (cs.get("state") or {}).get("waiting") or {}
            if waiting.get("reason"):
                return waiting["reason"]
            if not cs.get("ready"):
                return "NotReady"
        return "Running"
    return "none"


def analyze(nodes: list[dict[str, Any]], pods: list[dict[str, Any]], vultr_ids: set[str] | None = None,
            node_price: float = 20.0, now: datetime | None = None) -> dict[str, Any]:
    rows = []
    for node in nodes:
        verdict = classify_node(node, vultr_ids, now)
        rows.append({
            "name": node["metadata"]["name"],
            **verdict,
            **node_capacity(node, pods),
            "calico": calico_status(node["metadata"]["name"], pods),
        })
    usable = [r for r in rows if r["state"] == HEALTHY]
    wasted = [r for r in rows if r["state"] in (UNINITIALIZED, NOTREADY) and r["billed"]]
    pending = [p for p in pods if p.get("status", {}).get("phase") == "Pending"]
    cpu_alloc = sum(r["cpu_allocatable_m"] for r in usable)
    cpu_req = sum(r["cpu_request_m"] for r in usable)
    advice: list[str] = []
    stale = [r for r in rows if r["state"] == STALE]
    if stale:
        advice.append(f"{len(stale)} stale Node object(s) can be deleted (the stale-node-reaper does this automatically)")
    if any(r["state"] == UNINITIALIZED for r in rows):
        advice.append("Nodes are not being initialized by the Vultr cloud controller: open/escalate the Vultr ticket; new nodes cannot be used")
    if wasted:
        advice.append(f"{len(wasted)} billed node(s) are unusable, about ${node_price * len(wasted):.0f}/month")
    if usable and cpu_alloc and cpu_req / cpu_alloc > 0.85:
        advice.append(f"usable nodes are {round(100 * cpu_req / cpu_alloc)}% CPU-requested: rollouts will leave pods Pending; lower requests or add working nodes")
    if pending:
        advice.append(f"{len(pending)} pod(s) Pending")
    return {
        "nodes": rows,
        "summary": {
            "total": len(rows),
            "healthy": len(usable),
            "uninitialized": sum(r["state"] == UNINITIALIZED for r in rows),
            "stale": len(stale),
            "notready": sum(r["state"] == NOTREADY for r in rows),
            "billed_unusable": len(wasted),
            "est_wasted_usd_month": node_price * len(wasted),
            "pending_pods": len(pending),
            "healthy_cpu_request_pct": round(100 * cpu_req / cpu_alloc) if cpu_alloc else None,
        },
        "advice": advice,
    }


def render(report: dict[str, Any]) -> str:
    lines = [f"{'NODE':<24} {'STATE':<14} {'CPU REQ':>8} {'MEM REQ':>8} {'PODS':>5} {'CALICO':<18} NOTES"]
    for r in sorted(report["nodes"], key=lambda r: (r["state"] != HEALTHY, r["name"])):
        cpu = f"{r['cpu_request_pct']}%" if r["cpu_request_pct"] is not None else "-"
        mem = f"{r['mem_request_pct']}%" if r["mem_request_pct"] is not None else "-"
        lines.append(f"{r['name']:<24} {r['state']:<14} {cpu:>8} {mem:>8} {r['pods']:>5} {r['calico']:<18} {'; '.join(r['reasons'])}")
    s = report["summary"]
    lines.append("")
    lines.append(f"{s['healthy']} healthy of {s['total']} node objects; {s['uninitialized']} uninitialized, {s['stale']} stale, "
                 f"{s['notready']} not ready; {s['pending_pods']} pending pods")
    for item in report["advice"]:
        lines.append(f"- {item}")
    return "\n".join(lines)
