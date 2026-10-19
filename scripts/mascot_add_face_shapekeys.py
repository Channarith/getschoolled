#!/usr/bin/env python3
"""
mascot_add_face_shapekeys.py - add procedural facial shape keys to a
rigged Mascot.glb so expressions deform the sculpted stone face instead
of just adding color tints and particle overlays.

The Meshy image-to-3D pipeline produces a sculpted mesh with no blend
shapes and no facial sub-skeleton (the Mixamo rig stops at the Head
bone - no jaw, no eye, no brow bones). This script fills that gap:

  1. Imports the GLB (keeps all existing animations + skinning intact).
  2. Finds the Head bone's vertex group (Mixamo: mixamorig:Head).
     Everything with head weight > 0.5 is a "head vert".
  3. Within head verts, splits by the *front* half (-Z in Mixamo
     convention is forward) so the top-of-head crown doesn't get
     brow-furrow deformation.
  4. Further splits by vertical zone within the head bbox:
       - upper (y 0.60-1.00 of head height) = brow / forehead
       - mid   (y 0.30-0.60)                = eyes / cheeks / nose
       - lower (y 0.00-0.30)                = mouth / jaw / chin
  5. Creates one Blender Shape Key per expression (angry, sad,
     excited, etc.) with a procedurally-computed vertex offset per
     zone (and per left/right side where asymmetric expressions
     benefit from it, e.g. mischievous).
  6. Re-exports GLB with export_morph=True so the browser can drive
     each expression via `mesh.morphTargetInfluences`.

The deformations are intentionally subtle (3-15 mm on a ~1.5 m tall
character). The face is smooth sculpted stone - we can't open mouths
or separate eyelids that aren't there - but we CAN push brow verts
down for angry, pull mouth verts up for a smile, puff cheeks for a
grin, etc. The result is real mesh motion, not a face sticker.

Usage (fresh build):

    /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python scripts/mascot_add_face_shapekeys.py -- \
      --input  apps/web/public/mascot3d/Mascot.glb \
      --output apps/web/public/mascot3d/Mascot.glb

The expression names created by this script MUST match the keys in
apps/web/app/components/mascot3d/expressions.ts so the renderer can
map `expression` -> morph target by name.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path


# Shape keys are named exactly as the renderer expressions. The script
# adds every key below as a non-"Basis" shape key. The renderer then
# drives mesh.morphTargetInfluences[expressionIndex] = 1 for the
# currently-selected mood, and all other influences to 0.
#
# Each entry is a dict of zone -> (dx, dy, dz) in METERS, measured in
# local mesh coords (same units as the imported mesh). Mixamo exports
# are typically in centimeters so these look larger than you'd expect
# in meters - roughly 0.5-1.5 cm of displacement per zone.
#
# Zone names:
#   upper        = brow / forehead (front, top third of head)
#   mid          = eyes / cheeks / nose (front, middle third)
#   lower        = mouth / jaw / chin (front, bottom third)
#   upper_left   = upper AND x > 0 (character's left from viewer POV)
#   upper_right  = upper AND x < 0
#   (same for mid_left, mid_right, lower_left, lower_right)
#
# A zone key beats the generic key if both are specified for a vert.
#
# Axes (Mixamo / glTF import convention):
#   +Y = up (towards the top of the head)
#   -Z = forward (character faces -Z)
#   +X = character's RIGHT (viewer's left)
EXPRESSION_SHAPE_KEYS: dict[str, dict[str, tuple[float, float, float]]] = {
    # Resting pose - no deformation. Still create the key so the
    # renderer can "lerp back to cute" by setting it to 1.
    "cute": {},
    # Brow pulled down and in, mouth corners tightened. Subtle but
    # unmistakable scowl on a stone face.
    "angry": {
        "upper": (0.0, -1.5, -0.8),
        "lower": (0.0, -0.5, 0.0),
    },
    # Brow pulled down with slight inward tilt, mouth corners down,
    # whole face relaxes forward.
    "sad": {
        "upper": (0.0, -0.9, 0.0),
        "lower": (0.0, -1.3, 0.3),
    },
    # Worried brow (up and in) + jaw drops slightly (sob).
    "crying": {
        "upper": (0.0, 0.9, -0.4),
        "lower": (0.0, -1.7, 0.0),
    },
    # Brow up, mouth corners up and back (fake smile on a smooth
    # stone face by puffing cheeks and lifting mouth zone).
    "excited": {
        "upper": (0.0, 1.1, 0.0),
        "mid": (0.0, 0.5, -0.6),
        "lower": (0.0, 1.6, -0.9),
    },
    # Mild raised brows, head reads as "interested" via tilt
    # (handled by renderer posture).
    "curious": {
        "upper": (0.0, 1.4, -0.5),
        "mid": (0.0, 0.4, -0.3),
    },
    # Asymmetric: only RIGHT brow raised (viewer's left), only
    # LEFT mouth corner lifted. Produces the classic smirk.
    "mischievous": {
        "upper_right": (0.0, 1.2, -0.4),
        "lower_left": (0.0, 0.8, -0.5),
    },
    # Brow faintly lowered, mouth narrowed to a focused line.
    "serious": {
        "upper": (0.0, -0.6, 0.0),
        "lower": (0.0, -0.3, 0.3),
    },
}


def _parse_args() -> argparse.Namespace:
    try:
        split = sys.argv.index("--")
        args = sys.argv[split + 1 :]
    except ValueError:
        args = sys.argv[1:]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument(
        "--head-weight-min",
        type=float,
        default=0.5,
        help="Vertex is a 'head vert' when its weight on the Head bone "
        "exceeds this. Default 0.5. Lower = include more neck + ears.",
    )
    return p.parse_args(args)


def _clean_scene(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.armatures):
        bpy.data.armatures.remove(block)
    for block in list(bpy.data.actions):
        bpy.data.actions.remove(block)


def _import_glb(bpy, path: str) -> None:
    bpy.ops.import_scene.gltf(filepath=path)


def _find_mesh_and_armature(bpy):
    mesh_obj = None
    armature_obj = None
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and (mesh_obj is None or len(obj.data.vertices) > len(mesh_obj.data.vertices)):
            mesh_obj = obj
        elif obj.type == "ARMATURE":
            armature_obj = obj
    if not mesh_obj:
        raise SystemExit("ERROR: no mesh found in imported GLB")
    if not armature_obj:
        raise SystemExit("ERROR: no armature found in imported GLB (not a rigged character)")
    return mesh_obj, armature_obj


def _find_head_bone_name(armature_obj) -> str:
    """Prefer mixamorig:Head; fall back to any bone whose stem is just
    'Head' or contains 'head' without 'top'/'end' tags."""
    bones = {b.name.lower(): b.name for b in armature_obj.data.bones}
    for canonical in ("mixamorig:head", "head"):
        if canonical in bones:
            return bones[canonical]
    for lower, actual in bones.items():
        if "head" in lower and "top" not in lower and "end" not in lower and "front" not in lower:
            return actual
    raise SystemExit(
        f"ERROR: no Head bone found. Available: {sorted(bones.values())}"
    )


def _collect_head_verts(mesh_obj, head_vg_name: str, min_weight: float):
    """Return a dict {vertex_index: head_weight}. Only verts whose
    weight on the Head vertex group exceeds min_weight are included."""
    if head_vg_name not in mesh_obj.vertex_groups:
        raise SystemExit(
            f"ERROR: mesh has no vertex group '{head_vg_name}'. "
            f"Groups: {[vg.name for vg in mesh_obj.vertex_groups]}"
        )
    vg_index = mesh_obj.vertex_groups[head_vg_name].index
    out: dict[int, float] = {}
    for v in mesh_obj.data.vertices:
        for g in v.groups:
            if g.group == vg_index and g.weight >= min_weight:
                out[v.index] = g.weight
                break
    return out


def _facing_direction(head_verts: dict[int, float], vertices) -> str:
    """Mixamo-rigged glTF characters face -Z by convention, but Meshy
    sometimes re-orients. Infer facing by checking which Z half of the
    head has more surface verts (the face is where the mesh is denser
    - lots of carved detail on front, flat crown on top-back)."""
    coords = [vertices[i].co for i in head_verts]
    if not coords:
        return "neg_z"
    z_mean = sum(c.z for c in coords) / len(coords)
    front = sum(1 for c in coords if c.z < z_mean)
    back = sum(1 for c in coords if c.z >= z_mean)
    return "neg_z" if front >= back else "pos_z"


def _classify_vertex_zone(
    co, head_center, head_size, facing: str
) -> str | None:
    """Return 'upper_left', 'upper_right', 'mid_*', 'lower_*', or None
    if the vert is not on the front face."""
    # Front filter: character faces -Z in Mixamo convention. "Front" =
    # the Z half the face is on. Use a soft threshold: within 55% of the
    # front depth so we don't deform the back of the head.
    z_rel = (co.z - head_center.z) / max(0.001, head_size.z * 0.5)
    if facing == "neg_z":
        if z_rel > -0.1:  # verts need to be in the forward half (z < center)
            return None
    else:
        if z_rel < 0.1:
            return None

    # Vertical zone within the head bbox (0 = chin, 1 = crown).
    y_rel = (co.y - (head_center.y - head_size.y * 0.5)) / max(0.001, head_size.y)
    if y_rel < 0.30:
        zone = "lower"
    elif y_rel < 0.60:
        zone = "mid"
    elif y_rel < 1.00:
        zone = "upper"
    else:
        return None  # crown of head, no facial feature

    # Left/right side.
    x_rel = co.x - head_center.x
    # Center 20% of the face gets both left and right offsets - avoids
    # a seam down the nose.
    if x_rel > head_size.x * 0.03:
        side = "right"  # character's right = viewer's left
    elif x_rel < -head_size.x * 0.03:
        side = "left"  # character's left = viewer's right
    else:
        side = "center"

    return f"{zone}_{side}"


def _add_shape_keys(mesh_obj, head_verts, head_center, head_size, facing):
    """Create one shape key per EXPRESSION_SHAPE_KEYS entry with
    procedural per-vertex offsets."""
    me = mesh_obj.data
    # Ensure a Basis shape key exists.
    if not me.shape_keys:
        mesh_obj.shape_key_add(name="Basis", from_mix=False)
        basis = me.shape_keys.key_blocks["Basis"]
    else:
        basis = me.shape_keys.key_blocks[0]
    # Set the Basis to identity (just in case).
    basis.interpolation = "KEY_LINEAR"

    for expr_name, zones in EXPRESSION_SHAPE_KEYS.items():
        # Remove any pre-existing key with this name so re-runs are
        # idempotent.
        if expr_name in me.shape_keys.key_blocks:
            mesh_obj.shape_key_remove(me.shape_keys.key_blocks[expr_name])
        sk = mesh_obj.shape_key_add(name=expr_name, from_mix=False)
        sk.interpolation = "KEY_LINEAR"

        if not zones:
            print(f"  shape key '{expr_name}': resting (no displacement)")
            continue

        affected = 0
        for v_idx, head_weight in head_verts.items():
            co = me.vertices[v_idx].co
            zone_full = _classify_vertex_zone(co, head_center, head_size, facing)
            if zone_full is None:
                continue
            # Try zone+side first, then zone-only.
            zone_name, side = zone_full.rsplit("_", 1)
            offset = zones.get(zone_full)
            if offset is None and side != "center":
                offset = zones.get(zone_name)
            if offset is None:
                # Center verts fall back to the generic zone offset.
                offset = zones.get(zone_name)
            if offset is None:
                continue
            # Soft falloff: head_weight already biases towards the
            # center of the face. Multiply offset by weight so verts
            # on the neck boundary get only partial deformation.
            w = head_weight
            # Also radial falloff from the face center so the offset
            # is strongest near the center of the chosen zone and
            # fades at zone edges. This avoids hard discontinuities
            # between zones.
            dx = (co.x - head_center.x) / max(0.001, head_size.x * 0.5)
            dy_in_head = (co.y - head_center.y) / max(0.001, head_size.y * 0.5)
            radial = max(0.0, 1.0 - math.sqrt(dx * dx + dy_in_head * dy_in_head) * 0.5)
            w *= radial

            sk.data[v_idx].co = co + _vec3(offset) * w
            affected += 1
        print(f"  shape key '{expr_name}': {affected} verts displaced")


def _vec3(t):
    from mathutils import Vector  # type: ignore

    return Vector((t[0], t[1], t[2]))


def _compute_head_bbox(head_verts, vertices):
    from mathutils import Vector  # type: ignore

    coords = [vertices[i].co for i in head_verts]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    lo = Vector((min(xs), min(ys), min(zs)))
    hi = Vector((max(xs), max(ys), max(zs)))
    size = hi - lo
    center = (lo + hi) * 0.5
    return center, size


def _export_glb(bpy, out_path: str) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        filepath=out_path,
        export_format="GLB",
        export_animations=True,
        export_nla_strips=True,
        export_skins=True,
        export_morph=True,
        export_morph_normal=True,
        export_apply=False,
        export_image_format="AUTO",
    )
    try:
        bpy.ops.export_scene.gltf(**kwargs, export_draco_mesh_compression_enable=True)
    except (TypeError, RuntimeError) as exc:
        print(f"  draco unavailable ({exc}); retrying without compression")
        bpy.ops.export_scene.gltf(**kwargs)


def main() -> None:
    args = _parse_args()
    print(f"Adding face shape keys: {args.input} -> {args.output}")

    import bpy  # type: ignore

    _clean_scene(bpy)
    _import_glb(bpy, args.input)
    mesh_obj, armature_obj = _find_mesh_and_armature(bpy)
    print(f"  mesh: {mesh_obj.name} ({len(mesh_obj.data.vertices)} verts)")
    print(f"  armature: {armature_obj.name}")

    head_bone_name = _find_head_bone_name(armature_obj)
    print(f"  head bone: {head_bone_name}")

    head_verts = _collect_head_verts(mesh_obj, head_bone_name, args.head_weight_min)
    if not head_verts:
        raise SystemExit(
            f"ERROR: no verts have weight >= {args.head_weight_min} on {head_bone_name}"
        )
    print(f"  head verts (weight >= {args.head_weight_min}): {len(head_verts)}")

    head_center, head_size = _compute_head_bbox(head_verts, mesh_obj.data.vertices)
    print(f"  head bbox center: ({head_center.x:.3f}, {head_center.y:.3f}, {head_center.z:.3f})")
    print(f"  head bbox size:   ({head_size.x:.3f}, {head_size.y:.3f}, {head_size.z:.3f})")

    facing = _facing_direction(head_verts, mesh_obj.data.vertices)
    print(f"  face facing: {facing} (-Z = standard Mixamo)")

    bpy.context.view_layer.objects.active = mesh_obj
    mesh_obj.select_set(True)
    _add_shape_keys(mesh_obj, head_verts, head_center, head_size, facing)

    _export_glb(bpy, args.output)
    size_mb = Path(args.output).stat().st_size / 1_048_576
    print(f"Wrote {args.output} ({size_mb:.2f} MB)")
    print("Shape key names (match these in expressions.ts):")
    for name in EXPRESSION_SHAPE_KEYS:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
