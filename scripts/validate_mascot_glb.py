#!/usr/bin/env python3
"""Validate a mascot .glb against the Salareen MascotActor3D / MascotOverlay3D
drop-in contract. Pure stdlib so it runs anywhere (no numpy, no pygltflib).

The contract (see apps/web/app/components/MascotActor3D.tsx header):

    1. glTF 2.0 binary (.glb) with the animation tracks baked in.
    2. Exactly these three animation clip names:
         - "Survey"  (idle)
         - "Walk"
         - "Run"
       (The clip names are matched case-insensitively here and the renderer
       falls back to the first available clip if a name is missing - but we
       warn so you catch it before shipping.)
    3. Must be skinned (has a skeleton + skin weights), otherwise the mascot
       is a frozen T-pose on screen.
    4. Soft budget: <= 2 MB (fast first paint), hard ceiling 5 MB.

Usage:

    python3 scripts/validate_mascot_glb.py apps/web/public/mascot3d/Mascot.glb
    python3 scripts/validate_mascot_glb.py --json path/to/file.glb

Exit code is 0 on PASS (clip names present, skinned, under hard ceiling)
and 1 on FAIL. Soft warnings (naming hints, large file) do not fail.

This is the gate the mascot-pipeline doc (docs/mascot-pipeline.txt) tells
authors to run after Blender export, before copying into public/mascot3d/.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

GLB_MAGIC = b"glTF"
JSON_CHUNK = b"JSON"
BIN_CHUNK = b"BIN\x00"

REQUIRED_CLIPS = ("Survey", "Walk", "Run")
SOFT_SIZE_WARN_BYTES = 2 * 1024 * 1024     # 2 MB -> prints a warning
HARD_SIZE_FAIL_BYTES = 5 * 1024 * 1024     # 5 MB -> validation fails


@dataclass
class Finding:
    """One check result. kind is 'ok' / 'warn' / 'fail'."""
    kind: str
    message: str


@dataclass
class Report:
    path: str
    size_bytes: int
    gltf_version: int = 0
    animation_names: list[str] = field(default_factory=list)
    skin_count: int = 0
    node_count: int = 0
    mesh_count: int = 0
    triangle_count: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(f.kind == "fail" for f in self.findings)

    def add(self, kind: str, message: str) -> None:
        self.findings.append(Finding(kind=kind, message=message))

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "gltf_version": self.gltf_version,
            "animations": self.animation_names,
            "skin_count": self.skin_count,
            "node_count": self.node_count,
            "mesh_count": self.mesh_count,
            "triangle_count": self.triangle_count,
            "findings": [{"kind": f.kind, "message": f.message} for f in self.findings],
            "passed": not self.failed,
        }


def _read_glb_json(blob: bytes) -> dict:
    """Parse the JSON chunk out of a .glb binary blob.

    Format (glTF 2.0 binary):
        12-byte header: 'glTF' | uint32 version | uint32 total length
        Then one or more chunks:
            uint32 chunk_length | 4-byte chunk_type | <chunk_length> bytes
        The first chunk must be type 'JSON\\x00' (we accept 'JSON' + optional
        trailing null here since the spec pads to 4 bytes with \\x00).
    """
    if len(blob) < 12:
        raise ValueError("file is too short to be a .glb")
    magic, version, _total = struct.unpack("<4sII", blob[:12])
    if magic != GLB_MAGIC:
        raise ValueError(f"not a .glb: magic was {magic!r}, expected {GLB_MAGIC!r}")
    if version != 2:
        raise ValueError(f"unsupported glTF binary version {version} (expected 2)")

    # First chunk is JSON per the spec.
    chunk_length, chunk_type = struct.unpack("<I4s", blob[12:20])
    if chunk_type.rstrip(b"\x00") != JSON_CHUNK.rstrip(b"\x00"):
        raise ValueError(
            f"first chunk is {chunk_type!r}, expected {JSON_CHUNK!r} (JSON header)"
        )
    json_bytes = blob[20 : 20 + chunk_length]
    try:
        return json.loads(json_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"JSON chunk is not valid UTF-8 JSON: {exc}") from exc


def _accessor_triangle_count(gltf: dict) -> int:
    """Rough triangle count across all mesh primitives.

    For indexed geometry we use the index accessor's count / 3; for
    non-indexed geometry we use the POSITION accessor's count / 3. This is
    an over-estimate when primitives share accessors but is good enough as
    a budget sanity check (budget is 5k-20k triangles, we only need the
    order of magnitude).
    """
    accessors = gltf.get("accessors") or []
    meshes = gltf.get("meshes") or []
    total = 0
    for mesh in meshes:
        for prim in mesh.get("primitives", []) or []:
            if "indices" in prim and prim["indices"] < len(accessors):
                total += (accessors[prim["indices"]].get("count", 0)) // 3
                continue
            attrs = prim.get("attributes") or {}
            pos = attrs.get("POSITION")
            if pos is not None and pos < len(accessors):
                total += (accessors[pos].get("count", 0)) // 3
    return total


def validate_file(path: str) -> Report:
    """Check one .glb file and return a structured report."""
    p = Path(path)
    data = p.read_bytes()
    report = Report(path=str(p), size_bytes=len(data))

    try:
        gltf = _read_glb_json(data)
    except ValueError as exc:
        report.add("fail", f"could not parse .glb: {exc}")
        return report

    report.gltf_version = int(gltf.get("asset", {}).get("version", "2").split(".")[0])

    # ---- animations: must have Survey / Walk / Run (case-insensitive) ----
    anims = gltf.get("animations") or []
    report.animation_names = [a.get("name", "") for a in anims]
    lower_names = {n.lower() for n in report.animation_names if n}
    missing = [c for c in REQUIRED_CLIPS if c.lower() not in lower_names]
    if not anims:
        report.add("fail", "no animations in the file - renderer will show a static T-pose")
    elif missing:
        report.add(
            "fail",
            "missing required animation clips: "
            + ", ".join(missing)
            + f". Found: {report.animation_names}. Rename the tracks in Blender's "
            + "Dope Sheet > Action Editor before export, or update CLIP_MAP in "
            + "MascotActor3D.tsx / MascotOverlay3D.tsx to match your names.",
        )
    else:
        # Warn on casing drift so you don't ship 'survey' and silently depend
        # on the fuzzy fallback in the renderer.
        exact = {c for c in REQUIRED_CLIPS if c in report.animation_names}
        if len(exact) < len(REQUIRED_CLIPS):
            report.add(
                "warn",
                "clip names present but case does not match exactly. "
                + f"Found {report.animation_names}, want {list(REQUIRED_CLIPS)}. "
                + "The renderer matches case-insensitively, but exact names "
                + "make the code easier to read.",
            )

    # ---- skinning: must have at least one skin ----
    skins = gltf.get("skins") or []
    report.skin_count = len(skins)
    if report.skin_count == 0:
        report.add(
            "fail",
            "no skins in the file - the character will not deform with the "
            "animation. Confirm you exported with skinning / armatures enabled "
            "(Blender: glTF export > Data > Armature > Export Deformation Bones Only).",
        )

    # ---- scene / mesh / triangle counts ----
    report.node_count = len(gltf.get("nodes") or [])
    report.mesh_count = len(gltf.get("meshes") or [])
    report.triangle_count = _accessor_triangle_count(gltf)
    if report.triangle_count > 50_000:
        report.add(
            "warn",
            f"triangle count ~{report.triangle_count:,} is high. "
            "Target 5k-20k for a mascot that renders on mobile too.",
        )

    # ---- file size budget ----
    if report.size_bytes > HARD_SIZE_FAIL_BYTES:
        report.add(
            "fail",
            f"file is {report.size_bytes/1_048_576:.2f} MB (> 5 MB hard ceiling). "
            "Compress textures to KTX2/Basis or reduce poly count before shipping.",
        )
    elif report.size_bytes > SOFT_SIZE_WARN_BYTES:
        report.add(
            "warn",
            f"file is {report.size_bytes/1_048_576:.2f} MB (soft budget is 2 MB). "
            "Fine for desktop, slow for mobile first-paint.",
        )

    if not report.failed:
        report.add("ok", "ready to drop in at apps/web/public/mascot3d/Mascot.glb")

    return report


def _print_human(report: Report) -> None:
    print(f"{report.path}")
    print(f"  size:        {report.size_bytes/1_048_576:.3f} MB ({report.size_bytes:,} bytes)")
    print(f"  glTF ver:    {report.gltf_version}")
    print(f"  animations:  {report.animation_names}")
    print(f"  skins:       {report.skin_count}")
    print(f"  meshes:      {report.mesh_count}")
    print(f"  nodes:       {report.node_count}")
    print(f"  triangles:   ~{report.triangle_count:,}")
    print("  findings:")
    for f in report.findings:
        tag = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}.get(f.kind, f.kind.upper())
        print(f"    [{tag}] {f.message}")
    print(f"  result:      {'FAIL' if report.failed else 'PASS'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb", help="path to a .glb file to validate")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON instead of a human-readable summary",
    )
    args = parser.parse_args(argv)

    try:
        report = validate_file(args.glb)
    except FileNotFoundError:
        print(f"error: file not found: {args.glb}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not read file: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_human(report)
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
