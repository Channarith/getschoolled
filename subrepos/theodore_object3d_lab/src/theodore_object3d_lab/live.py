"""Keep one 3D camera streaming so the lab is not a click-to-snap page."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

import numpy as np

from aoep_shared.object3d.capture import REALSENSE_MODES, OakSession, RealSenseSession
from aoep_shared.object3d.cli import DEFAULT_SAMPLES
from aoep_shared.object3d.collect import AngleCapture
from aoep_shared.object3d.depth import align_depth
from aoep_shared.object3d.pipeline import crop_rgb
from aoep_shared.object3d.types import Frame

from .preview import (
    colorize_depth,
    draw_overlay,
    enhance_color,
    jpeg_bytes,
    no_depth_view,
    waiting_image,
)

PRESETS = (
    (0, "Custom"),
    (1, "Default"),
    (2, "Hand"),
    (3, "High accuracy"),
    (4, "High density"),
    (5, "Medium density"),
    (6, "Remove IR pattern"),
)

CONTROL_SPEC: tuple[dict[str, Any], ...] = (
    {"kind": "check", "id": "auto_exposure", "label": "Auto exposure", "group": "image"},
    {"kind": "range", "id": "exposure", "label": "Exposure", "min": 0, "max": 10000, "step": 10, "group": "image"},
    {"kind": "range", "id": "gain", "label": "Gain", "min": 0, "max": 128, "step": 1, "group": "image"},
    {"kind": "range", "id": "brightness", "label": "Brightness", "min": -64, "max": 64, "step": 1, "group": "image"},
    {"kind": "range", "id": "contrast", "label": "Contrast", "min": 0, "max": 100, "step": 1, "group": "image"},
    {"kind": "range", "id": "sharpness", "label": "Sharpness", "min": 0, "max": 100, "step": 1, "group": "image"},
    {"kind": "range", "id": "saturation", "label": "Saturation", "min": 0, "max": 100, "step": 1, "group": "image"},
    {"kind": "check", "id": "auto_white_balance", "label": "Auto white balance", "group": "image"},
    {"kind": "range", "id": "white_balance", "label": "White balance", "min": 2800, "max": 6500, "step": 10, "group": "image"},
    {"kind": "check", "id": "backlight", "label": "Backlight", "group": "image"},
    {"kind": "check", "id": "clahe", "label": "CLAHE contrast", "group": "image"},
    {"kind": "range", "id": "sharpen", "label": "Sharpen preview", "min": 0, "max": 1.5, "step": 0.05, "group": "image"},
    {"kind": "check", "id": "rotate", "label": "Rotate 180", "group": "image"},
    {"kind": "select", "id": "preset", "label": "Depth preset", "options": PRESETS, "group": "depth"},
    {"kind": "range", "id": "laser", "label": "Laser", "min": 0, "max": 360, "step": 30, "group": "depth"},
    {"kind": "check", "id": "emitter", "label": "Emitter on", "group": "depth"},
    {"kind": "check", "id": "depth_filters", "label": "Stabilize depth", "group": "depth"},
    {"kind": "check", "id": "fill_holes", "label": "Fill small holes", "group": "depth"},
    {"kind": "check", "id": "auto_range", "label": "Auto depth range", "group": "depth"},
    {"kind": "range", "id": "near_m", "label": "Near (m)", "min": 0.15, "max": 3, "step": 0.05, "group": "depth"},
    {"kind": "range", "id": "far_m", "label": "Far (m)", "min": 0.4, "max": 8, "step": 0.1, "group": "depth"},
    {"kind": "check", "id": "overlay", "label": "Show objects", "group": "depth"},
)


@dataclass
class LiveControls:
    camera: str = "realsense"
    quality: str = "clear"
    detector: str = "auto"
    auto_exposure: bool = True
    exposure: float = 170
    gain: float = 64
    brightness: float = 8
    contrast: float = 58
    sharpness: float = 50
    saturation: float = 64
    auto_white_balance: bool = True
    white_balance: float = 4600
    backlight: bool = False
    clahe: bool = True
    sharpen: float = 0.15
    rotate: bool = False
    preset: float = 4
    laser: float = 210
    emitter: bool = True
    depth_filters: bool = True
    fill_holes: bool = True
    auto_range: bool = True
    near_m: float = 0.3
    far_m: float = 4.0
    overlay: bool = True


_SENSOR = {
    "auto_exposure", "exposure", "gain", "brightness", "contrast", "sharpness",
    "saturation", "auto_white_balance", "white_balance", "backlight",
    "preset", "laser", "emitter",
}
_BOOLS = {
    "auto_exposure", "auto_white_balance", "backlight", "clahe", "rotate",
    "emitter", "depth_filters", "fill_holes", "auto_range", "overlay",
}
_FLOATS = {
    "exposure", "gain", "brightness", "contrast", "sharpness", "saturation",
    "white_balance", "sharpen", "preset", "laser", "near_m", "far_m",
}


def _realsense_usb() -> str:
    try:
        import pyrealsense2 as rs
    except Exception:
        return ""
    try:
        for dev in rs.context().query_devices():
            return str(dev.get_info(rs.camera_info.usb_type_descriptor))
    except Exception:
        return ""
    return ""


def _camera_name(camera: str) -> str:
    name = (camera or "").casefold()
    if name in ("realsense", "d435", "intel"):
        return "realsense"
    if name in ("oak", "oak-d", "luxonis"):
        return "oak"
    raise ValueError(f"unknown camera {camera!r} (use realsense or oak)")


class LiveHub:
    def __init__(self) -> None:
        self.controls = LiveControls()
        self.observe = None
        self.running = False
        self.error = ""
        self.mode = ""
        self.usb = ""
        self.note = ""
        self.fps = 0.0
        self.stats: dict[str, Any] = {}
        self._ops = threading.Lock()
        self._lock = threading.Lock()
        self._gen = 0
        self._control_gen = 0
        self._applied = -1
        self._ready = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._session: Any = None
        self._frame: Optional[Frame] = None
        self._observations: list[Any] = []
        self._seq = 0
        self._color = jpeg_bytes(waiting_image("Starting the camera"))
        self._depth = self._color
        self._times: list[float] = []
        self.frozen = False
        self.selected: Optional[int] = None
        self.capture: Optional[AngleCapture] = None
        self.samples_root = DEFAULT_SAMPLES
        self._capture_lock = threading.Lock()
        self._view_color: Optional[np.ndarray] = None
        self._view_depth: Optional[np.ndarray] = None

    def controls_dict(self) -> dict[str, Any]:
        return asdict(self.controls)

    def update(self, data: dict[str, Any]) -> None:
        with self._lock:
            for key, value in data.items():
                if not hasattr(self.controls, key) or key not in (*_BOOLS, *_FLOATS, "camera", "quality", "detector"):
                    continue
                if key in _BOOLS:
                    setattr(self.controls, key, bool(value))
                elif key in _FLOATS:
                    setattr(self.controls, key, float(value))
                else:
                    setattr(self.controls, key, str(value))
                if key in _SENSOR:
                    self._control_gen += 1

    def reset_controls(self) -> None:
        camera = self.controls.camera
        quality = self.controls.quality
        detector = self.controls.detector
        with self._lock:
            self.controls = LiveControls(camera=camera, quality=quality, detector=detector)
            self._control_gen += 1

    def start(self, camera: str, quality: str) -> dict[str, Any]:
        name = _camera_name(camera)
        quality = quality if quality in REALSENSE_MODES else "clear"
        with self._ops:
            self._stop_locked()
            with self._lock:
                self.controls.camera = name
                self.controls.quality = quality
                self._gen += 1
                self.error = ""
                self.running = False
                self.frozen = False
                self.selected = None
                self._ready.clear()
            self._thread = threading.Thread(target=self._run, name="object3d-live", daemon=True)
            self._thread.start()
            self._ready.wait(28)
            if self.error or not self.running:
                message = self.error or "camera did not deliver a frame"
                self._stop_locked()
                raise RuntimeError(message)
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._ops:
            self._stop_locked()
            return self.status()

    def _stop_locked(self) -> None:
        self._gen += 1
        session = self._session
        self._session = None
        if session is not None:
            session.stop()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=4)
        self._thread = None
        self.running = False
        job = self.capture
        if job is not None and job.active:
            job.stop("camera stopped")

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.running,
                "camera": self.controls.camera,
                "quality": self.controls.quality,
                "mode": self.mode,
                "usb": self.usb,
                "note": self.note,
                "fps": round(self.fps, 1),
                "error": self.error,
                "stats": dict(self.stats),
                "seq": self._seq,
                "frozen": self.frozen,
                "selected": self.selected,
                "observations": [obs.to_dict() for obs in self._observations],
                "capture": self._capture_status(),
                "controls": asdict(self.controls),
            }

    def _capture_status(self) -> dict[str, Any]:
        job = self.capture
        if job is None:
            return {"active": False, "label": "", "saved": 0, "reason": "", "folder": ""}
        return job.status()

    def frame_copy(self) -> Optional[Frame]:
        with self._lock:
            frame = self._frame
            if frame is None:
                return None
            return Frame(
                rgb=np.array(frame.rgb, copy=True),
                depth=None if frame.depth is None else np.array(frame.depth, copy=True),
                depth_scale=frame.depth_scale,
                camera=frame.camera,
                sensors=frame.sensors,
            )

    def observations(self) -> list[Any]:
        with self._lock:
            return list(self._observations)

    def jpeg(self, view: str) -> bytes:
        with self._lock:
            return self._depth if view == "depth" else self._color

    def set_frozen(self, frozen: bool) -> dict[str, Any]:
        with self._lock:
            self.frozen = bool(frozen)
            if not self.frozen:
                self.selected = None
        return self.status()

    def pick(self, x: float, y: float) -> dict[str, Any]:
        if not (0.0 <= float(x) <= 1.0 and 0.0 <= float(y) <= 1.0):
            return {"ok": False, "error": "click the picture"}
        with self._lock:
            frame = self._frame
            observations = list(self._observations)
            color = None if self._view_color is None else self._view_color
            depth_image = None if self._view_depth is None else self._view_depth
            if frame is None:
                return {"ok": False, "error": "no frame yet"}
            self.frozen = True
            height, width = frame.rgb.shape[:2]
            index = _hit_index(observations, float(x) * width, float(y) * height)
            self.selected = index
        if index is None:
            body = self.status()
            body.update({"ok": False, "error": "click an object box"})
            return body
        self._repaint(color, depth_image, observations)
        obs = observations[index]
        body = self.status()
        body.update({
            "ok": True,
            "index": index,
            "label": obs.label,
            "name": obs.name,
            "bbox": list(obs.bbox),
        })
        return body

    def select_index(self, index: int) -> dict[str, Any]:
        with self._lock:
            observations = list(self._observations)
            color = None if self._view_color is None else self._view_color
            depth_image = None if self._view_depth is None else self._view_depth
            if index < 0 or index >= len(observations):
                return {"ok": False, "error": "no object at that index"}
            self.frozen = True
            self.selected = int(index)
        self._repaint(color, depth_image, observations)
        obs = observations[index]
        body = self.status()
        body.update({
            "ok": True,
            "index": index,
            "label": obs.label,
            "name": obs.name,
            "bbox": list(obs.bbox),
        })
        return body

    def label_and_capture(
        self,
        label: str,
        *,
        index: Optional[int] = None,
        maker: str = "",
        year: int = 0,
        celsius: Optional[float] = None,
        smell: str = "",
        texture: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            frame = self._frame
            observations = list(self._observations)
            chosen = self.selected if index is None else index
        if frame is None:
            return {"ok": False, "error": "no frame yet"}
        if not observations:
            return {"ok": False, "error": "no object to label"}
        if chosen is None or chosen < 0 or chosen >= len(observations):
            chosen = 0
        obs = observations[chosen]
        try:
            job = AngleCapture.begin(
                self.samples_root,
                label,
                crop_rgb(frame.rgb, obs.bbox),
                obs.bbox,
                now=time.monotonic(),
                kind=obs.kind,
                maker=maker,
                year=year or None,
                heat_c=celsius,
                smell=smell,
                texture=texture,
                camera=frame.camera,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        with self._capture_lock:
            self.capture = job
        with self._lock:
            self.frozen = False
            self.selected = chosen
        body = self.status()
        body["ok"] = True
        return body

    def stop_capture(self) -> dict[str, Any]:
        with self._capture_lock:
            job = self.capture
            if job is not None and job.active:
                job.stop("stopped")
        body = self.status()
        body["ok"] = True
        return body

    def _repaint(self, color: Optional[np.ndarray], depth_image: Optional[np.ndarray], observations: list[Any]) -> None:
        if color is None:
            return
        with self._lock:
            selected = self.selected
        burned_color, burned_depth = self._burn(
            color,
            color if depth_image is None else depth_image,
            observations,
            selected,
        )
        with self._lock:
            self._color = jpeg_bytes(burned_color)
            self._depth = jpeg_bytes(burned_depth)

    def _burn(self, color, depth_image, observations, selected):
        if self.controls.overlay and observations:
            color = draw_overlay(color, observations, selected=selected)
            depth_image = draw_overlay(depth_image, observations, selected=selected)
        return color, depth_image

    def _run(self) -> None:
        gen = self._gen
        session = None
        try:
            session = self._open()
            self._session = session
            with self._lock:
                self.mode = session.mode
                self.usb = getattr(session, "usb", "") or ""
                self.running = True
                self.error = ""
            misses = 0
            tick = 0
            while gen == self._gen:
                self._apply(session)
                try:
                    if isinstance(session, RealSenseSession):
                        frame = session.read(timeout_ms=2000, filters=self.controls.depth_filters)
                    else:
                        frame = session.read(timeout=1.0)
                except Exception as exc:
                    misses += 1
                    if misses <= 8:
                        continue
                    raise RuntimeError(f"camera stopped delivering frames ({exc})") from exc
                if frame is None:
                    misses += 1
                    if misses > 25:
                        raise RuntimeError("camera stopped delivering frames")
                    continue
                misses = 0
                tick += 1
                stride = 3 if self.controls.detector == "coco" else 1
                try:
                    self._publish(frame, detect=tick % stride == 0)
                except Exception:
                    continue
                self._ready.set()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            with self._lock:
                self.error = str(exc)
                self.running = False
            self._ready.set()
        finally:
            if session is not None:
                session.stop()
            with self._lock:
                if gen == self._gen:
                    self.running = False

    def _open(self):
        controls = self.controls
        if controls.camera == "oak":
            width, height = (1280, 720) if controls.quality == "clear" else (640, 400)
            session = OakSession()
            session.start(width, height)
            return session
        modes = REALSENSE_MODES[controls.quality]
        usb = _realsense_usb()
        # 1280x720 color plus depth does not stay up on a USB 2 link. It returns
        # one frame and then the pipeline times out, which looks like a dead view.
        if controls.quality == "clear" and usb.startswith("2"):
            modes = REALSENSE_MODES["smooth"]
            self.note = (
                f"USB {usb} cannot hold 720p. Streaming 640x480. "
                "A USB 3 cable is what makes the picture sharper."
            )
        else:
            self.note = ""
        last = "no mode"
        for mode in modes:
            session = RealSenseSession()
            try:
                session.start((mode,), checks=2)
                self._applied = -1
                self._apply(session)
                session.read(timeout_ms=3000, filters=controls.depth_filters)
                return session
            except Exception as exc:
                last = str(exc)
                session.stop()
        raise RuntimeError(f"RealSense did not start ({last})")

    def _apply(self, session) -> None:
        if not isinstance(session, RealSenseSession):
            return
        with self._lock:
            gen = self._control_gen
            controls = self.controls
        if gen == self._applied:
            return
        session.apply(
            preset=controls.preset,
            laser=controls.laser,
            emitter=controls.emitter,
            auto_exposure=controls.auto_exposure,
            exposure=controls.exposure,
            gain=controls.gain,
            brightness=controls.brightness,
            contrast=controls.contrast,
            sharpness=controls.sharpness,
            saturation=controls.saturation,
            auto_white_balance=controls.auto_white_balance,
            white_balance=controls.white_balance,
            backlight=controls.backlight,
        )
        self._applied = gen

    def _publish(self, frame: Frame, detect: bool) -> None:
        controls = self.controls
        rgb = frame.rgb
        depth = frame.depth
        if depth is not None and depth.shape[:2] != rgb.shape[:2]:
            depth = align_depth(depth, rgb.shape)
            frame = Frame(
                rgb=rgb,
                depth=depth,
                depth_scale=frame.depth_scale,
                camera=frame.camera,
                sensors=frame.sensors,
            )
        if controls.rotate:
            rgb = np.rot90(rgb, 2)
            if depth is not None:
                depth = np.rot90(depth, 2)
            frame = Frame(
                rgb=rgb,
                depth=depth,
                depth_scale=frame.depth_scale,
                camera=frame.camera,
                sensors=frame.sensors,
            )
        observations = self._observations
        if detect and self.observe is not None:
            try:
                observations = list(self.observe(frame))
            except Exception:
                observations = self._observations
        color = enhance_color(rgb, clahe=controls.clahe, sharpen=controls.sharpen)
        if depth is None:
            depth_image = no_depth_view(rgb, "No stereo depth on this link")
            stats = {
                "coverage": 0.0,
                "scene_near_m": None,
                "scene_far_m": None,
                "hint": "No stereo depth on this link. Object boxes come from the color image.",
            }
        else:
            depth_image, stats = colorize_depth(
                depth,
                frame.depth_scale,
                rgb,
                near_m=controls.near_m,
                far_m=controls.far_m,
                auto_range=controls.auto_range,
                fill_holes=controls.fill_holes,
            )
        now = time.monotonic()
        self._times.append(now)
        self._times = [stamp for stamp in self._times if now - stamp < 2.0]
        fps = 0.0
        if len(self._times) >= 2:
            span = self._times[-1] - self._times[0]
            if span > 0:
                fps = (len(self._times) - 1) / span
        with self._lock:
            frozen = self.frozen
        if frozen:
            with self._lock:
                self.fps = fps
                self.stats = stats
            return
        selected = None
        with self._capture_lock:
            job = self.capture
            if job is not None and job.active:
                selected = job.step(frame, observations, now=now, fps=fps)
        burned_color, burned_depth = self._burn(color, depth_image, observations, selected)
        with self._lock:
            if self.frozen:
                self.fps = fps
                self.stats = stats
                return
            self._view_color = color
            self._view_depth = depth_image
            self._frame = frame
            self._observations = observations
            self.selected = selected
            self._seq += 1
            self._color = jpeg_bytes(burned_color)
            self._depth = jpeg_bytes(burned_depth)
            self.stats = stats
            self.fps = fps


def _hit_index(observations: list[Any], x: float, y: float) -> Optional[int]:
    """Smallest box that contains the click, in frame pixels."""
    inside: list[tuple[float, int]] = []
    for index, obs in enumerate(observations):
        bx, by, bw, bh = (float(value) for value in obs.bbox)
        if bx <= x <= bx + bw and by <= y <= by + bh:
            inside.append((bw * bh, index))
    if not inside:
        return None
    inside.sort()
    return inside[0][1]
