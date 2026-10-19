"""Prep a Meshy.ai image-to-3D GLB for the Salareen mascot pipeline.

Meshy's "Image to 3D" output is high-quality raw material (great surface
detail, honest geometry, PBR textures) but ships with a million+ triangles
and 8K base-color textures baked in. That gives file sizes in the 90-200 MB
range - unusable on the web.

This script (runs inside Blender headless, bpy-only, no GUI) takes a Meshy
GLB and produces a slim web-ready GLB:

  1. Imports the Meshy GLB.
  2. Joins all mesh objects into one (Meshy sometimes splits by material).
  3. Decimates to the target triangle count (default 15,000 - matches the
     validator's 5-20k budget) using the Collapse method, which preserves
     silhouette and UV seams better than Un-Subdivide.
  4. Resizes every texture image to the target square size (default 1024).
     This is where most of the file-size win comes from - the base color
     drops from ~96 MB uncompressed to ~800 KB JPEG.
  5. Re-exports as GLB with the exporter's default JPEG compression on
     diffuse maps and PNG only where alpha is needed. Draco mesh
     compression is enabled when the Blender build has it (newer official
     builds do; some custom builds strip it) and the exporter silently
     falls back if not.

Usage (headless, from the repo root):

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python scripts/mascot_meshy_prep.py -- \
        --input  ~/Downloads/Meshy_AI_Golden_Little_Prince_1019054819_texture.glb \
        --output /tmp/mascot_slim.glb \
        --target-tris 15000 \
        --texture-size 1024

Then validate the output:

    python3 scripts/validate_mascot_glb.py /tmp/mascot_slim.glb

If the result still fails the <= 5 MB hard ceiling, lower --target-tris
(e.g. 8000) and/or --texture-size (e.g. 512) and re-run.

This script does NOT rig the character. Meshy image-to-3D produces a
static mesh. For walking/running clips, upload the slim GLB (or an FBX
export) to Mixamo for auto-rig, download Idle/Walking/Running FBXs, and
run scripts/mascot_blender_postprocess.py to merge the three clips in
and emit the final Mascot.glb with Survey/Walk/Run.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _parse_args() -> "object":
    import argparse
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    p = argparse.ArgumentParser(description="Slim a Meshy.ai GLB for web.")
    p.add_argument("--input", required=True, help="Meshy GLB path.")
    p.add_argument("--output", required=True, help="Output GLB path.")
    p.add_argument("--target-tris", type=int, default=15000,
                   help="Target triangle count after decimation (default 15000).")
    p.add_argument("--texture-size", type=int, default=1024,
                   help="Max square dimension for every image (default 1024).")
    p.add_argument("--fbx-output", default=None,
                   help="Optional FBX export path - produces a Mixamo-ready "
                        "upload file alongside the slim GLB.")
    return p.parse_args(argv)


def _ensure_blender():
    try:
        import bpy  # type: ignore[import-not-found]
    except ImportError:
        print(
            "ERROR: this script must be run inside Blender, not with system python3.\n"
            "  /Applications/Blender.app/Contents/MacOS/Blender --background \\\n"
            "      --python scripts/mascot_meshy_prep.py -- --help\n",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return bpy


def _reset_scene(bpy) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _import_glb(bpy, path: str) -> None:
    if not Path(path).exists():
        raise SystemExit(f"ERROR: input not found: {path}")
    bpy.ops.import_scene.gltf(filepath=path)


def _collect_meshes(bpy) -> list:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def _join_meshes(bpy) -> "object":
    """Join all mesh objects into one so the decimate ratio produces a
    predictable triangle count. Returns the surviving mesh object."""
    meshes = _collect_meshes(bpy)
    if not meshes:
        raise SystemExit("ERROR: no meshes imported from GLB")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    primary = meshes[0]
    bpy.context.view_layer.objects.active = primary
    if len(meshes) > 1:
        bpy.ops.object.join()
    return primary


def _triangle_count(mesh_obj) -> int:
    """Count triangles after triangulation; polygons in Meshy output are
    typically already triangles, but n-gons would under-count without this."""
    tri_count = 0
    for poly in mesh_obj.data.polygons:
        # A polygon with N vertices triangulates into N-2 triangles.
        tri_count += max(1, len(poly.vertices) - 2)
    return tri_count


def _decimate(bpy, mesh_obj, target_tris: int) -> int:
    """Apply a Decimate modifier to hit ~target_tris. Returns the actual
    triangle count after apply."""
    current = _triangle_count(mesh_obj)
    if current <= target_tris:
        print(f"  decimate: skipped (current {current} <= target {target_tris})")
        return current
    ratio = target_tris / current
    print(f"  decimate: {current:,} tris -> target {target_tris:,} (ratio {ratio:.4f})")
    bpy.context.view_layer.objects.active = mesh_obj
    mod = mesh_obj.modifiers.new(name="MeshyPrepDecimate", type="DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    after = _triangle_count(mesh_obj)
    print(f"  decimate: done, now {after:,} tris")
    return after


def _resize_textures(bpy, max_dim: int) -> None:
    for img in list(bpy.data.images):
        if img.size[0] == 0 or img.size[1] == 0:
            continue  # placeholder / generated
        w, h = img.size[0], img.size[1]
        if w <= max_dim and h <= max_dim:
            print(f"  texture {img.name}: kept at {w}x{h}")
            continue
        aspect = w / h
        if aspect >= 1:
            new_w = max_dim
            new_h = max(1, round(max_dim / aspect))
        else:
            new_h = max_dim
            new_w = max(1, round(max_dim * aspect))
        print(f"  texture {img.name}: {w}x{h} -> {new_w}x{new_h}")
        img.scale(new_w, new_h)
        # Pack the resized image into the .blend so the glTF exporter
        # writes the shrunken bytes, not a reference to the original file.
        try:
            img.pack()
        except RuntimeError:
            # Already packed / generated - safe to ignore.
            pass


def _export_glb(bpy, out_path: str) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        filepath=out_path,
        export_format="GLB",
        export_animations=False,       # no rig / anims from Meshy image-to-3D
        export_skins=False,
        export_morph=False,
        export_apply=True,
        export_image_format="AUTO",    # JPEG when no alpha, PNG when alpha
    )
    # Draco is optional in some builds - try with, fall back without.
    try:
        bpy.ops.export_scene.gltf(**kwargs, export_draco_mesh_compression_enable=True)
    except (TypeError, RuntimeError) as exc:
        print(f"  draco unavailable ({exc}); retrying without compression")
        bpy.ops.export_scene.gltf(**kwargs)


def main() -> int:
    args = _parse_args()
    bpy = _ensure_blender()
    print(f"Meshy prep: {args.input}")
    print(f"  -> {args.output}")
    print(f"  target: {args.target_tris:,} tris, max texture {args.texture_size}px")

    _reset_scene(bpy)
    _import_glb(bpy, args.input)
    mesh = _join_meshes(bpy)
    print(f"  joined to one mesh: {mesh.name}")

    _decimate(bpy, mesh, args.target_tris)
    _resize_textures(bpy, args.texture_size)
    _export_glb(bpy, args.output)

    size_mb = os.path.getsize(args.output) / 1_048_576
    print(f"\nWrote {args.output} ({size_mb:.2f} MB).")
    print("Next: python3 scripts/validate_mascot_glb.py", args.output)

    if args.fbx_output:
        Path(args.fbx_output).parent.mkdir(parents=True, exist_ok=True)
        print(f"\nExporting FBX for Mixamo upload: {args.fbx_output}")
        bpy.ops.export_scene.fbx(
            filepath=args.fbx_output,
            use_selection=False,
            bake_space_transform=True,
            object_types={"MESH"},
            embed_textures=True,
            path_mode="COPY",
            axis_forward="-Z",
            axis_up="Y",
        )
        fbx_mb = os.path.getsize(args.fbx_output) / 1_048_576
        print(f"Wrote {args.fbx_output} ({fbx_mb:.2f} MB).")
        print("Upload this file to mixamo.com (Upload Character), auto-rig,")
        print("then download Idle/Walking/Running FBX and feed all four files")
        print("into scripts/mascot_blender_postprocess.py.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
