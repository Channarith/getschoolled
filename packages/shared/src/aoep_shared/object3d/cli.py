"""Shared flags for the object3d scripts."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from .gallery import ObjectGallery
from .sensors import SensorBundle, load_sensor_bundle

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_GALLERY = REPO_ROOT / "output" / "object3d" / "gallery.json"
DEFAULT_SAMPLES = REPO_ROOT / "output" / "object3d" / "samples"


def add_gallery_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--gallery",
        type=Path,
        default=DEFAULT_GALLERY,
        help=f"identification catalog (default {DEFAULT_GALLERY})",
    )


def add_camera_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--camera",
        choices=("realsense", "oak", "both"),
        default="realsense",
        help="which 3D camera to open",
    )


def add_detector_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--detector",
        choices=("auto", "coco", "depth"),
        default="auto",
        help="auto uses COCO names plus depth blobs",
    )


def add_sensor_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sensors", type=Path, help="JSON from a touch, smell, or heat collector")
    parser.add_argument("--thermal", type=Path, help="Celsius map (.npy) from a thermal camera")
    parser.add_argument("--celsius", type=float, default=None, help="probe temperature")
    parser.add_argument("--smell", default="", help="smell label, such as coffee or smoke")
    parser.add_argument("--texture", default="", help="touch texture, such as smooth or rough")
    parser.add_argument("--force", type=float, default=None, help="contact force in newtons")


def bundle_from_args(args: argparse.Namespace) -> SensorBundle:
    return load_sensor_bundle(
        getattr(args, "sensors", None),
        getattr(args, "thermal", None),
        celsius=getattr(args, "celsius", None),
        smell=getattr(args, "smell", "") or "",
        texture=getattr(args, "texture", "") or "",
        force_n=getattr(args, "force", None),
    )


def load_gallery(path: Path) -> ObjectGallery:
    return ObjectGallery(path if path.is_file() else None)


def llm_from_env():
    """Return a one-string completer when a voice/LLM endpoint is configured.

    Measured answers (distance, animal, food, a catalog maker or year) do not
    call this. It is only used to fill a fact the camera does not have.
    """
    key = os.environ.get("XAI_API_KEY", "").strip()
    if key:
        from ..xai_grok_voice import GrokVoiceAgent

        agent = GrokVoiceAgent(api_key=key)

        def complete(prompt: str) -> str:
            return agent.respond_to_query(prompt).text

        return complete
    return None


def speak(text: str) -> None:
    """Say ``text`` when a local speech command exists. Always safe to call."""
    custom = os.environ.get("OBJECT3D_SPEAK_CMD", "").strip()
    if custom:
        subprocess.run(custom, input=text + "\n", text=True, shell=True, check=False)
        return
    for cmd in ("spd-say", "espeak-ng", "espeak"):
        if shutil.which(cmd):
            subprocess.run([cmd, text], check=False)
            return
