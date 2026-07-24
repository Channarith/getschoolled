#!/usr/bin/env python3
"""Build a comprehensive Salareen / AOEP platform overview PDF.

Includes architecture diagrams, feature catalog, capabilities/providers,
payment systems, and product screenshots. Complements docs/architecture.pdf
(diagrams-focused) with a broader product + systems brief.

Deps:  pip install matplotlib==3.11.0 reportlab==5.0.0 Pillow==11.1.0
Usage: python3 scripts/build_platform_overview_pdf.py
Also refreshes architecture diagrams via build_architecture_pdf helpers.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from PIL import Image  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image as RLImage,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Reuse architecture diagram builders
sys.path.insert(0, str(ROOT / "scripts"))
import build_architecture_pdf as arch  # noqa: E402

PDF_PATH = ROOT / "docs" / "platform-overview.pdf"
SCREEN_CACHE = ROOT / "docs" / "diagrams" / "overview-screens"
DIAG_DIR = ROOT / "docs" / "diagrams" / "architecture"


def _version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontSize=26, leading=32,
            textColor=colors.HexColor("#0f172a"), spaceAfter=8, alignment=TA_CENTER,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontSize=12, leading=16,
            textColor=colors.HexColor("#475569"), alignment=TA_CENTER, spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=16, leading=20,
            textColor=colors.HexColor("#0f172a"), spaceBefore=4, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=12, leading=15,
            textColor=colors.HexColor("#1e293b"), spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontSize=9.5, leading=13,
            textColor=colors.HexColor("#0f172a"), alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=8, leading=11,
            textColor=colors.HexColor("#475569"), spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontSize=8, leading=10,
            textColor=colors.HexColor("#64748b"), alignment=TA_CENTER, spaceAfter=10,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontSize=9, leading=12,
            textColor=colors.HexColor("#0f172a"), leftIndent=4,
        ),
    }


def _prep_screens() -> dict[str, Path]:
    SCREEN_CACHE.mkdir(parents=True, exist_ok=True)
    mapping = {
        "ecosystem": ROOT / "docs" / "brand" / "salareen_platform_ecosystem.png",
        "landing": ROOT / "docs" / "screens" / "landing.webp",
        "homepage": ROOT / "docs" / "screens" / "homepage.webp",
        "browse": ROOT / "docs" / "screens" / "browse_catalog.webp",
        "drive": ROOT / "docs" / "screens" / "drive_mode_player.webp",
        "live": ROOT / "docs" / "screens" / "live_class_answer.webp",
        "arcade": ROOT / "docs" / "screens" / "arcade_adult_quiz.webp",
        "corporate": ROOT / "docs" / "screens" / "corporate_programs.webp",
        "rewards": ROOT / "docs" / "screens" / "rewards_redeem.webp",
        "account": ROOT / "docs" / "screens" / "member_account.webp",
        "languages": ROOT / "docs" / "screens" / "languages_grid.webp",
        "admin": ROOT / "docs" / "screens" / "admin_feature_flags.webp",
        "kids": ROOT / "docs" / "screens" / "kids_mode.webp",
        "careers": ROOT / "docs" / "screens" / "careers_match.webp",
    }
    out: dict[str, Path] = {}
    for key, src in mapping.items():
        if not src.exists():
            continue
        dest = SCREEN_CACHE / f"{key}.png"
        im = Image.open(src).convert("RGB")
        w, h = im.size
        max_w = 1400
        if w > max_w:
            im = im.resize((max_w, int(h * max_w / w)), Image.Resampling.LANCZOS)
        im.save(dest, "PNG", optimize=True)
        out[key] = dest
    return out


def _img(path: Path, max_w: float = 6.5 * inch, max_h: float = 3.6 * inch):
    im = Image.open(path)
    w, h = im.size
    aspect = h / float(w)
    width = max_w
    height = width * aspect
    if height > max_h:
        height = max_h
        width = height / aspect
    return RLImage(str(path), width=width, height=height)


def _bullets(items: list[str], style):
    return ListFlowable(
        [ListItem(Paragraph(i, style), leftIndent=8, bulletColor=colors.HexColor("#0ea5e9"))
         for i in items],
        bulletType="bullet", start="•", leftIndent=12, spaceBefore=2, spaceAfter=6,
    )


def _table(rows, col_widths):
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def build_pdf(diagrams: dict[str, Path], screens: dict[str, Path]) -> Path:
    from aoep_shared.flags import FLAG_CATALOG
    from aoep_shared.payments import PaymentMethod, Processor, processor_for
    from aoep_shared.plan_pricing import CONSUMER_PLANS

    S = _styles()
    ver = _version()
    today = datetime.date.today().isoformat()
    story: list = []

    # ---- Cover --------------------------------------------------------------
    story += [
        Spacer(1, 0.6 * inch),
        Paragraph("Salareen", S["cover_title"]),
        Paragraph("Agentic Online Education Platform", S["cover_sub"]),
        Paragraph("Platform Architecture, Features &amp; Capabilities Overview", S["cover_sub"]),
        Spacer(1, 0.2 * inch),
    ]
    if "ecosystem" in screens:
        story += [_img(screens["ecosystem"], max_w=6.2 * inch, max_h=4.0 * inch),
                  Paragraph("Platform ecosystem map", S["caption"])]
    story += [
        Paragraph(f"<b>Version</b> {ver} &nbsp;·&nbsp; <b>Generated</b> {today}", S["cover_sub"]),
        Paragraph(
            "Compiled from the live monorepo: FastAPI microservices, Next.js web, "
            "Expo mobile, <font face='Courier'>aoep_shared</font> providers, billing/payments, "
            "and product screens under <font face='Courier'>docs/screens/</font>.",
            S["small"],
        ),
        PageBreak(),
    ]

    # ---- TOC-ish executive summary -----------------------------------------
    story += [
        Paragraph("1. Executive summary", S["h1"]),
        Paragraph(
            "Salareen (also referred to as AOEP / AI Classroom in parts of the codebase) is a "
            "multi-service education platform for live AI-taught classes, Drive Mode audio lessons, "
            "adaptive learning, language learning, corporate upskilling, arcade games, rewards, "
            "careers matching, compliance controls, and third-party integrations. The same codebase "
            "runs <b>local</b>, <b>cloud</b>, or <b>edge</b> by environment configuration only — "
            "no code forks.",
            S["body"],
        ),
        _bullets([
            f"<b>Version:</b> {ver} (repo <font face='Courier'>VERSION</font>)",
            "<b>Clients:</b> Next.js web (<font face='Courier'>apps/web</font>) + Expo mobile "
            "(<font face='Courier'>apps/mobile</font>)",
            "<b>Backend:</b> FastAPI microservices behind <font face='Courier'>aoep_shared</font> providers",
            "<b>Realtime media:</b> LiveKit (Salareen group/solo rooms)",
            "<b>Deploy:</b> Vultr Kubernetes Engine (VKE) + Cloudflare DNS/TLS",
            "<b>Monetization:</b> Free / Standard ($19.99) / VIP Premium ($29.99) + ads + global payments",
        ], S["bullet"]),
        Paragraph("2. Logical architecture", S["h1"]),
        Paragraph(
            "Browser and mobile apps call HTTPS JSON APIs. Locally each service has its own port; "
            "in cluster every service listens on <font face='Courier'>:8000</font> and is reached "
            "via path prefixes (<font face='Courier'>/identity</font>, <font face='Courier'>/curriculum</font>, …). "
            "Shared business logic lives in <font face='Courier'>packages/shared</font> "
            "(distribution <font face='Courier'>aoep-shared</font>).",
            S["body"],
        ),
    ]
    if "topology" in diagrams:
        story += [_img(diagrams["topology"], max_h=4.2 * inch),
                  Paragraph("System topology (services, clients, data, providers)", S["caption"])]
    story += [PageBreak()]

    # ---- Services table -----------------------------------------------------
    story += [Paragraph("3. Services &amp; ports", S["h1"])]
    svc_rows = [
        ["Service", "Pkg", "Port", "Owns"],
        ["orchestrator", "orchestrator", "8000",
         "Teaching brain: lessons, sessions, assessment, live rooms, group classes, director"],
        ["speech", "speech_gw", "8002", "TTS routing, translation, language learning APIs"],
        ["perception", "perception", "8003", "Consent-gated face recognition / engagement (YuNet+SFace)"],
        ["memory", "memory", "8004", "Profiles, consent, legal, feature flags, surveys, telemetry"],
        ["curriculum", "curriculum", "8005", "Catalog, RAG, homework, scenes, ads plan, recommendations"],
        ["billing", "billing", "8006", "Plans, entitlements, checkout, ad slots / revenue ledger"],
        ["integrations", "integrations", "8007", "Webhooks, LMS/LTI, finance, Zoom/Teams/Meet bridges"],
        ["identity", "identity", "8008", "Accounts, auth, students, rewards, enrollments, language"],
        ["harvester", "harvester", "CLI", "Crawl/generate courses; mandatory .pptx + .course.json export"],
        ["homework", "homework", "CLI", "Generate / OCR / authorship / autograde worker"],
        ["cosyvoice", "sidecar", "9880", "GPU CosyVoice 2 TTS for clone narration"],
    ]
    story += [
        _table(svc_rows, [1.0 * inch, 0.95 * inch, 0.55 * inch, 4.1 * inch]),
        Spacer(1, 0.1 * inch),
        Paragraph(
            "Every HTTP service exposes <font face='Courier'>/health</font>, "
            "<font face='Courier'>/version</font>, <font face='Courier'>/__meta</font>, "
            "<font face='Courier'>/metrics</font>, and <font face='Courier'>/telemetry/*</font> "
            "via <font face='Courier'>create_service()</font>.",
            S["small"],
        ),
        PageBreak(),
    ]

    # ---- Feature catalog ----------------------------------------------------
    story += [
        Paragraph("4. Product feature catalog", S["h1"]),
        Paragraph("4.1 Learning surfaces", S["h2"]),
        _bullets([
            "<b>Live AI class</b> — Theodore narrates slides; Ask-the-teacher with RAG-grounded answers",
            "<b>Group classes / live rooms</b> — LiveKit video, raise-hand Q&amp;A, gifts, moderation",
            "<b>Solo 1:1 rooms</b> — same room model scaled to one learner",
            "<b>Drive Mode</b> — eyes-free audio courses with hands-free voice Q&amp;A",
            "<b>Corporate / professional courses</b> — mid-course pop quiz + required end assessment",
            "<b>Homework grader</b> — typed or handwritten with rationale + citations",
            "<b>Human-in-the-loop</b> — educator console reviews / co-grades when confidence is low",
            "<b>Languages</b> — pronunciation, speech practice; UI in 27 languages",
            "<b>Kids Mode</b> — age-appropriate pathways and parental account model",
            "<b>Arcade</b> — quiz/match + canvas games (geometry, stocks, chemistry Potion Lab, Challenge the AI)",
            "<b>Careers / jobs</b> — JD parse, skills match, certifications",
            "<b>XR lab</b> — audience readiness / XR assess APIs",
            "<b>Vision</b> — opt-in face/engagement via perception service",
        ], S["bullet"]),
        Paragraph("4.2 Platform &amp; ops", S["h2"]),
        _bullets([
            "Netflix-style home / browse / watch / recommended feeds",
            "Membership tiers, billing checkout, entitlements gate",
            "Rewards &amp; points ledger with prize redemption",
            "Feature flags (admin) with per-subject overrides",
            "Post-class surveys + admin insights / data mart",
            "Consent, legal, transparency, model cards, security pages",
            "Admin observability (versions, telemetry, ad revenue)",
            "Content packs + harvester corpus growth without code forks",
            "Adaptive learning / Foresight recommendations",
            "Assessment: formative checkpoints + verified summative pass tokens",
        ], S["bullet"]),
        PageBreak(),
    ]

    # ---- Screenshots --------------------------------------------------------
    story += [Paragraph("5. Product screenshots", S["h1"]),
              Paragraph(
                  "Screens captured from the shipped web UI "
                  "(<font face='Courier'>docs/screens/</font>). Newer arcade canvas games may not yet "
                  "have dedicated screenshots; quiz/match and core learning surfaces are shown.",
                  S["body"])]
    gallery = [
        ("landing", "Marketing / landing"),
        ("homepage", "Signed-in home feed"),
        ("browse", "Browse catalog"),
        ("drive", "Drive Mode player"),
        ("live", "Live class + grounded Ask answer"),
        ("arcade", "Learning Arcade quiz"),
        ("corporate", "Corporate training programs"),
        ("languages", "Languages grid"),
        ("kids", "Kids Mode"),
        ("careers", "Careers match"),
        ("rewards", "Rewards redeem"),
        ("account", "Member account"),
        ("admin", "Admin feature flags"),
    ]
    for key, caption in gallery:
        if key not in screens:
            continue
        story.append(KeepTogether([
            _img(screens[key], max_w=6.3 * inch, max_h=3.35 * inch),
            Paragraph(caption, S["caption"]),
        ]))
    story.append(PageBreak())

    # ---- Capabilities / providers -------------------------------------------
    story += [
        Paragraph("6. Provider capabilities (dual-mode)", S["h1"]),
        Paragraph(
            "Capabilities are selected by <font face='Courier'>DEPLOY_MODE</font> "
            "(local | cloud | edge) plus optional per-component "
            "<font face='Courier'>&lt;COMPONENT&gt;_MODE</font>. Blank override inherits deploy mode. "
            "Offline paths degrade gracefully (RAG tutor fallback, device TTS, sandbox payments).",
            S["body"],
        ),
        _table([
            ["Capability", "Local / offline", "Cloud"],
            ["LLM", "vLLM/Ollama or grounded RAG fallback", "Cloud LLM endpoint"],
            ["Speech / TTS", "edge-tts → device voices; CosyVoice optional", "ElevenLabs → edge-tts → device"],
            ["Vision", "OpenCV YuNet + SFace (CPU)", "Same self-hosted models"],
            ["Media", "Local LiveKit or degraded tiles", "LiveKit Cloud / cluster JWT mint"],
            ["Object store", "Local / MinIO", "S3-compatible (Vultr Object Storage)"],
            ["Payment", "Sandbox (all methods simulated)", "Routed real processors (keys required)"],
            ["OCR / Search / Jobs", "Local stubs / light impls", "Cloud connectors when configured"],
        ], [1.15 * inch, 2.55 * inch, 2.9 * inch]),
        Spacer(1, 0.12 * inch),
        Paragraph("6.1 Feature flags", S["h2"]),
        Paragraph(
            f"Runtime catalog currently defines <b>{len(FLAG_CATALOG)}</b> flags across engagement, "
            "data, access, monetization, AI, UX, and ops — evaluated via memory service "
            "(<font face='Courier'>GET /flags/evaluate</font>) with admin overrides.",
            S["body"],
        ),
        PageBreak(),
    ]

    # ---- Payments -----------------------------------------------------------
    methods = list(PaymentMethod)
    by_proc: dict[str, list[str]] = {}
    for m in methods:
        proc = processor_for(m).value
        by_proc.setdefault(proc, []).append(m.value)

    plan_rows = [["Plan", "Tier", "Price (USD/mo)", "Notes"]]
    for key, plan in CONSUMER_PLANS.items():
        plan_rows.append([
            getattr(plan, "display_name", key),
            getattr(plan, "tier", key),
            f"${getattr(plan, 'price_usd', 0):.2f}",
            getattr(plan, "blurb", "")[:70],
        ])

    story += [
        Paragraph("7. Membership &amp; payment systems", S["h1"]),
        Paragraph("7.1 Consumer plans", S["h2"]),
        Paragraph(
            "Netflix-style calendar billing on the signup day. Standard includes ads; "
            "VIP Premium is ad-free. Entitlements are gated by the billing service "
            "(<font face='Courier'>can_start</font>) before classes start.",
            S["body"],
        ),
        _table(plan_rows, [1.3 * inch, 0.9 * inch, 1.1 * inch, 3.3 * inch]),
        Spacer(1, 0.1 * inch),
        Paragraph("7.2 Global payment methods", S["h2"]),
        Paragraph(
            f"The platform models <b>{len(methods)}</b> consumer payment methods routed across "
            f"<b>{len(by_proc)}</b> processors. Local sandbox simulates every method; cloud "
            "providers advertise only what their API keys can process. Country/locale helpers "
            "pick a sensible default method set for checkout UI.",
            S["body"],
        ),
        _table([
            ["Processor", "Example methods"],
            *[[proc, ", ".join(sorted(ms)[:12]) + ("…" if len(ms) > 12 else "")]
              for proc, ms in sorted(by_proc.items())],
        ], [1.4 * inch, 5.2 * inch]),
        Spacer(1, 0.08 * inch),
        Paragraph(
            "Regional coverage includes Stripe rails (cards, wallets, BNPL, SEPA, Alipay/WeChat, …), "
            "PayPal/Venmo, Square, Razorpay (UPI/PhonePe), Mercado Pago (PIX), VNPay/MoMo, "
            "ABA/KHQR/Wing (Cambodia), YooMoney/Mir, Toss/Kakao/Naver, and manual Zelle.",
            S["small"],
        ),
        Paragraph("7.3 Ads &amp; revenue", S["h2"]),
        _bullets([
            "Video pre/mid-roll (VAST/VMAP) on watch / class / Drive — empty plan for VIP",
            "Display slots via billing <font face='Courier'>/ads/slot</font>; mobile AdMob banners",
            "Impression/click beacons → AdRevenueLedger; admin Ad Revenue panel",
        ], S["bullet"]),
        PageBreak(),
    ]

    # ---- Key flows with diagrams --------------------------------------------
    story += [Paragraph("8. Key system flows", S["h1"])]
    flow_sections = [
        ("network", "Network traffic",
         "Cloudflare → nginx Ingress (path routing + session affinity) → web/API pods; "
         "WebRTC to LiveKit is a separate path."),
        ("accounts", "Accounts &amp; language",
         "Identity mints JWT; preferred_language follows the learner across devices; "
         "rewards and membership live here with Redis snapshot durability."),
        ("data", "Data &amp; content",
         "Harvester → curriculum catalog/RAG; orchestrator sessions; Redis room state; "
         "object storage for media/exports."),
        ("live_class", "Live-class lifecycle",
         "Join → LiveKit token → tick loop auto-start/advance/end; raise-hand speaking mutex."),
        ("deploy", "VKE deployment",
         "GitHub Actions builds to Vultr registry; HPA/PDB; ConfigMap + out-of-band secrets."),
    ]
    for key, title, text in flow_sections:
        if key not in diagrams:
            continue
        story += [
            Paragraph(title, S["h2"]),
            _img(diagrams[key], max_h=3.5 * inch),
            Paragraph(text, S["caption"]),
        ]
    story.append(PageBreak())

    # ---- Clients ------------------------------------------------------------
    web_routes = sorted({
        "/" + str(p.relative_to(ROOT / "apps" / "web" / "app")).replace("/page.tsx", "").replace("page.tsx", "")
        for p in (ROOT / "apps" / "web" / "app").rglob("page.tsx")
        if "[" not in str(p)
    })
    web_routes = [r if r != "/." else "/" for r in web_routes]
    mobile_screens = sorted(p.stem for p in (ROOT / "apps" / "mobile" / "src" / "screens").glob("*.tsx"))

    story += [
        Paragraph("9. Client surfaces", S["h1"]),
        Paragraph("9.1 Web (Next.js)", S["h2"]),
        Paragraph(
            f"<b>{len(web_routes)}</b> top-level app routes (dynamic segments omitted), including "
            "arcade suite, corporate learn, Drive Mode, live rooms, billing, admin, and legal.",
            S["body"],
        ),
        Paragraph(", ".join(f"<font face='Courier'>{r}</font>" for r in web_routes[:45])
                  + ("…" if len(web_routes) > 45 else ""), S["small"]),
        Paragraph("9.2 Mobile (Expo)", S["h2"]),
        Paragraph(
            f"<b>{len(mobile_screens)}</b> screens: " + ", ".join(mobile_screens) + ".",
            S["body"],
        ),
        PageBreak(),
    ]

    # ---- Security / compliance note -----------------------------------------
    story += [
        Paragraph("10. Security, privacy &amp; compliance posture", S["h1"]),
        _bullets([
            "Auth: PBKDF2 credentials + HMAC/JWT bearer tokens (identity)",
            "Admin ops gated by <font face='Courier'>ADMIN_SECRET</font>",
            "Biometrics opt-in + consent-gated; self-hosted vision models",
            "Legal acceptance, retention, transparency, and model-card pages",
            "Redis snapshot durability for identity (not a throwaway cache)",
            "Secrets managed out-of-band in k8s; ConfigMap holds non-secret config",
        ], S["bullet"]),
        Paragraph("11. How to regenerate", S["h1"]),
        Paragraph(
            "<font face='Courier'>pip install matplotlib==3.11.0 reportlab==5.0.0 Pillow==11.1.0</font><br/>"
            "<font face='Courier'>python3 scripts/build_architecture_pdf.py</font> "
            "&nbsp;— diagrams + <font face='Courier'>docs/architecture.pdf</font><br/>"
            "<font face='Courier'>python3 scripts/build_platform_overview_pdf.py</font> "
            "&nbsp;— this overview PDF",
            S["body"],
        ),
        Paragraph(
            "Canonical text: <font face='Courier'>docs/architecture.txt</font>. "
            "API surface: <font face='Courier'>docs/api-reference.txt</font>. "
            "Hosting: <font face='Courier'>docs/hosting.txt</font> / "
            "<font face='Courier'>infra/k8s-vke/RUNBOOK.txt</font>.",
            S["small"],
        ),
        Spacer(1, 0.3 * inch),
        Paragraph(
            f"© Salareen / AOEP — document generated from source at v{ver} on {today}. "
            "For internal product, engineering, and investor review.",
            S["caption"],
        ),
    ]

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(PDF_PATH), pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.65 * inch, bottomMargin=0.65 * inch,
        title=f"Salareen Platform Overview v{ver}",
        author="Salareen / AOEP",
    )
    doc.build(story)
    return PDF_PATH


def main() -> int:
    print("Rendering architecture diagrams…")
    diagrams = {
        "topology": arch.diagram_topology(),
        "network": arch.diagram_network(),
        "accounts": arch.diagram_accounts(),
        "data": arch.diagram_data(),
        "live_class": arch.diagram_live_class(),
        "deploy": arch.diagram_deploy(),
    }
    print("Preparing screenshots…")
    screens = _prep_screens()
    print(f"  {len(screens)} screens ready")
    # Also refresh the shorter architecture.pdf
    arch.build_pdf(diagrams)
    pdf = build_pdf(diagrams, screens)
    print(f"PDF: {pdf.relative_to(ROOT)} ({pdf.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
