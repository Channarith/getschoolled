"""Mixamo FBX bundles -> Salareen Mascot.glb, inside Blender.

This is a Blender Python script. It must be run through Blender, NOT the
system python3, because it uses the bpy module which is Blender's embedded
interpreter.

Headless (no GUI) one-liner:

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python scripts/mascot_blender_postprocess.py -- \
        --mesh ~/Downloads/Mascot_tpose.fbx \
        --idle ~/Downloads/Idle.fbx \
        --walk ~/Downloads/Walking.fbx \
        --run  ~/Downloads/Running.fbx \
        --out  apps/web/public/mascot3d/Mascot.glb

What it does:

    1. Opens a fresh empty scene.
    2. Imports the T-pose mesh FBX (--mesh) - this becomes the exported body.
    3. Imports each animation FBX (--idle / --walk / --run) and copies its
       action onto the mesh's armature. Each action is renamed to the
       contract names "Survey" / "Walk" / "Run" so the renderer finds them.
    4. Pushes all three actions down to the NLA stack (required for glTF to
       include multiple clips in one export - without this, only the active
       action ships).
    5. Applies Decimate at 0.5 ratio if --decimate is passed (optional poly
       reduction before export).
    6. Exports as GLB with skinning + animations + draco mesh compression
       (if available in this Blender).

Why Mixamo:

    Mixamo (free Adobe service) will auto-rig any humanoid or near-humanoid
    mesh for you and gives free "Idle", "Walking", "Running" animations
    retargeted to the same skeleton. That means a working mascot in an
    afternoon instead of a week of hand-weight-painting.

Mesh-only alternative (if you only have the raw mesh, no rig):

    1. Upload the mesh at mixamo.com, click "Auto-Rigger", drop the joint
       markers (chin, wrists, elbows, knees, groin), download as FBX.
    2. On the same page under "Animations", pick Idle / Walking / Running,
       set "In Place" ON, download each as FBX ("With Skin" ON for the first
       one, OFF for the rest to keep files small).
    3. Run this script with those four FBX files.

After this script finishes, always run:

    python3 scripts/validate_mascot_glb.py apps/web/public/mascot3d/Mascot.glb

That script enforces the drop-in contract (clip names, skinning, size).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    # Blender passes its own args before "--"; keep only the ones after it.
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser(description="Build Mascot.glb from Mixamo FBX files inside Blender.")
    p.add_argument("--mesh", required=True, help="T-pose rigged mesh FBX (the body you export).")
    p.add_argument("--idle", required=True, help="FBX whose action becomes 'Survey'.")
    p.add_argument("--walk", required=True, help="FBX whose action becomes 'Walk'.")
    p.add_argument("--run", required=True, help="FBX whose action becomes 'Run'.")
    p.add_argument("--out", required=True, help="Output .glb path.")
    p.add_argument("--decimate", type=float, default=0.0,
                   help="Decimate ratio 0-1 (0 = off). 0.5 halves the triangle count.")
    return p.parse_args(argv)


def _ensure_blender() -> "object":
    """Fail fast with a readable message if run outside Blender."""
    try:
        import bpy  # type: ignore[import-not-found]
    except ImportError:
        print(
            "ERROR: this script must be run inside Blender, not with system python3.\n"
            "Use:\n"
            "  /Applications/Blender.app/Contents/MacOS/Blender --background \\\n"
            "      --python scripts/mascot_blender_postprocess.py -- --help\n",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return bpy


def _reset_scene(bpy) -> None:
    """Wipe the default scene so we start from empty."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _import_fbx(bpy, path: str) -> None:
    if not Path(path).exists():
        raise SystemExit(f"ERROR: file not found: {path}")
    bpy.ops.import_scene.fbx(filepath=path)


def _find_armature(bpy):
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            return obj
    raise SystemExit("ERROR: no armature found in the imported mesh FBX. Was it rigged?")


def _copy_action_into_scene(bpy, source_fbx: str, new_name: str) -> None:
    """Import an animation FBX, grab its (only) action, rename it, and
    assign/push it onto our mesh armature so the glTF exporter picks it up.
    """
    # Snapshot current action names so we can tell which one is new.
    before = {a.name for a in bpy.data.actions}
    _import_fbx(bpy, source_fbx)
    new_actions = [a for a in bpy.data.actions if a.name not in before]
    if not new_actions:
        print(f"WARN: {source_fbx} did not contain an action; skipping", file=sys.stderr)
        return
    action = new_actions[0]
    action.name = new_name

    # Remove the extra armature + mesh that the animation FBX dragged in -
    # we only wanted its action. Keep the first armature (our mesh's rig).
    rig = _find_armature(bpy)
    for obj in list(bpy.data.objects):
        if obj.type == "ARMATURE" and obj is not rig:
            bpy.data.objects.remove(obj, do_unlink=True)
        elif obj.type == "MESH":
            # Keep only meshes parented to our rig.
            if obj.parent is not rig:
                bpy.data.objects.remove(obj, do_unlink=True)

    # Assign the action to our rig and push it onto the NLA stack so glTF
    # exports it as a named clip.
    rig.animation_data_create()
    rig.animation_data.action = action
    track = rig.animation_data.nla_tracks.new()
    track.name = new_name
    track.strips.new(name=new_name, start=1, action=action)
    rig.animation_data.action = None  # clear so NLA strip is used as source


def _decimate_mesh(bpy, ratio: float) -> None:
    if ratio <= 0 or ratio >= 1:
        return
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        mod = obj.modifiers.new(name="MascotDecimate", type="DECIMATE")
        mod.ratio = ratio
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)


def _export_glb(bpy, out_path: str) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        export_animations=True,
        export_nla_strips=True,       # include every NLA track as a named clip
        export_skins=True,
        export_morph=False,
        export_apply=True,            # apply modifiers like our decimate
        export_draco_mesh_compression_enable=False,  # some Blender builds lack this
    )


def main() -> int:
    args = _parse_args()
    bpy = _ensure_blender()

    _reset_scene(bpy)
    _import_fbx(bpy, args.mesh)
    _find_armature(bpy)  # sanity check: mesh must be rigged

    for fbx_path, clip_name in [
        (args.idle, "Survey"),
        (args.walk, "Walk"),
        (args.run, "Run"),
    ]:
        _copy_action_into_scene(bpy, fbx_path, clip_name)

    _decimate_mesh(bpy, args.decimate)
    _export_glb(bpy, args.out)

    size_mb = os.path.getsize(args.out) / 1_048_576
    print(f"\nWrote {args.out} ({size_mb:.2f} MB).")
    print("Now run:  python3 scripts/validate_mascot_glb.py", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
