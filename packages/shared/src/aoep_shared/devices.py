"""One place that decides which torch device a component runs on.

Policy (see docs/fleet-ops.txt):
  spark       CUDA is REQUIRED. A missing or broken CUDA fails fast with a clear message and an
              explicit CPU request (NLLB_DEVICE=cpu, CUDA_VISIBLE_DEVICES='') is ignored with a loud
              warning unless AOEP_ALLOW_CPU=1 is also set.
  kalel       (iBuyPower, RTX 5060 Ti) CUDA preferred, CPU allowed with a warning.
  mac / other MPS or CPU is fine.

The role comes from AOEP_HOST_ROLE, else ~/.config/aoep/host.env (a KEY=VALUE file), else a hostname
match (AOEP_SPARK_HOSTNAME_PATTERN, default "spark"). AOEP_REQUIRE_CUDA=1/0 overrides the role default.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("aoep.devices")

HOST_ENV_FILE = Path(os.environ.get("AOEP_HOST_ENV_FILE") or Path.home() / ".config" / "aoep" / "host.env")
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

_smoke_lock = threading.Lock()
_smoke_cache: Dict[str, Tuple[bool, str]] = {}


class DevicePolicyError(RuntimeError):
    """CUDA is required on this host but cannot be used."""


def _read_host_env() -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        for line in HOST_ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip("'\"")
    except OSError:
        pass
    return out


def _setting(name: str) -> str:
    return (os.environ.get(name) or _read_host_env().get(name) or "").strip()


def host_role() -> str:
    role = _setting("AOEP_HOST_ROLE").lower()
    if role in {"spark", "kalel", "mac", "other"}:
        return role
    pattern = (_setting("AOEP_SPARK_HOSTNAME_PATTERN") or "spark").lower()
    host = socket.gethostname().lower()
    if pattern and pattern in host:
        return "spark"
    if "kal-el" in host or "kalel" in host:
        return "kalel"
    return "other"


def _flag(name: str) -> Optional[bool]:
    raw = _setting(name).lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    return None


def require_cuda() -> bool:
    explicit = _flag("AOEP_REQUIRE_CUDA")
    return explicit if explicit is not None else host_role() == "spark"


def allow_cpu() -> bool:
    return bool(_flag("AOEP_ALLOW_CPU"))


def _torch():
    import torch

    return torch


def cuda_diagnostics(torch: Any = None) -> Dict[str, Any]:
    torch = torch or _torch()
    info: Dict[str, Any] = {
        "torch": getattr(torch, "__version__", "?"),
        "torch_cuda": getattr(getattr(torch, "version", None), "cuda", None),
        "cuda_available": False,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    try:
        info["cuda_available"] = bool(torch.cuda.is_available())
        if info["cuda_available"]:
            info["device_name"] = torch.cuda.get_device_name(0)
            major, minor = torch.cuda.get_device_capability(0)
            info["capability"] = f"sm_{major}{minor}"
            info["arch_list"] = list(torch.cuda.get_arch_list())
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def cuda_smoke(torch: Any = None) -> Tuple[bool, str]:
    """Run real kernels (matmul + fp16 Linear forward) so a build without kernels for this GPU's
    architecture (for example sm_121 on the GB10) fails at startup, not mid-job. Cached per process."""
    torch = torch or _torch()
    key = str(id(torch))
    with _smoke_lock:
        if key in _smoke_cache:
            return _smoke_cache[key]
        try:
            if not torch.cuda.is_available():
                result = (False, "torch.cuda.is_available() is False")
            else:
                a = torch.randn(64, 64, device="cuda")
                (a @ a).sum().item()
                lin = torch.nn.Linear(16, 16).to("cuda").half()
                lin(torch.randn(2, 16, device="cuda").half()).sum().item()
                torch.cuda.synchronize()
                result = (True, "ok")
        except Exception as exc:  # noqa: BLE001
            result = (False, f"{type(exc).__name__}: {exc}")
        _smoke_cache[key] = result
        return result


def _describe_failure(component: str, detail: str, torch: Any) -> str:
    d = cuda_diagnostics(torch)
    return (
        f"CUDA is required on this host (role={host_role()}) but is not usable for '{component}': {detail}. "
        f"torch={d.get('torch')} (cuda build {d.get('torch_cuda')}), capability={d.get('capability')}, "
        f"arch_list={d.get('arch_list')}, CUDA_VISIBLE_DEVICES={d.get('cuda_visible_devices')!r}. "
        "Fix the install (NVIDIA CUDA build of PyTorch for this GPU). Set AOEP_ALLOW_CPU=1 only to run on CPU "
        "on purpose."
    )


def pick_device(component: str, requested: Optional[str] = None, torch_module: Any = None) -> str:
    """Return 'cuda', 'mps' or 'cpu' for ``component`` under the host policy.

    ``requested`` is the component's own setting (for example NLLB_DEVICE); 'auto'/'' means no preference.
    """
    req = (requested or "").strip().lower()
    strict = require_cuda() and not allow_cpu()
    try:
        torch = torch_module or _torch()
    except ImportError as exc:
        if strict:
            raise DevicePolicyError(
                f"CUDA is required on this host (role={host_role()}) but PyTorch is not installed for '{component}': {exc}"
            ) from exc
        return "cpu"
    cpu_asked = req == "cpu" or os.environ.get("CUDA_VISIBLE_DEVICES") == ""

    if cpu_asked:
        if strict:
            log.warning(
                "%s: ignoring the CPU request (%s) because CUDA is required on this host. Set AOEP_ALLOW_CPU=1 "
                "to run on CPU deliberately.",
                component,
                "CUDA_VISIBLE_DEVICES=''" if os.environ.get("CUDA_VISIBLE_DEVICES") == "" else f"device={req}",
            )
            if os.environ.get("CUDA_VISIBLE_DEVICES") == "":
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        else:
            log.warning("%s: running on CPU by request (role=%s).", component, host_role())
            return "cpu"

    ok, detail = cuda_smoke(torch)
    if ok:
        return req if req.startswith("cuda") else "cuda"
    if strict:
        raise DevicePolicyError(_describe_failure(component, detail, torch))
    if host_role() == "kalel":
        log.warning("%s: CUDA unavailable (%s); falling back to CPU on a CUDA-preferred host.", component, detail)
        return "cpu"
    try:
        if getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def device_status(device: Optional[str] = None, torch_module: Any = None) -> Dict[str, Any]:
    """Health/readiness payload: the device actually in use and whether the policy is met."""
    try:
        torch = torch_module or _torch()
    except Exception as exc:  # noqa: BLE001
        return {"ok": not require_cuda(), "device": device or "unknown", "error": f"torch import failed: {exc}",
                "cuda_required": require_cuda(), "role": host_role()}
    required = require_cuda()
    policy_ok = True
    reason = ""
    if required and not allow_cpu() and (device or "cuda") != "cuda" and not str(device).startswith("cuda"):
        policy_ok, reason = False, f"CUDA required but device is {device}"
    status: Dict[str, Any] = {
        "role": host_role(),
        "cuda_required": required,
        "cpu_allowed": allow_cpu(),
        "device": device or "unknown",
        "ok": policy_ok,
    }
    if reason:
        status["reason"] = reason
    try:
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            status["gpu_free_mb"] = int(free / 1048576)
            status["gpu_total_mb"] = int(total / 1048576)
            status["gpu_name"] = torch.cuda.get_device_name(0)
    except Exception:  # noqa: BLE001
        pass
    return status


def _reset_for_tests() -> None:
    _smoke_cache.clear()
