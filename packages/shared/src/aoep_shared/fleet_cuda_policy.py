"""Parse scripts/fleet/probe_cuda.sh output and flag CPU-pinned or GPU-idle ML work.

Kept apart from fleet_status.py on purpose (it only reads the probe's own output)."""
from __future__ import annotations

import sys
from dataclasses import dataclass

ML_HINTS = ("python", "uvicorn", "llama", "whisper", "torch", "nllb", "translate", "ffmpeg")
GPU_IDLE_PCT = 5.0
CPU_BOUND_PCT = 300.0
CPU_PINS = ("NLLB_DEVICE", "AOEP_ASR_DEVICE")


@dataclass
class Finding:
    severity: str  # CRIT | WARN
    message: str
    fix: str


def _num(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse(text: str) -> dict:
    out: dict = {"procs": []}
    for line in text.splitlines():
        if line.startswith("proc="):
            pid, pcpu, args, env = (line[5:].split("|", 3) + ["", "", "", ""])[:4]
            envs = {}
            for kv in env.split():
                if "=" in kv:
                    key, value = kv.split("=", 1)
                    envs[key] = value
            if "CUDA_VISIBLE_DEVICES=" in env.split() or env.endswith("CUDA_VISIBLE_DEVICES="):
                envs["CUDA_VISIBLE_DEVICES"] = ""
            out["procs"].append({"pid": pid, "pcpu": _num(pcpu) or 0.0, "args": args, "env": envs})
        elif "=" in line and not line.startswith("CUDA_POLICY_PROBE"):
            key, value = line.split("=", 1)
            out[key] = value
    return out


def _ml(proc: dict) -> bool:
    return any(h in proc["args"].lower() for h in ML_HINTS)


def analyze(report: dict) -> list[Finding]:
    findings: list[Finding] = []
    for p in report["procs"]:
        env = p["env"]
        for key in CPU_PINS:
            if env.get(key, "").lower() == "cpu":
                findings.append(Finding(
                    "CRIT",
                    f"pid {p['pid']} ({p['args'][:60]}) is pinned to CPU by {key}=cpu",
                    f"restart it with {key} unset (CUDA is required on the Spark); check who owns it first",
                ))
        if env.get("CUDA_VISIBLE_DEVICES") == "":
            findings.append(Finding(
                "CRIT",
                f"pid {p['pid']} ({p['args'][:60]}) hides every GPU (CUDA_VISIBLE_DEVICES is empty)",
                "restart it with CUDA_VISIBLE_DEVICES unset",
            ))
    util = _num(report.get("gpu_util", ""))
    ml = [p for p in report["procs"] if _ml(p)]
    busy = sum(p["pcpu"] for p in ml)
    if util is not None and util <= GPU_IDLE_PCT and busy >= CPU_BOUND_PCT:
        top = max(ml, key=lambda p: p["pcpu"])
        findings.append(Finding(
            "WARN",
            f"GPU is {util:.0f}% busy while ML processes use {busy:.0f}% CPU (top: pid {top['pid']} {top['args'][:60]})",
            "check that job's device setting (NLLB_DEVICE, AOEP_ASR_DEVICE, CUDA_VISIBLE_DEVICES) and its /device endpoint",
        ))
    return findings


def render(report: dict, findings: list[Finding]) -> str:
    lines = [f"CUDA policy: host {report.get('host', '?')}  gpu_util={report.get('gpu_util', '?')}  cpus={report.get('cpus', '?')}"]
    if not findings:
        lines.append("  OK: nothing pinned to CPU and no GPU-idle/CPU-bound pattern")
    for f in findings:
        lines.append(f"  [{f.severity}] {f.message}\n         fix: {f.fix}")
    return "\n".join(lines)


def main() -> int:
    report = parse(sys.stdin.read())
    findings = analyze(report)
    print(render(report, findings))
    return 2 if any(f.severity == "CRIT" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
