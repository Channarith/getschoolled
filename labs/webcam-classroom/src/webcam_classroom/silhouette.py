"""Single-frame silhouette detection for the webcam classroom.

Answers three questions about one webcam frame, with a transparent, CPU-only,
model-free heuristic (in the same spirit as ``aoep_shared.vision.engagement``):

  * is a human silhouette present in view,
  * how much of the frame do they occupy (coverage 0..1), and
  * where is the silhouette centred (for framing / "step back into view").

Approach (deliberately explainable, deterministic, and testable):
  1. Reduce the frame to a small luminance grid (default 32x32) so the maths is
     cheap and stable regardless of camera resolution.
  2. Estimate the background from the grid border (a webcam subject is centred
     against a background, so the border is mostly background).
  3. Mark grid cells that differ from the background beyond ``foreground_delta``
     as foreground. Coverage = fraction of foreground cells; the centroid and the
     connected-component count come from that mask.

Inputs accepted by :func:`detect_silhouette`:
  * a numpy ndarray (H, W) grayscale or (H, W, 3/4) colour,
  * a pre-reduced grid as ``list[list[float]]`` (0..1 luminance) - the pure path,
  * encoded image ``bytes`` (JPEG/PNG) - decoded via OpenCV or Pillow when present.

There is also :func:`silhouette_from_faces`, which derives a reading from the
platform's face observations (the hybrid/group path only ships embeddings + bbox,
never raw frames), so group classes get a silhouette signal without a frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

# Silhouette states.
PRESENT = "present"      # a clear, sufficiently large silhouette is in view
PARTIAL = "partial"      # something is there but small/edge (leaning out of view)
ABSENT = "absent"        # no meaningful silhouette (empty chair)
UNKNOWN = "unknown"      # could not be determined (undecodable / no data)

GRID = 32  # reduced grid side used for the heuristic

FrameLike = Union[bytes, bytearray, "object", List[List[float]]]


class SilhouetteUnavailable(RuntimeError):
    """Raised when an encoded frame cannot be decoded (no cv2/Pillow, bad data)."""


@dataclass
class SilhouetteReading:
    """Result of analysing a single frame.

    ``coverage`` is the fraction (0..1) of the frame occupied by the largest
    silhouette; ``centroid`` is its normalised (x, y) centre; ``regions`` is how
    many distinct foreground blobs were found (useful to flag "more than one
    person in a solo session").
    """

    state: str
    present: bool
    coverage: float
    centroid: Tuple[float, float]
    regions: int
    confidence: float
    source: str = "frame"
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "present": self.present,
            "coverage": round(self.coverage, 4),
            "centroid": [round(self.centroid[0], 4), round(self.centroid[1], 4)],
            "regions": self.regions,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "detail": self.detail,
        }


@dataclass
class SilhouetteConfig:
    present_coverage: float = 0.10
    partial_coverage: float = 0.03
    foreground_delta: float = 0.18
    grid: int = GRID


# --------------------------------------------------------------------------- #
# Frame reduction (to a small luminance grid, 0..1)
# --------------------------------------------------------------------------- #
def _grid_from_ndarray(img, grid: int) -> List[List[float]]:
    import numpy as np

    arr = np.asarray(img)
    if arr.ndim == 3:
        # Average channels to luminance; ignore alpha if present.
        arr = arr[:, :, :3].mean(axis=2)
    arr = arr.astype("float64")
    if arr.max() > 1.0:
        arr = arr / 255.0
    h, w = arr.shape[:2]
    if h == 0 or w == 0:
        raise SilhouetteUnavailable("empty image array")
    ys = (np.linspace(0, h, grid + 1)).astype(int)
    xs = (np.linspace(0, w, grid + 1)).astype(int)
    out: List[List[float]] = []
    for r in range(grid):
        y0, y1 = ys[r], max(ys[r] + 1, ys[r + 1])
        row: List[float] = []
        for c in range(grid):
            x0, x1 = xs[c], max(xs[c] + 1, xs[c + 1])
            row.append(float(arr[y0:y1, x0:x1].mean()))
        out.append(row)
    return out


def _decode_to_ndarray(data: bytes):
    """Decode encoded image bytes to a grayscale-capable ndarray (cv2 or Pillow)."""
    try:
        import cv2  # type: ignore
        import numpy as np

        buf = np.frombuffer(bytes(data), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is not None:
            return img
    except Exception:  # noqa: BLE001 - fall through to Pillow
        pass
    try:
        import io

        import numpy as np
        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(bytes(data))) as im:
            return np.asarray(im.convert("L"))
    except Exception as exc:  # noqa: BLE001
        raise SilhouetteUnavailable(
            "cannot decode frame bytes: install the [image] extra "
            "(opencv/numpy) or Pillow"
        ) from exc


def _to_grid(frame: FrameLike, grid: int) -> List[List[float]]:
    # Already a reduced grid (pure-python path).
    if isinstance(frame, list):
        if not frame or not isinstance(frame[0], (list, tuple)):
            raise SilhouetteUnavailable("grid must be a 2-D list of luminance rows")
        norm = [[float(v) for v in row] for row in frame]
        mx = max((max(row) for row in norm if row), default=1.0)
        if mx > 1.0:
            norm = [[v / 255.0 for v in row] for row in norm]
        return norm
    if isinstance(frame, (bytes, bytearray)):
        return _grid_from_ndarray(_decode_to_ndarray(frame), grid)
    # Assume a numpy ndarray (or array-like).
    return _grid_from_ndarray(frame, grid)


# --------------------------------------------------------------------------- #
# Silhouette scoring on the reduced grid
# --------------------------------------------------------------------------- #
def _border_background(g: List[List[float]]) -> float:
    n = len(g)
    m = len(g[0])
    border: List[float] = []
    border.extend(g[0])
    border.extend(g[n - 1])
    for r in range(1, n - 1):
        border.append(g[r][0])
        border.append(g[r][m - 1])
    border.sort()
    return border[len(border) // 2]  # median border luminance


def _foreground_mask(g: List[List[float]], bg: float, delta: float) -> List[List[bool]]:
    return [[abs(v - bg) >= delta for v in row] for row in g]


def _largest_component(mask: List[List[bool]]) -> Tuple[List[Tuple[int, int]], int]:
    """Return (cells of the largest 4-connected component, total component count)."""
    n = len(mask)
    m = len(mask[0]) if n else 0
    seen = [[False] * m for _ in range(n)]
    best: List[Tuple[int, int]] = []
    components = 0
    for sr in range(n):
        for sc in range(m):
            if not mask[sr][sc] or seen[sr][sc]:
                continue
            components += 1
            stack = [(sr, sc)]
            seen[sr][sc] = True
            cells: List[Tuple[int, int]] = []
            while stack:
                r, c = stack.pop()
                cells.append((r, c))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < n and 0 <= nc < m and mask[nr][nc] and not seen[nr][nc]:
                        seen[nr][nc] = True
                        stack.append((nr, nc))
            if len(cells) > len(best):
                best = cells
    return best, components


def analyze_grid(
    grid: List[List[float]], config: Optional[SilhouetteConfig] = None, *, source: str = "frame"
) -> SilhouetteReading:
    """Score a pre-reduced luminance grid into a :class:`SilhouetteReading`."""
    cfg = config or SilhouetteConfig()
    n = len(grid)
    m = len(grid[0]) if n else 0
    if n == 0 or m == 0:
        return SilhouetteReading(UNKNOWN, False, 0.0, (0.5, 0.5), 0, 0.0, source, "empty grid")

    bg = _border_background(grid)
    mask = _foreground_mask(grid, bg, cfg.foreground_delta)
    cells, components = _largest_component(mask)
    total = n * m
    coverage = len(cells) / total if total else 0.0

    if cells:
        cy = sum(r for r, _ in cells) / len(cells) / (n - 1 if n > 1 else 1)
        cx = sum(c for _, c in cells) / len(cells) / (m - 1 if m > 1 else 1)
        centroid = (round(cx, 4), round(cy, 4))
    else:
        centroid = (0.5, 0.5)

    if coverage >= cfg.present_coverage:
        state, present = PRESENT, True
    elif coverage >= cfg.partial_coverage:
        state, present = PARTIAL, False
    else:
        state, present = ABSENT, False

    # Confidence: how decisively coverage clears the present threshold, tempered
    # by how centred the mass is (a centred subject is a more confident person).
    span = max(cfg.present_coverage, 1e-6)
    cover_conf = max(0.0, min(1.0, coverage / span))
    centre_conf = max(0.0, 1.0 - (abs(centroid[0] - 0.5) + abs(centroid[1] - 0.5)))
    confidence = round(0.7 * cover_conf + 0.3 * centre_conf, 4)

    detail = f"bg={bg:.2f} components={components}"
    return SilhouetteReading(
        state=state,
        present=present,
        coverage=round(coverage, 4),
        centroid=centroid,
        regions=components,
        confidence=confidence,
        source=source,
        detail=detail,
    )


def detect_silhouette(
    frame: FrameLike, config: Optional[SilhouetteConfig] = None
) -> SilhouetteReading:
    """Detect a human silhouette in a single webcam frame.

    ``frame`` may be encoded bytes, a numpy ndarray, or a pre-reduced luminance
    grid. Raises :class:`SilhouetteUnavailable` only when encoded bytes cannot be
    decoded (no cv2/Pillow); array/grid inputs always succeed.
    """
    cfg = config or SilhouetteConfig()
    grid = _to_grid(frame, cfg.grid)
    return analyze_grid(grid, cfg, source="frame")


# --------------------------------------------------------------------------- #
# Bridge: derive a silhouette reading from face observations (no raw frame)
# --------------------------------------------------------------------------- #
def silhouette_from_faces(
    faces: Sequence[object],
    *,
    frame_size: Optional[Tuple[int, int]] = None,
    config: Optional[SilhouetteConfig] = None,
) -> SilhouetteReading:
    """Approximate a silhouette reading from detected faces.

    The hybrid/group path sends face geometry (bbox + landmarks), not frames. A
    present face implies a present silhouette; coverage is estimated from the
    face bounding boxes (a face is a fraction of the whole body/silhouette, so
    the box area is scaled up). ``faces`` items may be ``DetectedFace`` (bbox +
    frame_size) or any object exposing ``bbox``/``frame_size`` attributes.
    """
    cfg = config or SilhouetteConfig()
    boxes: List[Tuple[int, int, int, int]] = []
    fw = fh = 0
    for f in faces:
        bbox = getattr(f, "bbox", None)
        if not bbox or len(bbox) < 4:
            continue
        fsz = getattr(f, "frame_size", None) or frame_size
        if fsz and len(fsz) >= 2 and fsz[0] and fsz[1]:
            fw, fh = int(fsz[0]), int(fsz[1])
        boxes.append(tuple(int(v) for v in bbox[:4]))

    if not boxes or not (fw and fh):
        return SilhouetteReading(
            ABSENT, False, 0.0, (0.5, 0.5), 0, 0.0, source="faces",
            detail="no faces" if not boxes else "unknown frame size",
        )

    total = float(fw * fh)
    # A visible face typically spans ~10-18% of frame height; the silhouette
    # (head+torso) is several times the face box. Scale the face area up by ~5x
    # as a coarse body-coverage proxy, clamped to 1.0.
    biggest = max(boxes, key=lambda b: b[2] * b[3])
    face_cov = (biggest[2] * biggest[3]) / total
    coverage = min(1.0, face_cov * 5.0)
    cx = (biggest[0] + biggest[2] / 2.0) / fw
    cy = (biggest[1] + biggest[3] / 2.0) / fh

    if coverage >= cfg.present_coverage:
        state, present = PRESENT, True
    elif coverage >= cfg.partial_coverage:
        state, present = PARTIAL, False
    else:
        state, present = ABSENT, False

    return SilhouetteReading(
        state=state,
        present=present,
        coverage=round(coverage, 4),
        centroid=(round(cx, 4), round(cy, 4)),
        regions=len(boxes),
        confidence=round(min(1.0, face_cov * 5.0 / max(cfg.present_coverage, 1e-6)), 4),
        source="faces",
        detail=f"faces={len(boxes)}",
    )
