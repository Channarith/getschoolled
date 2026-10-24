from datetime import datetime, timezone

from aoep_shared.node_analyzer import HEALTHY, NOTREADY, STALE, UNINITIALIZED, analyze, classify_node, node_capacity

NOW = datetime(2026, 10, 24, 3, 0, tzinfo=timezone.utc)


def node(name, *, ready=True, since="2026-10-24T01:00:00Z", taints=(), addresses=("InternalIP",), instance=None, cpu="2", mem="4Gi"):
    return {
        "metadata": {"name": name},
        "spec": {"taints": [{"key": k} for k in taints], "providerID": f"vultr://{instance}" if instance else ""},
        "status": {
            "conditions": [{"type": "Ready", "status": "True" if ready else "Unknown", "lastTransitionTime": since}],
            "addresses": [{"type": t, "address": "x"} for t in addresses],
            "allocatable": {"cpu": cpu, "memory": mem},
        },
    }


def pod(name, on, cpu="500m", mem="256Mi", phase="Running"):
    return {"metadata": {"name": name}, "spec": {"nodeName": on, "containers": [{"resources": {"requests": {"cpu": cpu, "memory": mem}}}]}, "status": {"phase": phase}}


def test_healthy_node():
    assert classify_node(node("a", instance="i1"), {"i1"}, NOW)["state"] == HEALTHY


def test_uninitialized_node_is_billed_and_unusable():
    v = classify_node(node("b", taints=["node.cloudprovider.kubernetes.io/uninitialized"], addresses=("Hostname",), instance="i2"), {"i2"}, NOW)
    assert v["state"] == UNINITIALIZED and v["billed"] is True and len(v["reasons"]) == 2


def test_node_without_vultr_instance_is_stale_and_not_billed():
    v = classify_node(node("c", ready=False, instance="gone"), {"i1"}, NOW)
    assert v["state"] == STALE and v["billed"] is False


def test_autoscaler_marked_notready_is_stale_without_vultr_data():
    v = classify_node(node("d", ready=False, taints=["ToBeDeletedByClusterAutoscaler"]), None, NOW)
    assert v["state"] == STALE


def test_plain_notready():
    assert classify_node(node("e", ready=False, instance="i1"), {"i1"}, NOW)["state"] == NOTREADY


def test_capacity_counts_only_running_pods_on_that_node():
    n = node("a")
    pods = [pod("p1", "a"), pod("p2", "a", cpu="1"), pod("p3", "b"), pod("p4", "a", phase="Succeeded")]
    cap = node_capacity(n, pods)
    assert cap["pods"] == 2 and cap["cpu_request_m"] == 1500 and cap["cpu_request_pct"] == 75


def test_analyze_reports_waste_and_pressure():
    nodes = [node("a", instance="i1"), node("b", taints=["node.cloudprovider.kubernetes.io/uninitialized"], addresses=("Hostname",), instance="i2")]
    pods = [pod("p1", "a", cpu="1900m"), pod("pend", "", phase="Pending")]
    report = analyze(nodes, pods, {"i1", "i2"}, node_price=20, now=NOW)
    s = report["summary"]
    assert s["healthy"] == 1 and s["uninitialized"] == 1 and s["est_wasted_usd_month"] == 20 and s["pending_pods"] == 1
    assert any("Vultr cloud controller" in a for a in report["advice"])
    assert any("CPU-requested" in a for a in report["advice"])
