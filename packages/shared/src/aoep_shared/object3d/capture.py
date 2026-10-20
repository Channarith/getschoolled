"""Grab RGB-D frames from the RealSense D435 or the OAK-D Lite.

The RealSense session stays open for the lab's live view. Depth is aligned
to the color camera, then a short spatial / temporal / nearest-hole pass
removes the speckle that otherwise looks like a torn depth picture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from .types import Frame

# Clear prefers detail. Smooth prefers a higher frame rate on a USB 2 link.
REALSENSE_MODES = {
    "clear": ((1280, 720, 6), (640, 480, 15), (640, 480, 6)),
    "smooth": ((640, 480, 15), (640, 480, 6)),
    "fast": ((640, 480, 6),),
}


def _set_option(sensor, option, value) -> None:
    try:
        if sensor is None or not sensor.supports(option):
            return
        rng = sensor.get_option_range(option)
        number = float(value)
        if rng.step:
            steps = round((number - rng.min) / rng.step)
            number = rng.min + steps * rng.step
        number = min(float(rng.max), max(float(rng.min), number))
        sensor.set_option(option, float(number))
    except Exception:
        return


def _tune_filters(rs, spatial, temporal, hole) -> None:
    # holes_fill 2 on the spatial filter is a 4-pixel fill, not "fill the frame".
    # The dedicated hole filter's mode 2 copies the nearest pixel. Mode 0 smears
    # from the left edge and looks corrupted.
    _set_option(spatial, rs.option.filter_magnitude, 2)
    _set_option(spatial, rs.option.filter_smooth_alpha, 0.5)
    _set_option(spatial, rs.option.filter_smooth_delta, 20)
    _set_option(spatial, rs.option.holes_fill, 2)
    _set_option(temporal, rs.option.filter_smooth_alpha, 0.35)
    _set_option(temporal, rs.option.filter_smooth_delta, 20)
    _set_option(hole, rs.option.holes_fill, 2)


def _color_sensor(device, rs):
    for sensor in device.query_sensors():
        try:
            name = sensor.get_info(rs.camera_info.name)
        except Exception:
            continue
        if "RGB" in name:
            return sensor
    return None


class RealSenseSession:
    """One open D435 pipeline. Call ``stop`` before opening it again."""

    def __init__(self) -> None:
        self.mode = ""
        self.usb = ""
        self.depth_scale = 0.001
        self._rs = None
        self._pipeline = None
        self._align = None
        self._spatial = None
        self._temporal = None
        self._hole = None
        self._depth_sensor = None
        self._color_sensor = None
        self._last_depth = None

    def start(self, modes: tuple[tuple[int, int, int], ...], checks: int = 2) -> str:
        import pyrealsense2 as rs

        self._rs = rs
        last = "no mode worked"
        for width, height, fps in modes:
            self.stop()
            pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.depth, int(width), int(height), rs.format.z16, int(fps))
            config.enable_stream(rs.stream.color, int(width), int(height), rs.format.rgb8, int(fps))
            try:
                profile = pipeline.start(config)
            except Exception as exc:
                last = str(exc)
                try:
                    pipeline.stop()
                except Exception:
                    pass
                continue
            self._pipeline = pipeline
            self._align = rs.align(rs.stream.color)
            self._spatial = rs.spatial_filter()
            self._temporal = rs.temporal_filter()
            self._hole = rs.hole_filling_filter()
            _tune_filters(rs, self._spatial, self._temporal, self._hole)
            device = profile.get_device()
            self._depth_sensor = device.first_depth_sensor()
            self._color_sensor = _color_sensor(device, rs)
            self.depth_scale = float(self._depth_sensor.get_depth_scale())
            try:
                self.usb = device.get_info(rs.camera_info.usb_type_descriptor)
            except Exception:
                self.usb = ""
            self.mode = f"{width}x{height}@{fps}"
            try:
                for _ in range(max(1, checks)):
                    self.read(timeout_ms=4000, filters=True)
            except Exception as exc:
                last = str(exc)
                self.stop()
                continue
            return self.mode
        raise RuntimeError(f"RealSense did not start ({last})")

    def apply(
        self,
        *,
        preset: float = 4,
        laser: float = 210,
        emitter: bool = True,
        auto_exposure: bool = True,
        exposure: float = 166,
        gain: float = 64,
        brightness: float = 8,
        contrast: float = 58,
        sharpness: float = 70,
        saturation: float = 64,
        auto_white_balance: bool = True,
        white_balance: float = 4600,
        backlight: bool = False,
    ) -> None:
        rs = self._rs
        if rs is None:
            return
        depth = self._depth_sensor
        # Preset first. It resets the other depth options, including the laser.
        _set_option(depth, rs.option.visual_preset, preset)
        _set_option(depth, rs.option.emitter_enabled, 1 if emitter else 0)
        if emitter:
            _set_option(depth, rs.option.laser_power, laser)
        color = self._color_sensor
        if color is None:
            return
        _set_option(color, rs.option.enable_auto_exposure, 1 if auto_exposure else 0)
        if not auto_exposure:
            _set_option(color, rs.option.exposure, exposure)
            _set_option(color, rs.option.gain, gain)
        _set_option(color, rs.option.brightness, brightness)
        _set_option(color, rs.option.contrast, contrast)
        _set_option(color, rs.option.sharpness, sharpness)
        _set_option(color, rs.option.saturation, saturation)
        _set_option(color, rs.option.enable_auto_white_balance, 1 if auto_white_balance else 0)
        if not auto_white_balance:
            _set_option(color, rs.option.white_balance, white_balance)
        _set_option(color, rs.option.backlight_compensation, 1 if backlight else 0)

    def read(self, timeout_ms: int = 5000, filters: bool = True) -> Frame:
        if self._pipeline is None or self._align is None:
            raise RuntimeError("RealSense session is not started")
        frames = self._pipeline.wait_for_frames(int(timeout_ms))
        aligned = self._align.process(frames)
        color = aligned.get_color_frame()
        depth_frame = aligned.get_depth_frame()
        if not color or not depth_frame:
            raise RuntimeError("RealSense is missing color or depth")
        if filters and self._spatial is not None:
            try:
                depth_frame = self._spatial.process(depth_frame)
                depth_frame = self._temporal.process(depth_frame)
                depth_frame = self._hole.process(depth_frame)
            except Exception:
                pass
        self._last_depth = depth_frame
        rgb = np.asanyarray(color.get_data()).copy()
        depth = np.asanyarray(depth_frame.get_data()).copy()
        return Frame(rgb=rgb, depth=depth, depth_scale=self.depth_scale, camera="realsense")

    def stop(self) -> None:
        pipeline = self._pipeline
        self._pipeline = None
        self._align = None
        self._last_depth = None
        self._depth_sensor = None
        self._color_sensor = None
        if pipeline is not None:
            try:
                pipeline.stop()
            except Exception:
                pass


class OakSession:
    """One open OAK-D pipeline. Stereo is attempted once, then color-only."""

    def __init__(self) -> None:
        self.mode = ""
        self.usb = ""
        self.depth_ok = False
        self._cm = None
        self._color_q = None
        self._depth_q = None

    def start(self, width: int = 1280, height: int = 720) -> str:
        self.stop()
        errors: list[str] = []
        for with_depth in (True, False):
            try:
                self._open(width, height, with_depth)
                frame = self.read(timeout=3 if with_depth else 5)
                if with_depth and (frame is None or frame.depth is None):
                    frame = self.read(timeout=1.5)
            except Exception as exc:
                errors.append(str(exc))
                self.stop()
                continue
            if frame is None:
                errors.append("no color frame")
                self.stop()
                continue
            if with_depth and frame.depth is None:
                errors.append("stereo produced no depth")
                self.stop()
                continue
            self.depth_ok = frame.depth is not None
            self.mode = f"{width}x{height}" + ("+depth" if self.depth_ok else " color")
            return self.mode
        raise RuntimeError("OAK-D did not start ({})".format("; ".join(errors) or "no pipeline"))

    def _open(self, width: int, height: int, with_depth: bool) -> None:
        import depthai as dai

        pipeline = dai.Pipeline()
        entered = pipeline.__enter__()
        cam = entered.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        color_q = cam.requestOutput((int(width), int(height)), fps=15).createOutputQueue()
        depth_q = None
        if with_depth:
            left = entered.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
            right = entered.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
            stereo = entered.create(dai.node.StereoDepth).build(left=left, right=right)
            depth_out = stereo.depth if not callable(stereo.depth) else stereo.depth()
            depth_q = depth_out.createOutputQueue()
        entered.start()
        self._cm = pipeline
        self._color_q = color_q
        self._depth_q = depth_q

    def read(self, timeout: float = 1.0) -> Optional[Frame]:
        import time

        if self._color_q is None:
            raise RuntimeError("OAK-D session is not started")
        deadline = time.monotonic() + timeout
        color = None
        while time.monotonic() < deadline:
            color = self._color_q.tryGet()
            if color is not None:
                break
            time.sleep(0.02)
        if color is None:
            return None
        rgb = np.asarray(color.getCvFrame())
        if rgb.ndim == 3 and rgb.shape[2] == 3:
            rgb = rgb[:, :, ::-1].copy()
        else:
            rgb = np.asarray(rgb).copy()
        depth = None
        if self._depth_q is not None:
            msg = self._depth_q.tryGet()
            if msg is not None:
                depth = np.asarray(msg.getFrame()).copy()
        return Frame(rgb=rgb, depth=depth, depth_scale=0.001, camera="oak")

    def stop(self) -> None:
        cm = self._cm
        self._cm = None
        self._color_q = None
        self._depth_q = None
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass


def capture_realsense(*, width: int = 640, height: int = 480, fps: int = 6, warmup: int = 8) -> Frame:
    """Aligned color and depth. Depth values stay millimeters."""
    session = RealSenseSession()
    modes = ((width, height, fps), (640, 480, 6))
    session.start(modes)
    session.apply()
    try:
        frame = None
        for _ in range(max(1, warmup)):
            frame = session.read(filters=True)
        if frame is None:
            raise RuntimeError("RealSense returned no frames")
        return frame
    finally:
        session.stop()


def _capture_oak_pipeline(*, width: int, height: int, with_depth: bool) -> Frame:
    session = OakSession()
    session._open(width, height, with_depth)
    try:
        frame = session.read(timeout=8 if with_depth else 4)
        if frame is None:
            raise RuntimeError("OAK-D returned no color frame")
        if with_depth and frame.depth is None:
            # One extra wait. USB 2 often never produces stereo.
            import time
            time.sleep(0.4)
            again = session.read(timeout=2)
            if again is not None and again.depth is not None:
                return again
        return frame
    finally:
        session.stop()


WEBCAM_MODES = {
    "clear": ((3840, 2160, 30), (1920, 1080, 30), (1280, 720, 30)),
    "smooth": ((1920, 1080, 30), (1280, 720, 30)),
    "fast": ((1280, 720, 30),),
}


def v4l_nodes(root: Optional[Path] = None) -> list[tuple[str, str, int]]:
    """``(device path, card name, node index)`` for every video4linux node."""
    base = Path(root) if root is not None else Path("/sys/class/video4linux")
    found: list[tuple[str, str, int]] = []
    if not base.is_dir():
        return found
    for node in sorted(base.iterdir()):
        if not node.name.startswith("video"):
            continue
        try:
            name = (node / "name").read_text(encoding="utf-8").strip()
            index = int((node / "index").read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            continue
        found.append((f"/dev/{node.name}", name, index))
    return found


def choose_uhd_webcam(
    nodes: Optional[list[tuple[str, str, int]]] = None,
) -> Optional[tuple[str, str]]:
    """The capture node of the 4K webcam, skipping RealSense video nodes."""
    rows = v4l_nodes() if nodes is None else nodes
    candidates = [
        (path, name, index)
        for path, name, index in rows
        if index == 0 and "realsense" not in name.casefold()
    ]
    if not candidates:
        return None

    def rank(row: tuple[str, str, int]) -> tuple[int, str]:
        label = row[1].casefold()
        if "ac310" in label:
            return (0, row[0])
        if "4k" in label or "ultra" in label:
            return (1, row[0])
        return (2, row[0])

    path, name, _index = sorted(candidates, key=rank)[0]
    return path, name


class WebcamSession:
    """The USB 4K webcam. It has color only, so detection uses the picture."""

    def __init__(self) -> None:
        self.mode = ""
        self.usb = ""
        self.name = ""
        self.path = ""
        self._cap = None

    def start(self, modes: tuple[tuple[int, int, int], ...]) -> str:
        import cv2

        chosen = choose_uhd_webcam()
        if chosen is None:
            raise RuntimeError("No 4K webcam is connected")
        path, name = chosen
        last = "no mode worked"
        for width, height, fps in modes:
            self.stop()
            cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
            if not cap.isOpened():
                last = f"could not open {path}"
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
            cap.set(cv2.CAP_PROP_FPS, int(fps))
            ok = False
            for _ in range(4):
                ok, _frame = cap.read()
                if ok and _frame is not None:
                    break
            if not ok:
                last = f"{name} returned no frame at {width}x{height}"
                cap.release()
                continue
            got_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or width)
            got_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or height)
            got_fps = int(round(float(cap.get(cv2.CAP_PROP_FPS) or fps)))
            self._cap = cap
            self.path = path
            self.name = name.split(":")[0].strip() or name
            self.mode = f"{got_w}x{got_h}@{got_fps or fps}"
            return self.mode
        raise RuntimeError(f"4K webcam did not start ({last})")

    def read(self, timeout: float = 1.0) -> Optional[Frame]:
        import cv2

        cap = self._cap
        if cap is None:
            return None
        ok, bgr = cap.read()
        if not ok or bgr is None:
            return None
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return Frame(rgb=rgb, depth=None, camera="webcam")

    def stop(self) -> None:
        cap = self._cap
        self._cap = None
        if cap is not None:
            cap.release()


def capture_webcam(*, quality: str = "clear") -> Frame:
    """One color frame from the 4K webcam. Clear asks for 3840x2160."""
    session = WebcamSession()
    session.start(WEBCAM_MODES.get(quality, WEBCAM_MODES["clear"]))
    try:
        frame = session.read()
        if frame is None:
            raise RuntimeError("4K webcam returned no frame")
        return frame
    finally:
        session.stop()


def capture_oak(*, width: int = 640, height: int = 400, with_depth: bool = True) -> Frame:
    """Color from the OAK-D Lite, plus stereo depth when the link can carry it."""
    if with_depth:
        try:
            frame = _capture_oak_pipeline(width=width, height=height, with_depth=True)
            if frame.depth is not None:
                return frame
        except Exception:
            pass
    return _capture_oak_pipeline(width=width, height=height, with_depth=False)


def capture(camera: str) -> Frame:
    name = (camera or "").casefold()
    if name in ("realsense", "d435", "intel"):
        return capture_realsense()
    if name in ("oak", "oak-d", "luxonis"):
        return capture_oak()
    if name in ("webcam", "4k", "uhd", "ac310", "ultra"):
        return capture_webcam()
    raise ValueError(f"unknown camera {camera!r} (use realsense, oak, or webcam)")
