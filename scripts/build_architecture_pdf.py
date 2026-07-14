#!/usr/bin/env python3
"""Build the Salareen / AOEP architecture document (diagrams + PDF).

Renders accurate, code-grounded architecture diagrams with matplotlib (NOT an
image model, so they stay correct) into docs/diagrams/architecture/, then
compiles them plus comprehensive prose into docs/architecture.pdf with reportlab.

Deterministic and offline: no network, no GPU. Re-run whenever the architecture
changes so the PDF stays current.

Deps (build-time only, pinned):  pip install matplotlib==3.11.0 reportlab==5.0.0
Usage:                           python3 scripts/build_architecture_pdf.py
"""

from __future__ import annotations

import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIAG_DIR = ROOT / "docs" / "diagrams" / "architecture"
PDF_PATH = ROOT / "docs" / "architecture.pdf"


def _version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


# --- palette -----------------------------------------------------------------
C = {
    "client": "#dbeafe",   # frontend / clients (blue)
    "svc": "#dcfce7",      # backend services (green)
    "shared": "#fef9c3",   # shared lib (yellow)
    "data": "#ede9fe",     # data stores (purple)
    "ext": "#fee2e2",      # external / edge (pink)
    "worker": "#ffedd5",   # CLI workers / sidecars (orange)
    "note": "#f1f5f9",     # neutral note
}
EDGE = "#334155"
TEXT = "#0f172a"
ARROW = "#475569"


# --- drawing helpers ---------------------------------------------------------
def _fig(title: str, w: float = 12.0, h: float = 7.6):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_title(title, fontsize=16, fontweight="bold", color=TEXT, loc="left", pad=12)
    return fig, ax


def _box(ax, x, y, w, h, text, fc, *, fs=9.5, bold=False, tc=TEXT, ec=EDGE):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.6",
        fc=fc, ec=ec, lw=1.2, zorder=2,
    ))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc, zorder=3,
            fontweight="bold" if bold else "normal", linespacing=1.25)


def _label(ax, x, y, text, *, fs=8.5, color=ARROW, ha="center", style="italic"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=color, fontstyle=style, zorder=3)


def _arrow(ax, p1, p2, *, color=ARROW, lw=1.4, ls="-", style="-|>", both=False):
    ax.add_patch(FancyArrowPatch(
        p1, p2, arrowstyle="<|-|>" if both else style, mutation_scale=13,
        color=color, lw=lw, linestyle=ls, shrinkA=3, shrinkB=3, zorder=1,
    ))


def _legend(ax, items, x=1, y=2.5):
    for i, (label, fc) in enumerate(items):
        bx = x + i * 19.5
        ax.add_patch(FancyBboxPatch((bx, y), 2.4, 2.4, boxstyle="round,pad=0.1,rounding_size=0.6",
                                    fc=fc, ec=EDGE, lw=1))
        ax.text(bx + 3.1, y + 1.2, label, ha="left", va="center", fontsize=8, color=TEXT)


def _save(fig, name):
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    out = DIAG_DIR / name
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# --- diagrams ----------------------------------------------------------------
def diagram_topology():
    fig, ax = _fig("1 · System topology — frontend, backend, shared, data")
    # clients
    _box(ax, 14, 88, 32, 8, "Web app\napps/web (Next.js)", C["client"], bold=True)
    _box(ax, 54, 88, 32, 8, "Mobile app\napps/mobile (Expo · iOS/Android)", C["client"], bold=True)

    services = [
        ("orchestrator\n:8000", "teaching brain · live rooms"),
        ("curriculum\n:8005", "catalog · RAG · homework"),
        ("identity\n:8008", "accounts · rewards"),
        ("speech\n:8002", "TTS · translate"),
        ("memory\n:8004", "signals · flags"),
        ("billing\n:8006", "plans · ads"),
        ("integrations\n:8007", "webhooks · bridges"),
        ("perception\n:8003", "face / attention"),
    ]
    x0, y0, bw, bh, gx, gy = 4, 56, 21.5, 11, 2.4, 3.5
    for i, (name, sub) in enumerate(services):
        col = i % 4
        row = i // 4
        x = x0 + col * (bw + gx)
        y = y0 - row * (bh + gy)
        _box(ax, x, y, bw, bh, f"{name}\n{sub}", C["svc"], fs=8.6, bold=True)
        _arrow(ax, (x + bw / 2, y + bh), (x + bw / 2, y + bh + gy - 0.5), color="#94a3b8", lw=0.9)

    # workers / sidecar
    _box(ax, 4, 34, 44, 6.5, "harvester · homework (CLI workers) → curriculum", C["worker"], fs=8.6)
    _box(ax, 52, 34, 44, 6.5, "cosyvoice GPU TTS sidecar (:9880) → speech", C["worker"], fs=8.6)

    # shared
    _box(ax, 6, 22, 88, 8, "packages/shared · aoep_shared — provider abstraction "
                            "(LLM · Speech · Vision · Media/LiveKit · Payment · ObjectStore · Search)",
         C["shared"], fs=9.5, bold=True)
    # data
    _box(ax, 6, 8, 20, 8, "Postgres\n+ pgvector", C["data"], fs=9, bold=True)
    _box(ax, 30, 8, 20, 8, "Redis\n(snapshots/state)", C["data"], fs=9, bold=True)
    _box(ax, 54, 8, 18, 8, "Object store\n(media/exports)", C["data"], fs=9, bold=True)
    _box(ax, 76, 8, 18, 8, "LiveKit\n(WebRTC media)", C["data"], fs=9, bold=True)

    # cross-tier arrows (representative)
    _arrow(ax, (30, 88), (25, 67))       # web -> orchestrator col
    _arrow(ax, (34, 88), (50, 67))       # web -> curriculum
    _arrow(ax, (70, 88), (74, 67))       # mobile -> identity
    _arrow(ax, (66, 88), (98, 67), ls=":")  # mobile -> speech-ish
    _arrow(ax, (50, 45), (50, 30.5), color="#94a3b8")   # services -> shared
    _arrow(ax, (50, 22), (50, 16.5), color="#94a3b8")   # shared -> data
    _label(ax, 50, 86, "HTTPS / JSON (per-service URL locally, /prefix via gateway when deployed)", fs=8)

    _legend(ax, [("frontend", C["client"]), ("service", C["svc"]),
                 ("shared lib", C["shared"]), ("data", C["data"]), ("worker", C["worker"])])
    return _save(fig, "arch_system_topology.png")


def diagram_network():
    fig, ax = _fig("2 · Network traffic flow — device → edge → services → data")
    _box(ax, 2, 62, 17, 14, "User device\nBrowser /\nMobile app", C["client"], bold=True)
    _box(ax, 24, 62, 18, 14, "Cloudflare\nDNS + TLS\nsalareen.com", C["ext"], bold=True)
    _box(ax, 47, 60, 20, 18, "nginx Ingress\nhost + path routing\ncookie affinity\ncert-manager TLS", C["ext"], bold=True, fs=8.6)
    _box(ax, 72, 70, 26, 9, "web pods ×3 (HPA)", C["svc"], fs=9, bold=True)
    _box(ax, 72, 58, 26, 9, "API pods :8000 ×3\n(HPA · PDB)", C["svc"], fs=8.8, bold=True)
    _box(ax, 72, 44, 26, 9, "Redis · Postgres\nObject store", C["data"], fs=8.8, bold=True)

    _arrow(ax, (19, 69), (24, 69))
    _label(ax, 21.5, 72, "HTTPS 443", fs=7.5, style="normal")
    _arrow(ax, (42, 69), (47, 69))
    _arrow(ax, (67, 70), (72, 74))
    _arrow(ax, (67, 66), (72, 62), )
    _label(ax, 63, 55, "/identity /curriculum\n/orchestrator /speech …", fs=7.5, ha="center")
    _arrow(ax, (85, 58), (85, 53), color="#94a3b8")
    _label(ax, 85, 55.5, "in-cluster", fs=7, style="normal")

    # media path
    _box(ax, 26, 30, 18, 12, "LiveKit Cloud\n/ self-hosted", C["data"], bold=True, fs=8.8)
    _arrow(ax, (12, 62), (30, 42), color="#7c3aed", lw=1.6, both=True)
    _label(ax, 31, 52, "WebRTC media\n(UDP/TLS) · token-authed", fs=7.6, color="#6d28d9", ha="left")

    # registry / CI
    _box(ax, 55, 30, 20, 10, "Vultr Container\nRegistry", C["worker"], fs=8.6, bold=True)
    _box(ax, 55, 14, 20, 10, "GitHub Actions\ndeploy.yml", C["note"], fs=8.6, bold=True)
    _arrow(ax, (65, 24), (65, 30))
    _label(ax, 76, 40, "image pull secret", fs=7.5, ha="left", style="normal")
    _arrow(ax, (75, 35), (82, 44), ls=":", color="#94a3b8")

    _box(ax, 2, 26, 17, 13, "Auth: Bearer\nJWT header\non every\nprivate call", C["note"], fs=8.2)
    _arrow(ax, (10, 62), (10, 39), color="#94a3b8", ls=":")

    _legend(ax, [("client", C["client"]), ("edge/net", C["ext"]),
                 ("service", C["svc"]), ("data", C["data"]), ("ops", C["note"])])
    return _save(fig, "arch_network_flow.png")


def diagram_accounts():
    fig, ax = _fig("3 · Accounts, auth & language — identity of the learner")
    _box(ax, 4, 80, 26, 12, "Web / Mobile\nsignup · login\n(email · OAuth · passkey)", C["client"], bold=True, fs=8.8)
    _box(ax, 40, 80, 26, 12, "identity :8008\n/auth/* → JWT\n(session token)", C["svc"], bold=True, fs=8.8)
    _box(ax, 74, 80, 22, 12, "Redis snapshot\ndurable across\nreplicas/redeploys", C["data"], bold=True, fs=8.6)
    _arrow(ax, (30, 86), (40, 86))
    _label(ax, 35, 89, "credentials", fs=7.5, style="normal")
    _arrow(ax, (66, 86), (74, 86))
    _label(ax, 70, 89, "persist", fs=7.5, style="normal")

    _box(ax, 4, 60, 26, 12, "Client stores JWT\nsends Authorization:\nBearer <token>", C["client"], fs=8.6)
    _box(ax, 40, 60, 26, 12, "GET /auth/me →\naccount.public()\nincl. preferred_language", C["svc"], fs=8.6)
    _arrow(ax, (17, 80), (17, 72))
    _arrow(ax, (30, 66), (40, 66))
    _arrow(ax, (53, 80), (53, 72), both=True)

    _box(ax, 4, 40, 26, 12, "Device adopts locale\n(LocaleProvider) →\nUI + course in their\nlanguage", C["client"], fs=8.4)
    _box(ax, 40, 40, 26, 12, "POST /account/language\npersists the pick →\nfollows every device", C["svc"], fs=8.4)
    _arrow(ax, (17, 60), (17, 52))
    _arrow(ax, (30, 46), (40, 46), both=True)
    _arrow(ax, (53, 60), (53, 52))

    _box(ax, 74, 46, 22, 20,
         "identity owns:\n• students / profiles\n• enrollments\n• rewards / points\n• membership tiers\n• preferred_language",
         C["note"], fs=8.2)

    _box(ax, 4, 18, 62, 12,
         "Bearer token authorizes other services — orchestrator (live-room join carries the\n"
         "learner's language), curriculum, billing, memory. The tutor answers each learner in\n"
         "the language on their profile/device.", C["shared"], fs=8.6)
    _arrow(ax, (35, 40), (35, 30), color="#94a3b8")

    _legend(ax, [("client", C["client"]), ("identity svc", C["svc"]),
                 ("data", C["data"]), ("cross-service", C["shared"])])
    return _save(fig, "arch_account_auth_flow.png")


def diagram_data():
    fig, ax = _fig("4 · Data flow & stores — content, sessions, signals, state")
    # content pipeline
    _box(ax, 3, 82, 20, 10, "Sources\n(web · files · DB)", C["ext"], fs=8.6, bold=True)
    _box(ax, 28, 82, 22, 10, "harvester\ncrawl → generate\n.pptx + .course.json", C["worker"], fs=8.4, bold=True)
    _box(ax, 55, 82, 22, 10, "curriculum :8005\ncatalog + RAG corpus", C["svc"], fs=8.6, bold=True)
    _box(ax, 82, 82, 15, 10, "Object\nstore", C["data"], fs=8.6, bold=True)
    _arrow(ax, (23, 87), (28, 87))
    _arrow(ax, (50, 87), (55, 87))
    _arrow(ax, (77, 87), (82, 87), ls=":")

    # teaching / sessions
    _box(ax, 3, 60, 20, 10, "Web / Mobile\nlearner", C["client"], fs=8.6, bold=True)
    _box(ax, 28, 60, 22, 10, "orchestrator :8000\nsessions · tutor Q&A", C["svc"], fs=8.6, bold=True)
    _box(ax, 55, 60, 22, 10, "session store\n(Redis / in-mem)", C["data"], fs=8.6, bold=True)
    _box(ax, 82, 60, 15, 10, "RAG\nretrieve", C["shared"], fs=8.6, bold=True)
    _arrow(ax, (23, 65), (28, 65), both=True)
    _arrow(ax, (50, 65), (55, 65), both=True)
    _arrow(ax, (50, 68), (82, 68), ls=":", color="#94a3b8")

    # live rooms
    _box(ax, 28, 42, 22, 9, "live rooms\n(orchestrator)", C["svc"], fs=8.6, bold=True)
    _box(ax, 55, 42, 22, 9, "live_room state\n→ Redis (all replicas)", C["data"], fs=8.4, bold=True)
    _box(ax, 82, 42, 15, 9, "LiveKit\ntokens", C["data"], fs=8.4, bold=True)
    _arrow(ax, (39, 60), (39, 51))
    _arrow(ax, (50, 46.5), (55, 46.5), both=True)
    _arrow(ax, (77, 46.5), (82, 46.5), ls=":")

    # signals + accounts
    _box(ax, 3, 24, 22, 9, "memory :8004\nmastery · behavior · flags", C["svc"], fs=8.2, bold=True)
    _box(ax, 30, 24, 22, 9, "identity :8008\naccounts · rewards", C["svc"], fs=8.4, bold=True)
    _box(ax, 57, 24, 20, 9, "Redis snapshots", C["data"], fs=8.6, bold=True)
    _box(ax, 80, 24, 17, 9, "adaptive\nengine (shared)", C["shared"], fs=8.4, bold=True)
    _arrow(ax, (14, 42), (14, 33), color="#94a3b8", ls=":")
    _arrow(ax, (25, 28.5), (30, 28.5))
    _arrow(ax, (52, 28.5), (57, 28.5), both=True)
    _arrow(ax, (25, 30), (80, 31), ls=":", color="#94a3b8")

    _box(ax, 3, 8, 94, 8,
         "Telemetry / metrics / feature flags flow from every service (create_service) → memory + /metrics; "
         "content packs (JSON/JSONL) merge into the catalog with no code change.", C["note"], fs=8.4)

    _legend(ax, [("client", C["client"]), ("service", C["svc"]),
                 ("data", C["data"]), ("shared", C["shared"]), ("worker/ext", C["worker"])])
    return _save(fig, "arch_data_flow.png")


def diagram_live_class():
    fig, ax = _fig("5 · Live-class lifecycle — join → teach → Q&A → complete")
    steps = [
        ("Learner joins room\n(name + language from profile)", C["client"]),
        ("Server stores language on Participant;\nmints LiveKit no-publish token (mutex)", C["svc"]),
        ("Tick loop (any client, 8s): auto-start when\nfull / 5-min past scheduled time", C["svc"]),
        ("AI presents; slides auto-advance on a dwell\ntimer; AI answers in the learner's language", C["svc"]),
        ("Q&A: raise hand → host/AI grants floor →\npublish token issued (one speaker at a time)", C["shared"]),
        ("Allotted time expires → auto-end → courteous\n\"class complete\" farewell (multilingual)", C["ext"]),
        ("Countdown → learner excused back to classes", C["client"]),
    ]
    y = 90
    for i, (text, fc) in enumerate(steps):
        _box(ax, 16, y - 9, 68, 8, text, fc, fs=9)
        if i < len(steps) - 1:
            _arrow(ax, (50, y - 9), (50, y - 12.5))
        y -= 12.2
    _box(ax, 2, 40, 12, 40, "Backed by\nRedis live-\nroom state\nso every\nreplica\nagrees", C["data"], fs=8)
    _box(ax, 86, 40, 12, 40, "Solo 1:1\nis the same\nroom, one\nlearner\nseat\n(no auto-\nend)", C["note"], fs=8)
    _legend(ax, [("client", C["client"]), ("service", C["svc"]),
                 ("shared", C["shared"]), ("end", C["ext"]), ("data", C["data"])])
    return _save(fig, "arch_live_class_flow.png")


def diagram_deploy():
    fig, ax = _fig("6 · Deployment — Vultr Kubernetes Engine (namespace aoep)")
    _box(ax, 3, 84, 22, 9, "Cloudflare DNS + TLS\nsalareen.com", C["ext"], bold=True, fs=8.6)
    _box(ax, 3, 66, 22, 9, "GitHub Actions\ndeploy.yml\nbuild · push · roll", C["note"], bold=True, fs=8.4)
    _box(ax, 3, 48, 22, 9, "Vultr Container\nRegistry", C["worker"], bold=True, fs=8.6)

    # cluster
    ax.add_patch(FancyBboxPatch((30, 8), 68, 86, boxstyle="round,pad=0.4,rounding_size=2",
                                fc="#f8fafc", ec="#94a3b8", lw=1.4, ls="--", zorder=0))
    ax.text(32, 90, "VKE cluster — namespace aoep", fontsize=10, fontweight="bold", color=TEXT)
    _box(ax, 34, 78, 60, 8, "nginx Ingress (host + path routing · session affinity · cert-manager TLS)", C["ext"], fs=8.6, bold=True)
    _box(ax, 34, 66, 28, 8, "web Deployment ×3\nHPA 3→30 · PDB", C["svc"], fs=8.4, bold=True)
    _box(ax, 66, 66, 28, 8, "API tier ×3 each\nHPA · PDB · anti-affinity", C["svc"], fs=8.2, bold=True)
    _box(ax, 34, 52, 60, 8, "orchestrator · curriculum · identity · speech · memory · billing · integrations · perception (:8000)",
         C["svc"], fs=7.8)
    _box(ax, 34, 38, 18, 8, "redis-0\n(StatefulSet)", C["data"], fs=8.2, bold=True)
    _box(ax, 55, 38, 20, 8, "cosyvoice GPU\n(optional pool)", C["worker"], fs=8.0, bold=True)
    _box(ax, 78, 38, 16, 8, "Vultr Object\nStorage", C["data"], fs=8.0, bold=True)
    _box(ax, 34, 24, 60, 8, "aoep-config (ConfigMap) + aoep-secrets (out-of-band) — LiveKit, DB, payments, keys", C["note"], fs=8.0)
    _box(ax, 34, 12, 60, 7, "LiveKit Cloud (WebRTC) reached directly by clients via LIVEKIT_URL", C["data"], fs=8.0)

    _arrow(ax, (14, 84), (14, 75))
    _arrow(ax, (14, 66), (14, 57))
    _arrow(ax, (25, 52.5), (34, 56), ls=":", color="#94a3b8")
    _label(ax, 27, 60, "image\npull", fs=7, ha="left", style="normal")
    _arrow(ax, (25, 88), (34, 82))
    _arrow(ax, (64, 78), (60, 74), color="#94a3b8")
    _arrow(ax, (78, 78), (80, 74), color="#94a3b8")
    _arrow(ax, (64, 66), (64, 60), color="#94a3b8")

    _legend(ax, [("edge", C["ext"]), ("service", C["svc"]),
                 ("data", C["data"]), ("ops/reg", C["worker"]), ("config", C["note"])])
    return _save(fig, "arch_deploy_vke.png")


# --- PDF ---------------------------------------------------------------------
def build_pdf(diagrams: dict):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=colors.HexColor("#0f172a"), spaceAfter=8)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor("#1e293b"), spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)
    small = ParagraphStyle("Small", parent=body, fontSize=8.5, textColor=colors.HexColor("#475569"))
    title = ParagraphStyle("Title", parent=styles["Title"], fontSize=26, textColor=colors.HexColor("#0f172a"))

    def img(path, max_w=6.6 * inch):
        w, h = Image.open(path).size
        scale = max_w / w
        return RLImage(str(path), width=w * scale, height=h * scale)

    story = []
    today = datetime.date.today().isoformat()
    story += [
        Spacer(1, 1.6 * inch),
        Paragraph("Salareen / AOEP", title),
        Paragraph("Platform Architecture", ParagraphStyle("Sub", parent=title, fontSize=18,
                                                          textColor=colors.HexColor("#475569"))),
        Spacer(1, 0.3 * inch),
        Paragraph(f"Agentic Online Education Platform &mdash; version {_version()} &middot; {today}", body),
        Paragraph("Frontend, backend, accounts, data flow, network traffic, live classes, and deployment. "
                  "Diagrams are generated from code by <font face='Courier'>scripts/build_architecture_pdf.py</font> "
                  "and stay in sync with the system.", small),
        PageBreak(),
    ]

    # Overview
    story += [
        Paragraph("Overview", h1),
        Paragraph("Salareen (referred to as \"AI Classroom\" in parts of the codebase) is a multi-service education "
                  "platform for live AI-taught classes, mobile Drive-Mode audio lessons, adaptive learning, language "
                  "learning, rewards, careers-to-skills matching, compliance controls, and third-party integrations. "
                  "The <b>same codebase</b> runs local, cloud, or edge by environment configuration only.", body),
        Paragraph("Shape of the system", h2),
        Paragraph("&bull; <b>Monorepo.</b> Backend = Python/FastAPI microservices; web = Next.js "
                  "(<font face='Courier'>apps/web</font>); mobile = Expo React Native "
                  "(<font face='Courier'>apps/mobile</font>).", body),
        Paragraph("&bull; <b>Shared library.</b> <font face='Courier'>packages/shared</font> "
                  "(<font face='Courier'>aoep_shared</font>) holds all cross-service logic and a provider "
                  "abstraction (LLM, Speech, Vision, Media/LiveKit, Payment, Object Store, Search). Implementations "
                  "are chosen by env (<font face='Courier'>DEPLOY_MODE</font> = local | cloud | edge, plus per-component "
                  "<font face='Courier'>&lt;COMPONENT&gt;_MODE</font>) &mdash; no code forks between local and cloud.", body),
        Paragraph("&bull; <b>Offline-first.</b> Heavy providers target real endpoints; without them the code degrades "
                  "gracefully (RAG-grounded tutor fallback, device TTS, in-memory stores) so the teaching loop still runs.", body),
        Paragraph("Services and local ports", h2),
    ]
    svc_rows = [
        ["Service", "Pkg", "Port", "Owns"],
        ["orchestrator", "orchestrator", "8000", "teaching brain: sessions, tutor, live rooms, group classes, assessment, HIL"],
        ["speech", "speech_gw", "8002", "TTS routing/synthesis, translation, language learning"],
        ["perception", "perception", "8003", "consent-gated face recognition / engagement (OpenCV YuNet+SFace)"],
        ["memory", "memory", "8004", "consent, mastery/behavior signals, feature flags, surveys, mascots"],
        ["curriculum", "curriculum", "8005", "catalog, RAG corpus, decks, audio courses, jobs, homework, notifications"],
        ["billing", "billing", "8006", "plans, entitlements, payment methods, checkout, ads"],
        ["integrations", "integrations", "8007", "webhooks, LMS, finance, cloud connectors, Zoom/Teams/Meet bridges"],
        ["identity", "identity", "8008", "accounts, auth, students, rewards, enrollments, preferred language"],
        ["harvester", "harvester", "\u2014", "CLI worker: crawl/generate/export courses -> curriculum"],
        ["homework", "homework", "\u2014", "CLI worker: generate / OCR / authorship / autograde"],
        ["cosyvoice", "(server.py)", "9880", "GPU CosyVoice 2 TTS sidecar (POST /tts) for clone narration"],
    ]
    tbl = Table(svc_rows, colWidths=[1.0 * inch, 0.95 * inch, 0.5 * inch, 4.15 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [tbl,
              Paragraph("Every HTTP service also exposes <font face='Courier'>/health</font>, "
                        "<font face='Courier'>/version</font>, <font face='Courier'>/__meta</font>, "
                        "<font face='Courier'>/metrics</font>, and <font face='Courier'>/telemetry/*</font> "
                        "via <font face='Courier'>create_service()</font>. In Docker/k8s every service listens on "
                        "<font face='Courier'>:8000</font> internally; the <font face='Courier'>:800x</font> ports "
                        "above are local dev only.", small),
              PageBreak()]

    sections = [
        ("System topology", diagrams["topology"],
         "Clients (web + mobile) call the FastAPI services over HTTPS/JSON. Locally each service has its own port; "
         "when deployed the browser reaches them through same-origin path prefixes (<font face='Courier'>/identity</font>, "
         "<font face='Courier'>/curriculum</font>, &hellip;) that the gateway rewrites. Every service depends on "
         "<font face='Courier'>aoep_shared</font>, which in turn talks to the data tier. CLI workers (harvester, homework) "
         "feed the curriculum service; the cosyvoice GPU sidecar serves the speech gateway."),
        ("Network traffic flow", diagrams["network"],
         "User traffic enters via Cloudflare (DNS + TLS) to the nginx Ingress, which does host + path routing with cookie "
         "session affinity and cert-manager TLS, then forwards to the web pods or the API pods (all on :8000). Services reach "
         "Redis / Postgres / object storage in-cluster. Real-time class media is a separate path: clients connect directly to "
         "LiveKit (Cloud or self-hosted) over token-authenticated WebRTC. Images are pulled from the Vultr Container Registry "
         "using an image-pull secret; GitHub Actions builds and rolls them. Every private HTTP call carries an "
         "<font face='Courier'>Authorization: Bearer &lt;JWT&gt;</font> header."),
        ("Accounts, auth &amp; language", diagrams["accounts"],
         "Signup/login (email, OAuth, or passkey) mints a JWT from the identity service; the client sends it as a Bearer token. "
         "<font face='Courier'>GET /auth/me</font> returns the account, including <font face='Courier'>preferred_language</font>. "
         "The device adopts that locale (LocaleProvider) so the UI and course appear in the learner's language, and a change via "
         "the picker persists with <font face='Courier'>POST /account/language</font> so it follows the learner to every device. "
         "Identity is a system of record backed by a Redis snapshot (durable across replicas and redeploys) and owns students, "
         "enrollments, rewards/points, and membership tiers. The Bearer token authorizes the other services, and the tutor answers "
         "each learner in the language on their profile/device."),
        ("Data flow &amp; stores", diagrams["data"],
         "Content: the harvester crawls/generates courses (exporting <font face='Courier'>.pptx</font> + "
         "<font face='Courier'>.course.json</font>) into the curriculum catalog and RAG corpus. Teaching: apps drive "
         "orchestrator sessions (session store, Redis in cloud) that retrieve grounding passages via RAG and answer. Live rooms "
         "keep their state in Redis so every orchestrator replica serves the same room, and mint LiveKit tokens. Learner signals "
         "(mastery/behavior/flags) live in memory and feed the adaptive engine; accounts and rewards live in identity. Telemetry, "
         "metrics, and feature flags flow from every service; content packs merge into the catalog with no code change."),
        ("Live-class lifecycle", diagrams["live_class"],
         "A learner joins with a name and their language; the server records the language on the Participant and mints a "
         "no-publish LiveKit token (the single-speaker mutex). A tick loop (any client, every 8s) auto-starts the class when the "
         "room is full or 5 minutes past the scheduled time, auto-advances slides on a dwell timer, and auto-ends when the allotted "
         "time expires &mdash; showing a courteous multilingual \"class complete\" farewell before excusing everyone. Q&amp;A uses a "
         "raise-hand queue; the host/AI grants the floor, which issues a publish token so exactly one person talks. A solo 1:1 class "
         "is the same room scaled to a single learner seat (open-ended, no auto-end)."),
        ("Deployment (Vultr VKE)", diagrams["deploy"],
         "GitHub Actions (<font face='Courier'>deploy.yml</font>) builds images, pushes them to the Vultr Container Registry, and "
         "rolls the cluster. In the <font face='Courier'>aoep</font> namespace, the nginx Ingress fronts a web Deployment (HPA 3&rarr;30, "
         "PDB) and the API tier (each service ×3 with HPA, PDB, and zone anti-affinity, all on :8000). Redis runs as a StatefulSet; an "
         "optional GPU pool runs cosyvoice; media/exports use Vultr Object Storage. Configuration is split between "
         "<font face='Courier'>aoep-config</font> (ConfigMap) and <font face='Courier'>aoep-secrets</font> (managed out-of-band so "
         "<font face='Courier'>apply -k</font> never clobbers real secret values). Clients reach LiveKit directly via "
         "<font face='Courier'>LIVEKIT_URL</font>."),
    ]
    for name, path, text in sections:
        story += [Paragraph(name, h1), img(path), Spacer(1, 0.12 * inch), Paragraph(text, body), PageBreak()]

    story += [
        Paragraph("Rebuild &amp; references", h1),
        Paragraph("Regenerate this document (diagrams + PDF) after any architecture change:", body),
        Paragraph("<font face='Courier'>pip install matplotlib==3.11.0 reportlab==5.0.0</font><br/>"
                  "<font face='Courier'>python3 scripts/build_architecture_pdf.py</font>", small),
        Paragraph("Deeper references: <font face='Courier'>docs/architecture.txt</font> (canonical text), "
                  "<font face='Courier'>docs/api-reference.txt</font> (every endpoint), "
                  "<font face='Courier'>docs/hosting.txt</font> / <font face='Courier'>docs/scalability.txt</font>, "
                  "the per-service <font face='Courier'>README.txt</font>, and <font face='Courier'>infra/k8s-vke/RUNBOOK.txt</font>.", body),
    ]

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(PDF_PATH), pagesize=letter,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                            title="Salareen / AOEP Architecture")
    doc.build(story)
    return PDF_PATH


def main() -> int:
    diagrams = {
        "topology": diagram_topology(),
        "network": diagram_network(),
        "accounts": diagram_accounts(),
        "data": diagram_data(),
        "live_class": diagram_live_class(),
        "deploy": diagram_deploy(),
    }
    for name, path in diagrams.items():
        print(f"  diagram: {path.relative_to(ROOT)}")
    pdf = build_pdf(diagrams)
    size_kb = pdf.stat().st_size / 1024
    print(f"  PDF: {pdf.relative_to(ROOT)} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
