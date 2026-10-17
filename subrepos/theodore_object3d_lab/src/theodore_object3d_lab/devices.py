"""What is installed, and which 3D cameras answer on USB."""

from __future__ import annotations

from typing import Any


TOOLS: tuple[dict[str, str], ...] = (
    {
        "name": "Theodore object3d lab",
        "use": "Browser console with the camera left on: aligned color, a depth map, questions, and enroll.",
        "command": "python3 -m uvicorn theodore_object3d_lab.main:app --port 8020 --host 127.0.0.1",
    },
    {
        "name": "object3d_pipeline.py",
        "use": "One scan of the RealSense, the OAK-D, or both. Prints distance and any trained name.",
        "command": "python3 scripts/object3d_pipeline.py --camera realsense",
    },
    {
        "name": "object3d_ask.py",
        "use": "Ask how far, animal, food, maker, year, sign translation, heat, smell, or touch.",
        "command": "python3 scripts/object3d_ask.py --camera realsense \"how far is it?\"",
    },
    {
        "name": "object3d_train.py",
        "use": "Enroll labeled views in parallel, including optional heat, smell, and texture.",
        "command": "python3 scripts/object3d_train.py --data output/object3d/samples --workers 8",
    },
    {
        "name": "Intel RealSense Viewer",
        "use": (
            "Official color, infrared, and depth viewer. It ships with a graphical "
            "librealsense build (realsense-viewer). This Spark uses the pyrealsense2 "
            "wheel, which streams frames and does not include that viewer."
        ),
        "command": "realsense-viewer",
    },
    {
        "name": "v4l2-ctl and ffplay",
        "use": "Show the RealSense UVC nodes. This is not aligned metric depth.",
        "command": "ffplay /dev/video0",
    },
    {
        "name": "Luxonis DepthAI demo",
        "use": (
            "Official OAK examples in the depthai-python repo (depthai_demo.py) or "
            "the DepthAI Viewer app. This lab uses the installed depthai package."
        ),
        "command": "python3 scripts/object3d_pipeline.py --camera oak",
    },
)


def _imports(name: str) -> bool:
    try:
        __import__(name)
    except Exception:
        return False
    return True


def sdk_status() -> dict[str, bool]:
    return {
        "pyrealsense2": _imports("pyrealsense2"),
        "depthai": _imports("depthai"),
        "torch": _imports("torch"),
        "pillow": _imports("PIL"),
    }


def connected_cameras() -> list[dict[str, Any]]:
    """List cameras that answer. A missing SDK is an error entry, not a crash."""
    found: list[dict[str, Any]] = []
    try:
        import pyrealsense2 as rs

        ctx = rs.context()
        devices = ctx.query_devices()
        if len(devices) == 0:
            found.append({"camera": "realsense", "connected": False})
        for dev in devices:
            found.append({
                "camera": "realsense",
                "connected": True,
                "name": dev.get_info(rs.camera_info.name),
                "serial": dev.get_info(rs.camera_info.serial_number),
                "firmware": dev.get_info(rs.camera_info.firmware_version),
            })
    except Exception as exc:
        found.append({"camera": "realsense", "connected": False, "error": str(exc)})
    try:
        import depthai as dai

        infos = dai.Device.getAllAvailableDevices()
        if not infos:
            found.append({"camera": "oak", "connected": False})
        for info in infos:
            found.append({
                "camera": "oak",
                "connected": True,
                "name": str(info.name),
                "mxid": str(info.deviceId),
                "state": str(info.state),
            })
    except Exception as exc:
        found.append({"camera": "oak", "connected": False, "error": str(exc)})
    return found
