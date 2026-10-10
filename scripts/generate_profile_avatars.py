#!/usr/bin/env python3
"""Generate polished local SVG profile avatars (Realistic + Cute).

Writes apps/web/public/avatars/{id}.svg and apps/mobile/assets/avatars/{id}.svg,
plus a TypeScript catalog mirror for web/mobile. Deterministic original vectors —
no third-party URLs, suitable for repo inclusion.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Load avatars.py directly so we do not pull in aoep_shared.__init__ (pydantic).
import importlib.util

_avatars_path = ROOT / "packages" / "shared" / "src" / "aoep_shared" / "avatars.py"
_spec = importlib.util.spec_from_file_location("aoep_avatars_gen", _avatars_path)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules["aoep_avatars_gen"] = _mod
_spec.loader.exec_module(_mod)
AVATAR_CATALOG = _mod.AVATAR_CATALOG
DEFAULT_AVATAR_ID = _mod.DEFAULT_AVATAR_ID
avatar_catalog_list = _mod.avatar_catalog_list

WEB_OUT = ROOT / "apps" / "web" / "public" / "avatars"
MOBILE_OUT = ROOT / "apps" / "mobile" / "assets" / "avatars"
WEB_TS = ROOT / "apps" / "web" / "app" / "lib" / "avatarCatalog.ts"
MOBILE_TS = ROOT / "apps" / "mobile" / "src" / "avatarCatalog.ts"
JSON_OUT = ROOT / "packages" / "shared" / "src" / "aoep_shared" / "data" / "avatars" / "catalog.json"


# Visual recipes keyed by avatar id — colors only; geometry from style templates.
RECIPES = {
    "r-nova": dict(bg=("#dbeafe", "#93c5fd"), skin="#c68642", hair="#3b2314",
                   lip="#a24b4b", eye="#2a1a10", brow="#2a1a10", glasses="#1e293b",
                   blush="#e8a090", shirt="#1e3a8a"),
    "r-amir": dict(bg=("#fde68a", "#f59e0b"), skin="#5c3317", hair="#1a0f0a",
                   lip="#7a3a35", eye="#1a0f0a", brow="#1a0f0a", glasses="",
                   blush="#8a5048", shirt="#065f46"),
    "r-mei": dict(bg=("#fce7f3", "#f9a8d4"), skin="#f1c27d", hair="#1c1917",
                  lip="#c45c6a", eye="#1c1917", brow="#1c1917", glasses="",
                  blush="#f0a8a0", shirt="#7c3aed"),
    "r-sofia": dict(bg=("#ffedd5", "#fb923c"), skin="#c68642", hair="#5c3317",
                    lip="#b44a52", eye="#2a1a10", brow="#2a1a10", glasses="",
                    blush="#e09a88", shirt="#b91c1c", earring="#fbbf24"),
    "r-jordan": dict(bg=("#e0e7ff", "#a5b4fc"), skin="#f1c27d", hair="#9a3412",
                     lip="#c45c6a", eye="#3f2a1d", brow="#9a3412", glasses="",
                     blush="#f0b0a0", shirt="#334155", freckles=True),
    "r-kai": dict(bg=("#ccfbf1", "#5eead4"), skin="#a97142", hair="#2a1a10",
                  lip="#8a4a45", eye="#2a1a10", brow="#2a1a10", glasses="",
                  blush="#c48878", shirt="#0f766e", beanie="#334155"),
    "r-priya": dict(bg=("#fae8ff", "#e879f9"), skin="#a97142", hair="#1c0f0a",
                    lip="#a24b4b", eye="#1c0f0a", brow="#1c0f0a", glasses="",
                    blush="#d48878", shirt="#ea580c"),
    "r-leo": dict(bg=("#dcfce7", "#86efac"), skin="#8d5524", hair="#1a0f0a",
                  lip="#7a3a35", eye="#1a0f0a", brow="#1a0f0a", glasses="#0f172a",
                  blush="#a07060", shirt="#166534"),
    "r-sam": dict(bg=("#e2e8f0", "#94a3b8"), skin="#ddb892", hair="#64748b",
                  lip="#a86a6a", eye="#334155", brow="#64748b", glasses="",
                  blush="#e0a898", shirt="#1e293b"),
    "c-peach": dict(bg=("#ffe4e6", "#fda4af"), skin="#f6c6a8", hair="#6b3e26",
                    lip="#e36b7a", eye="#2a1a10", cheek="#ff9aa8", shirt="#fb7185",
                    accent="#fbbf24"),
    "c-mint": dict(bg=("#d1fae5", "#6ee7b7"), skin="#ffe8d6", hair="#34d399",
                   lip="#e36b7a", eye="#14532d", cheek="#fda4af", shirt="#10b981",
                   freckles=True),
    "c-coco": dict(bg=("#fef3c7", "#fcd34d"), skin="#6b3e26", hair="#1c0f0a",
                   lip="#c45c6a", eye="#1c0f0a", cheek="#c47868", shirt="#f59e0b",
                   accent="#fbbf24"),
    "c-sky": dict(bg=("#e0f2fe", "#7dd3fc"), skin="#ffe0c2", hair="#334155",
                  lip="#e36b7a", eye="#0c4a6e", cheek="#fda4af", shirt="#38bdf8",
                  beanie="#0ea5e9"),
    "c-honey": dict(bg=("#ffedd5", "#fdba74"), skin="#e0ac69", hair="#5c3317",
                    lip="#c45c6a", eye="#3f2a1d", cheek="#f0a090", shirt="#f97316",
                    glasses="#1e293b"),
    "c-berry": dict(bg=("#fce7f3", "#f9a8d4"), skin="#c68642", hair="#3b2314",
                    lip="#e36b7a", eye="#2a1a10", cheek="#f09090", shirt="#db2777",
                    accent="#fb7185"),
    "c-moss": dict(bg=("#ecfccb", "#bef264"), skin="#c68642", hair="#365314",
                   lip="#c45c6a", eye="#14532d", cheek="#e8a090", shirt="#65a30d",
                   headphones="#334155"),
    "c-luna": dict(bg=("#ede9fe", "#c4b5fd"), skin="#ffe8d6", hair="#cbd5e1",
                   lip="#e36b7a", eye="#4c1d95", cheek="#fda4af", shirt="#8b5cf6",
                   accent="#e2e8f0"),
    "c-sunny": dict(bg=("#fef9c3", "#fde047"), skin="#a97142", hair="#1c0f0a",
                    lip="#c45c6a", eye="#1c0f0a", cheek="#d48878", shirt="#eab308"),
}


def _svg_wrap(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" '
        'role="img" width="128" height="128">\n'
        f"{body}\n</svg>\n"
    )


def _bg(c1: str, c2: str) -> str:
    return (
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{c1}"/>'
        f'<stop offset="100%" stop-color="{c2}"/>'
        f"</linearGradient></defs>"
        '<circle cx="64" cy="64" r="64" fill="url(#g)"/>'
    )


def realistic_svg(r: dict) -> str:
    glasses = ""
    if r.get("glasses"):
        glasses = (
            f'<g fill="none" stroke="{r["glasses"]}" stroke-width="2.4">'
            '<circle cx="46" cy="62" r="11"/><circle cx="82" cy="62" r="11"/>'
            '<path d="M57 62h14"/><path d="M35 60h-6"/><path d="M93 60h6"/></g>'
        )
    beanie = ""
    if r.get("beanie"):
        beanie = (
            f'<path d="M28 48c4-22 68-22 72 0v8H28z" fill="{r["beanie"]}"/>'
            f'<rect x="26" y="50" width="76" height="10" rx="4" fill="{r["beanie"]}"/>'
        )
    earring = ""
    if r.get("earring"):
        earring = (
            f'<circle cx="24" cy="78" r="3.5" fill="none" stroke="{r["earring"]}" stroke-width="2"/>'
            f'<circle cx="104" cy="78" r="3.5" fill="none" stroke="{r["earring"]}" stroke-width="2"/>'
        )
    freckles = ""
    if r.get("freckles"):
        freckles = (
            '<g fill="#c47a5a" opacity="0.7">'
            '<circle cx="40" cy="72" r="1.2"/><circle cx="46" cy="76" r="1"/>'
            '<circle cx="88" cy="72" r="1.2"/><circle cx="82" cy="76" r="1"/>'
            "</g>"
        )
    # Hair back layer + face + features + hair front accents
    body = f"""
{_bg(*r["bg"])}
<!-- hair back -->
<ellipse cx="64" cy="58" rx="42" ry="46" fill="{r["hair"]}"/>
<!-- shoulders -->
<path d="M20 128c8-22 28-34 44-34s36 12 44 34" fill="{r["shirt"]}"/>
<!-- neck -->
<rect x="54" y="92" width="20" height="16" rx="6" fill="{r["skin"]}"/>
<!-- face -->
<ellipse cx="64" cy="66" rx="30" ry="34" fill="{r["skin"]}"/>
<!-- ears -->
<ellipse cx="33" cy="70" rx="6" ry="8" fill="{r["skin"]}"/>
<ellipse cx="95" cy="70" rx="6" ry="8" fill="{r["skin"]}"/>
{earring}
<!-- brows -->
<path d="M42 54q8-6 16 0" fill="none" stroke="{r["brow"]}" stroke-width="2.2" stroke-linecap="round"/>
<path d="M70 54q8-6 16 0" fill="none" stroke="{r["brow"]}" stroke-width="2.2" stroke-linecap="round"/>
<!-- eyes -->
<ellipse cx="50" cy="64" rx="4.2" ry="5" fill="{r["eye"]}"/>
<ellipse cx="78" cy="64" rx="4.2" ry="5" fill="{r["eye"]}"/>
<circle cx="51.5" cy="62.5" r="1.3" fill="#fff" opacity="0.9"/>
<circle cx="79.5" cy="62.5" r="1.3" fill="#fff" opacity="0.9"/>
<!-- nose -->
<path d="M64 68v8" fill="none" stroke="{r["eye"]}" stroke-width="1.6" stroke-linecap="round" opacity="0.45"/>
<!-- blush -->
<ellipse cx="42" cy="76" rx="7" ry="4" fill="{r["blush"]}" opacity="0.45"/>
<ellipse cx="86" cy="76" rx="7" ry="4" fill="{r["blush"]}" opacity="0.45"/>
{freckles}
<!-- smile -->
<path d="M52 84q12 10 24 0" fill="none" stroke="{r["lip"]}" stroke-width="2.4" stroke-linecap="round"/>
{glasses}
{beanie}
<!-- hair front fringe for non-beanie -->
{"" if r.get("beanie") else f'<path d="M34 48c10 14 20 8 30 2 10 6 20 12 30-2-8-18-52-18-60 0z" fill="{r["hair"]}" opacity="0.95"/>'}
"""
    return _svg_wrap(body)


def cute_svg(r: dict) -> str:
    glasses = ""
    if r.get("glasses"):
        glasses = (
            f'<g fill="none" stroke="{r["glasses"]}" stroke-width="2.6">'
            '<circle cx="46" cy="64" r="12"/><circle cx="82" cy="64" r="12"/>'
            '<path d="M58 64h12"/></g>'
        )
    beanie = ""
    if r.get("beanie"):
        beanie = (
            f'<path d="M30 52c6-24 62-24 68 0v6H30z" fill="{r["beanie"]}"/>'
            f'<ellipse cx="64" cy="34" rx="10" ry="8" fill="{r["beanie"]}"/>'
            f'<circle cx="64" cy="26" r="4" fill="#fff" opacity="0.85"/>'
        )
    headphones = ""
    if r.get("headphones"):
        headphones = (
            f'<path d="M28 70c0-28 72-28 72 0" fill="none" stroke="{r["headphones"]}" stroke-width="5"/>'
            f'<rect x="22" y="68" width="12" height="22" rx="6" fill="{r["headphones"]}"/>'
            f'<rect x="94" y="68" width="12" height="22" rx="6" fill="{r["headphones"]}"/>'
        )
    accent = ""
    if r.get("accent"):
        # star / heart / crescent clips drawn generically near top-right hair
        accent = (
            f'<g transform="translate(92 40)">'
            f'<polygon points="0,-8 2.4,-2.4 8,-2.4 3.4,1.2 5.2,7 0,3.4 -5.2,7 -3.4,1.2 -8,-2.4 -2.4,-2.4" '
            f'fill="{r["accent"]}"/></g>'
        )
    freckles = ""
    if r.get("freckles"):
        freckles = (
            '<g fill="#c47a5a">'
            '<circle cx="40" cy="74" r="1.4"/><circle cx="46" cy="78" r="1.2"/>'
            '<circle cx="88" cy="74" r="1.4"/><circle cx="82" cy="78" r="1.2"/>'
            "</g>"
        )
    # Extra hair shapes for pigtails / puffs / cornrows hinted via ellipses
    hair_extra = (
        f'<ellipse cx="28" cy="48" rx="14" ry="16" fill="{r["hair"]}"/>'
        f'<ellipse cx="100" cy="48" rx="14" ry="16" fill="{r["hair"]}"/>'
    )
    body = f"""
{_bg(*r["bg"])}
<!-- hair dome -->
<ellipse cx="64" cy="56" rx="44" ry="46" fill="{r["hair"]}"/>
{hair_extra}
<!-- body -->
<path d="M18 128c10-26 30-38 46-38s36 12 46 38" fill="{r["shirt"]}"/>
<!-- face -->
<circle cx="64" cy="70" r="34" fill="{r["skin"]}"/>
<!-- ears -->
<circle cx="30" cy="72" r="8" fill="{r["skin"]}"/>
<circle cx="98" cy="72" r="8" fill="{r["skin"]}"/>
{headphones}
<!-- eyes (big cute) -->
<ellipse cx="48" cy="68" rx="7" ry="9" fill="{r["eye"]}"/>
<ellipse cx="80" cy="68" rx="7" ry="9" fill="{r["eye"]}"/>
<circle cx="50.5" cy="65" r="2.4" fill="#fff"/>
<circle cx="82.5" cy="65" r="2.4" fill="#fff"/>
<circle cx="46" cy="71" r="1.2" fill="#fff" opacity="0.7"/>
<circle cx="78" cy="71" r="1.2" fill="#fff" opacity="0.7"/>
<!-- brows -->
<path d="M38 56q10-7 18 0" fill="none" stroke="{r["eye"]}" stroke-width="2.4" stroke-linecap="round"/>
<path d="M72 56q10-7 18 0" fill="none" stroke="{r["eye"]}" stroke-width="2.4" stroke-linecap="round"/>
<!-- cheeks -->
<ellipse cx="38" cy="80" rx="9" ry="5" fill="{r["cheek"]}" opacity="0.7"/>
<ellipse cx="90" cy="80" rx="9" ry="5" fill="{r["cheek"]}" opacity="0.7"/>
{freckles}
<!-- mouth -->
<path d="M54 86q10 12 20 0" fill="none" stroke="{r["lip"]}" stroke-width="3" stroke-linecap="round"/>
{glasses}
{beanie}
{accent}
"""
    return _svg_wrap(body)


def render(avatar_id: str) -> str:
    entry = AVATAR_CATALOG[avatar_id]
    recipe = RECIPES[avatar_id]
    if entry.style == "realistic":
        return realistic_svg(recipe)
    return cute_svg(recipe)


def write_ts_catalog(path: Path, *, require_prefix: str, asset_ext: str = "svg") -> None:
    entries = avatar_catalog_list()
    lines = [
        "// Auto-generated by scripts/generate_profile_avatars.py — do not edit.",
        "export type AvatarStyle = \"realistic\" | \"cute\";",
        "",
        "export type AvatarEntry = {",
        "  id: string;",
        "  label: string;",
        "  style: AvatarStyle;",
        "  alt: string;",
        "  path: string;",
        "  skin?: string;",
        "  hair?: string;",
        "  accessories?: string;",
        "  expression?: string;",
        "};",
        "",
        f'export const DEFAULT_AVATAR_ID = "{DEFAULT_AVATAR_ID}";',
        "",
        "export const LEGACY_AVATAR_ALIASES: Record<string, string> = {",
        '  "": DEFAULT_AVATAR_ID,',
        '  default: DEFAULT_AVATAR_ID,',
        '  none: DEFAULT_AVATAR_ID,',
        '  null: DEFAULT_AVATAR_ID,',
        '  undefined: DEFAULT_AVATAR_ID,',
        '  logo: "c-sunny",',
        '  "logo-mark": "c-sunny",',
        '  bayon: "c-sunny",',
        '  "bayon-buddy": "c-sunny",',
        '  mascot: "c-sunny",',
        '  "salareen-mascot": "c-sunny",',
        '  initials: DEFAULT_AVATAR_ID,',
        '  emoji: "c-peach",',
        '  graduate: "c-sunny",',
        '  theodore: "c-moss",',
        '  "ai-host": "c-moss",',
        '  "presenter-male": "r-amir",',
        '  "presenter-female": "r-sofia",',
        "};",
        "",
        "export const AVATAR_CATALOG: AvatarEntry[] = [",
    ]
    for e in entries:
        lines.append(
            "  {"
            f' id: "{e["id"]}", label: "{e["label"]}", style: "{e["style"]}",'
            f' alt: {json.dumps(e["alt"])}, path: "{e["path"]}",'
            f' skin: {json.dumps(e.get("skin") or "")},'
            f' hair: {json.dumps(e.get("hair") or "")},'
            f' accessories: {json.dumps(e.get("accessories") or "")}'
            " },"
        )
    lines.append("];")
    lines.append("")
    if require_prefix:
        lines.append("export const AVATAR_IMAGES: Record<string, number> = {")
        for e in entries:
            lines.append(f'  "{e["id"]}": require("{require_prefix}/{e["id"]}.{asset_ext}"),')
        lines.append("};")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    missing = [aid for aid in AVATAR_CATALOG if aid not in RECIPES]
    if missing:
        raise SystemExit(f"missing recipes for: {missing}")

    WEB_OUT.mkdir(parents=True, exist_ok=True)
    MOBILE_OUT.mkdir(parents=True, exist_ok=True)
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)

    for avatar_id in AVATAR_CATALOG:
        svg = render(avatar_id)
        (WEB_OUT / f"{avatar_id}.svg").write_text(svg, encoding="utf-8")
        try:
            import cairosvg
            png_path = MOBILE_OUT / f"{avatar_id}.png"
            cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(png_path),
                             output_width=256, output_height=256)
        except Exception:
            # Fallback: keep SVG on mobile if rasterizer unavailable.
            (MOBILE_OUT / f"{avatar_id}.svg").write_text(svg, encoding="utf-8")

    JSON_OUT.write_text(
        json.dumps(
            {
                "default_id": DEFAULT_AVATAR_ID,
                "styles": [
                    {"id": "realistic", "label": "Realistic"},
                    {"id": "cute", "label": "Cute"},
                ],
                "avatars": avatar_catalog_list(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    write_ts_catalog(WEB_TS, require_prefix="")
    # Rewrite web TS without require()
    text = WEB_TS.read_text(encoding="utf-8")
    if "AVATAR_IMAGES" in text:
        text = text.split("export const AVATAR_IMAGES")[0].rstrip() + "\n"
        WEB_TS.write_text(text, encoding="utf-8")

    # avatarCatalog.ts lives in src/, so one "../" reaches apps/mobile/assets.
    write_ts_catalog(MOBILE_TS, require_prefix="../assets/avatars", asset_ext="png")
    print(f"Generated {len(AVATAR_CATALOG)} avatars -> {WEB_OUT} + {MOBILE_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
