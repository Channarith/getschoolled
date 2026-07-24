#!/usr/bin/env python3
"""Build Salareen / GetSchoolled strategic fundraising PDF.

Source of truth prose also lives in docs/fundraising-strategy.txt.
Usage:
  pip install reportlab==5.0.0 Pillow==11.1.0
  python3 scripts/build_fundraising_strategy_pdf.py
"""

from __future__ import annotations

import datetime
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
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

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "docs" / "fundraising-strategy.pdf"
TXT_PATH = ROOT / "docs" / "fundraising-strategy.txt"
SCREEN_CACHE = ROOT / "docs" / "diagrams" / "fundraising-screens"

NAVY = colors.HexColor("#0b1020")
GOLD = colors.HexColor("#C9A03C")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#f8fafc")


def _version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


def _styles():
    base = getSampleStyleSheet()
    return {
        "cover": ParagraphStyle(
            "cover", parent=base["Title"], fontSize=22, leading=28,
            textColor=NAVY, alignment=TA_CENTER, spaceAfter=6,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontSize=11, leading=15,
            textColor=MUTED, alignment=TA_CENTER, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=14, leading=18,
            textColor=NAVY, spaceBefore=2, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=11, leading=14,
            textColor=SLATE, spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontSize=9.2, leading=12.5,
            textColor=NAVY, alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "email": ParagraphStyle(
            "email", parent=base["Normal"], fontSize=9, leading=12.2,
            textColor=NAVY, alignment=TA_LEFT, spaceAfter=3,
            leftIndent=6, rightIndent=6,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=8, leading=10.5,
            textColor=MUTED, spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontSize=8, leading=10,
            textColor=MUTED, alignment=TA_CENTER, spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontSize=9, leading=12,
            textColor=NAVY,
        ),
        "subject": ParagraphStyle(
            "subject", parent=base["Normal"], fontSize=9.5, leading=12,
            textColor=NAVY, fontName="Helvetica-Bold", spaceAfter=6,
        ),
    }


def _bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(i, style), leftIndent=6, bulletColor=GOLD)
         for i in items],
        bulletType="bullet", start="•", leftIndent=12, spaceBefore=2, spaceAfter=6,
    )


def _table(rows, widths):
    tbl = Table(rows, colWidths=widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.4),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _prep_screens() -> dict[str, Path]:
    SCREEN_CACHE.mkdir(parents=True, exist_ok=True)
    mapping = {
        "ecosystem": ROOT / "docs" / "brand" / "salareen_platform_ecosystem.png",
        "homepage": ROOT / "docs" / "screens" / "homepage.webp",
        "drive": ROOT / "docs" / "screens" / "drive_mode_player.webp",
        "live": ROOT / "docs" / "screens" / "live_class_answer.webp",
        "corporate": ROOT / "docs" / "screens" / "corporate_programs.webp",
        "arcade": ROOT / "docs" / "screens" / "arcade_adult_quiz.webp",
    }
    out = {}
    for key, src in mapping.items():
        if not src.exists():
            continue
        dest = SCREEN_CACHE / f"{key}.png"
        im = Image.open(src).convert("RGB")
        w, h = im.size
        max_w = 1200
        if w > max_w:
            im = im.resize((max_w, int(h * max_w / w)), Image.Resampling.LANCZOS)
        im.save(dest, "PNG", optimize=True)
        out[key] = dest
    return out


def _img(path: Path, max_w=6.4 * inch, max_h=3.2 * inch):
    im = Image.open(path)
    w, h = im.size
    aspect = h / float(w)
    width = max_w
    height = width * aspect
    if height > max_h:
        height = max_h
        width = height / aspect
    return RLImage(str(path), width=width, height=height)


def write_txt_source(ver: str, today: str) -> None:
    """Plain-text companion (repo convention: docs/*.txt)."""
    TXT_PATH.write_text(f"""SALAREEN STRATEGIC FUNDRAISING DOCUMENT
=======================================
Document Version 1.0  |  Platform build v{ver}  |  Confidential  |  {today}
Brand: Salareen (product) · GetSchoolled (ecosystem / org surface)

This file is the editable source. Rendered PDF:
  docs/fundraising-strategy.pdf
  python3 scripts/build_fundraising_strategy_pdf.py

LEGAL / HONESTY NOTE
--------------------
Revenue figures, SAFE terms, and valuation caps in this document are fundraising
assumptions provided by the founding team for outreach drafts. Have counsel
review SAFE terms before sending. Product/tech claims below are grounded in the
shipped monorepo (FastAPI microservices, Next.js, Expo, LiveKit, VKE).

-----------------------------------------------------------------------------
1. INVESTOR COLD EMAIL TEMPLATE
-----------------------------------------------------------------------------
Subject: Seed Stage: Multi-Agent AI EdTech ($1M+ Run-Rate) / 60-Day Deployment Runway

Dear [Partner Name],

Salareen is an enterprise-grade, multi-agent AI education platform running live
on Kubernetes (Vultr VKE) with 600+ self-paced courses localized across 27
languages. We are currently generating early seven-figure revenues through
custom B2B corporate compliance tracks (OSHA/DMV) and instructor marketplace
commissions.

We have built 60% of our core consumer "Netflix-style" subscription engine. We
are raising a Seed round via a SAFE note to secure a 60-day deployment runway
to finalize feature qualification, complete comprehensive QA, and fund our Q3
marketing launch.

Why Salareen Wins:
• Proprietary AI Tutor: Powered by our socratic AI agent (Theodore) utilizing an
  LLM endpoint abstraction (NVIDIA Nemotron/GPT-4o).
• Machine Vision Safeguards: Built-in opt-in computer vision microservice
  (OpenCV YuNet/SFace) tracking student attention and securing anti-cheating
  classroom authentication.
• Adaptive Learning Engine: Real-time Bayesian Knowledge Tracing (BKT) that
  automatically profiles student engagement and scales difficulty dynamically.
• Gamified Ecosystem: Includes a 3D open-world educational RPG (Salareen Worlds)
  built on Three.js to maximize student retention.

We are giving select EdTech and AI investors a technical look at our deployment
pipeline before our subscription layers go live. Are you open to a brief
10-minute call next Tuesday to look at our live architecture and feature
roadmap?

Best regards,

[Your Name]
Founder & CEO, Salareen
cvanthin@nvidia.com
https://salareen.com

-----------------------------------------------------------------------------
2. PITCH DECK STRUCTURAL OUTLINE (4-SLIDE INVESTOR BRIEF)
-----------------------------------------------------------------------------
Slide 1 — Vision & Traction
  Heading: Scaling World-Class AI Education Globally
  Metrics: 600+ live courses, 27 languages, 40+ global payment methods
  Visual: Interactive global map / localization

Slide 2 — The Multi-Engine Business Model
  Heading: Diversified Monetization Beyond Traditional SaaS
  Pillars: B2B enterprise tracks, B2C subscriptions, marketplace commissions,
           RPG / arcade gamification
  Visual: Cash-flow matrix

Slide 3 — Proprietary Technology Moat
  Heading: Production-Grade Microservices Architecture
  Core: Orchestrator, Perception (YuNet), Memory (BKT), Billing, Identity on K8s
  Visual: FastAPI service topology

Slide 4 — The 60-Day Deployment Phase (The Ask)
  Heading: Subscription Engine Final QA & Launch
  Use of funds: engineering payroll + targeted customer acquisition
  Visual: 60-day sprint timeline

-----------------------------------------------------------------------------
3. MARKET WINDOW & READINESS
-----------------------------------------------------------------------------
• Valuation leverage before full consumer subscription go-live
• Asset density: core stack, harvester, live rooms, Drive Mode already functional
• De-risked path: active B2B enterprise revenue reduces early downside
• SAFE instrument avoids premature priced round during QA
• 60-day engineering firewall for feature qualification + launch marketing

-----------------------------------------------------------------------------
4. INVESTOR DIRECTORY
-----------------------------------------------------------------------------
Pure-Play EdTech VCs     Reach / Owl / GSV           $500K–$3M
Applied AI & Deep Tech   Gradient / Precursor / Two Sigma  $250K–$1.5M
Non-Dilutive             Lighter / Capchase / Pipe   $100K–$2M (revenue-backed)

-----------------------------------------------------------------------------
5. SAFE NOTE VALUATION CAP FRAMEWORK
-----------------------------------------------------------------------------
Assumptions:
  Current run-rate: $1,000,000+ via B2B contracts
  Round size: $500,000–$1,000,000 (60-day runway)
  Cap range: $8M floor · $12M target · $15M upper (if backlog > $1.5M)

Dilution at $12M cap:
  $500K raise ≈ 4.17%
  $1M raise ≈ 8.33%

-----------------------------------------------------------------------------
6. GETSCHOOLLED / SALAREEN ECOSYSTEM (PRODUCT MAP)
-----------------------------------------------------------------------------
Live AI classes (Theodore) · Group / solo LiveKit rooms · Drive Mode audio
Corporate professional tracks · Arcade + Challenge the AI · Salareen Worlds
Languages (27) · Kids Academy · Careers/jobs match · Homework grader
HIL educator console · Rewards · Billing (Free/Standard/VIP) · Harvester
Perception (opt-in vision) · Adaptive/BKT · Content packs · VKE deploy

Rebuild PDF: python3 scripts/build_fundraising_strategy_pdf.py
""", encoding="utf-8")


def build_pdf(screens: dict[str, Path]) -> Path:
    S = _styles()
    ver = _version()
    today = datetime.date.today().strftime("%B %Y")
    today_iso = datetime.date.today().isoformat()
    write_txt_source(ver, today_iso)

    story = []

    # Cover
    story += [
        Spacer(1, 0.45 * inch),
        Paragraph("Salareen Strategic Fundraising Document", S["cover"]),
        Paragraph("GetSchoolled Ecosystem · Seed Outreach Pack", S["cover_sub"]),
        Paragraph(
            f"Document Version 1.0 &nbsp;·&nbsp; Confidential &nbsp;·&nbsp; {today}"
            f" &nbsp;·&nbsp; Platform build v{ver}",
            S["cover_sub"],
        ),
        HRFlowable(width="100%", thickness=1.2, color=GOLD, spaceBefore=8, spaceAfter=12),
    ]
    if "ecosystem" in screens:
        story += [
            _img(screens["ecosystem"], max_h=3.6 * inch),
            Paragraph("Salareen / GetSchoolled platform ecosystem", S["caption"]),
        ]
    story += [
        Paragraph(
            "This pack is for select EdTech and applied-AI investors. It includes a "
            "ready-to-send cold email, a four-slide brief outline, market-window framing, "
            "an investor directory, and a SAFE valuation-cap framework — aligned to the "
            "live Salareen product running on Vultr Kubernetes (VKE).",
            S["body"],
        ),
        Paragraph(
            "<b>Confidential.</b> Revenue, SAFE, and valuation figures are fundraising "
            "assumptions for outreach drafts and require counsel review before use.",
            S["small"],
        ),
        PageBreak(),
    ]

    # 1 Cold email
    story += [
        Paragraph("1. Investor Cold Email Template", S["h1"]),
        Paragraph(
            "Subject: Seed Stage: Multi-Agent AI EdTech ($1M+ Run-Rate) / 60-Day Deployment Runway",
            S["subject"],
        ),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=8),
        Paragraph("Dear [Partner Name],", S["email"]),
        Spacer(1, 4),
        Paragraph(
            "Salareen is an enterprise-grade, multi-agent AI education platform running live "
            "on Kubernetes (Vultr VKE) with 600+ self-paced courses localized across 27 languages. "
            "We are currently generating early seven-figure revenues through custom B2B corporate "
            "compliance tracks (OSHA/DMV) and instructor marketplace commissions.",
            S["email"],
        ),
        Spacer(1, 4),
        Paragraph(
            "We have built 60% of our core consumer \"Netflix-style\" subscription engine. We are "
            "raising a Seed round via a SAFE note to secure a 60-day deployment runway to finalize "
            "feature qualification, complete comprehensive QA, and fund our Q3 marketing launch.",
            S["email"],
        ),
        Spacer(1, 4),
        Paragraph("<b>Why Salareen Wins:</b>", S["email"]),
        _bullets([
            "<b>Proprietary AI Tutor:</b> Powered by our socratic AI agent (Theodore) utilizing an "
            "LLM endpoint abstraction (NVIDIA Nemotron/GPT-4o).",
            "<b>Machine Vision Safeguards:</b> Built-in opt-in computer vision microservice "
            "(OpenCV YuNet/SFace) tracking student attention and securing anti-cheating "
            "classroom authentication.",
            "<b>Adaptive Learning Engine:</b> Real-time Bayesian Knowledge Tracing (BKT) that "
            "automatically profiles student engagement and scales difficulty dynamically.",
            "<b>Gamified Ecosystem:</b> Includes a 3D open-world educational RPG (Salareen Worlds) "
            "built on Three.js to maximize student retention.",
        ], S["bullet"]),
        Paragraph(
            "We are giving select EdTech and AI investors a technical look at our deployment "
            "pipeline before our subscription layers go live. Are you open to a brief 10-minute "
            "call next Tuesday to look at our live architecture and feature roadmap?",
            S["email"],
        ),
        Spacer(1, 6),
        Paragraph("Best regards,", S["email"]),
        Spacer(1, 4),
        Paragraph("[Your Name]<br/>Founder &amp; CEO, Salareen<br/>"
                  "cvanthin@nvidia.com<br/>https://salareen.com", S["email"]),
        PageBreak(),
    ]

    # 2 Pitch deck
    story += [
        Paragraph("2. Pitch Deck Structural Outline", S["h1"]),
        Paragraph(
            "A tight four-slide investor brief for the 10-minute technical call. Pair with the "
            "longer 12-slide narrative in <font face='Courier'>docs/pitch/</font> when deeper "
            "storytelling is required.",
            S["body"],
        ),
        Paragraph("Slide 1: Vision &amp; Traction", S["h2"]),
        _bullets([
            "<b>Heading:</b> Scaling World-Class AI Education Globally",
            "<b>Core metrics:</b> 600+ live courses, 27 languages, and 40+ global payment methods",
            "<b>Visual focus:</b> Interactive global map highlighting multi-language localization",
        ], S["bullet"]),
        Paragraph("Slide 2: The Multi-Engine Business Model", S["h2"]),
        _bullets([
            "<b>Heading:</b> Diversified Monetization Beyond Traditional SaaS",
            "<b>Key pillars:</b> B2B Enterprise Tracks, B2C Subscriptions, Marketplace Commissions, "
            "and RPG / Arcade Gamification",
            "<b>Visual focus:</b> Matrix diagram mapping enterprise cash flows to platform stability",
        ], S["bullet"]),
        Paragraph("Slide 3: Proprietary Technology Moat", S["h2"]),
        _bullets([
            "<b>Heading:</b> Production-Grade Microservices Architecture",
            "<b>Deep tech core:</b> Separate Kubernetes services for Orchestration, Perception "
            "(YuNet tracking), Memory (BKT models), Identity, Billing, Curriculum, Speech",
            "<b>Visual focus:</b> Technical architecture block diagram showing async FastAPI endpoints",
        ], S["bullet"]),
        Paragraph("Slide 4: The 60-Day Deployment Phase (The Ask)", S["h2"]),
        _bullets([
            "<b>Heading:</b> Milestone Target — Subscription Engine Final QA &amp; Launch",
            "<b>Strategic use of funds:</b> 100% allocated to engineering payroll and targeted "
            "customer acquisition",
            "<b>Visual focus:</b> Timeline layout detailing the 60-day engineering sprint to public launch",
        ], S["bullet"]),
        PageBreak(),
    ]

    # 3 Market window
    story += [
        Paragraph("3. Market Window &amp; Readiness Analysis", S["h1"]),
        Paragraph("Strategic Entry Window", S["h2"]),
        _bullets([
            "<b>Valuation leverage:</b> Investors get a lower entry point before subscriptions go live",
            "<b>Asset density:</b> Core tech stack, content harvester, LiveKit rooms, Drive Mode, "
            "and base code are fully functional on VKE",
            "<b>De-risked metrics:</b> Active B2B enterprise revenue minimizes early operational downside",
        ], S["bullet"]),
        Paragraph("Feature Gap Management", S["h2"]),
        _bullets([
            "<b>SAFE instrument:</b> Prevents premature down-rounds during QA phases",
            "<b>Development buffer:</b> Funding builds a 60-day engineering firewall for feature testing",
            "<b>Core validation:</b> Custom compliance modules prove the platform's stability under load",
        ], S["bullet"]),
        Paragraph("GetSchoolled Ecosystem Snapshot (shipped)", S["h2"]),
        _bullets([
            "Live AI classes with Theodore + grounded Ask · Group/solo LiveKit rooms",
            "Drive Mode audio · Corporate professional tracks with verified assessments",
            "Arcade + Challenge the AI · Salareen Worlds (Three.js) · Languages (27)",
            "Kids Academy · Careers match · Homework grader · HIL educator console",
            "Rewards · Free / Standard ($19.99) / VIP ($29.99) · Global payment routing",
            "Harvester → catalog · Opt-in vision (YuNet/SFace) · Adaptive / BKT engines",
        ], S["bullet"]),
    ]
    if "homepage" in screens:
        story += [
            _img(screens["homepage"], max_h=2.8 * inch),
            Paragraph("Netflix-style consumer home (subscription engine surface)", S["caption"]),
        ]
    story.append(PageBreak())

    # Product proof screens
    story += [Paragraph("3b. Product Proof Points (for the 10-minute call)", S["h1"])]
    for key, cap in [
        ("live", "Live AI class — Theodore + grounded answers"),
        ("drive", "Drive Mode — hands-free audio learning"),
        ("corporate", "Corporate / professional training funnel"),
        ("arcade", "Learning Arcade — retention &amp; engagement"),
    ]:
        if key in screens:
            story.append(KeepTogether([
                _img(screens[key], max_h=2.55 * inch),
                Paragraph(cap, S["caption"]),
            ]))
    story.append(PageBreak())

    # 4 Investor directory
    story += [
        Paragraph("4. Comprehensive Investor Directory", S["h1"]),
        _table([
            ["Investor Group", "Target Firms", "Core Thesis / Alignment", "Check Size"],
            [
                Paragraph("<b>Pure-Play EdTech VCs</b>", S["small"]),
                Paragraph("Reach Capital<br/>Owl Ventures<br/>GSV Ventures", S["small"]),
                Paragraph(
                    "Global workforce learning and deep gamified student retention frameworks.",
                    S["small"],
                ),
                Paragraph("$500,000 to $3,000,000", S["small"]),
            ],
            [
                Paragraph("<b>Applied AI &amp; Deep Tech</b>", S["small"]),
                Paragraph("Gradient Ventures<br/>Precursor Ventures<br/>Two Sigma Ventures", S["small"]),
                Paragraph(
                    "Scalable multi-agent frameworks, computer vision, and offline edge capabilities.",
                    S["small"],
                ),
                Paragraph("$250,000 to $1,500,000", S["small"]),
            ],
            [
                Paragraph("<b>Non-Dilutive Capital</b>", S["small"]),
                Paragraph("Lighter Capital<br/>Capchase<br/>Pipe", S["small"]),
                Paragraph(
                    "Rapid non-equity advances secured by live B2B revenue contracts.",
                    S["small"],
                ),
                Paragraph("$100,000 to $2,000,000", S["small"]),
            ],
        ], [1.35 * inch, 1.55 * inch, 2.35 * inch, 1.35 * inch]),
        Spacer(1, 0.15 * inch),
        Paragraph(
            "Outreach tip: lead EdTech firms with retention + B2B compliance traction; lead AI firms "
            "with Theodore, perception, BKT, and the VKE multi-agent architecture; lead revenue-based "
            "financiers with contracted B2B run-rate and payment history.",
            S["body"],
        ),
        PageBreak(),
    ]

    # 5 SAFE
    story += [
        Paragraph("5. SAFE Note Valuation Cap Framework", S["h1"]),
        Paragraph("Financial Assumptions", S["h2"]),
        _bullets([
            "<b>Current run-rate:</b> $1,000,000+ via B2B contracts",
            "<b>Tech multiplier:</b> Premium for proprietary multi-agent architecture and "
            "27-language infrastructure",
            "<b>Round size target:</b> $500,000 to $1,000,000 for 60-day runway",
        ], S["bullet"]),
        Paragraph("Recommended Valuation Cap Range", S["h2"]),
        _table([
            ["Bound", "Cap", "Rationale"],
            ["Lower", "$8,000,000", "Floor mapping to typical ~8x SaaS enterprise multiples"],
            ["Target", "$12,000,000", "Mid-market sweet spot: AI moat + deployment readiness"],
            ["Upper", "$15,000,000", "Premium if active B2B backlog exceeds $1.5M"],
        ], [1.2 * inch, 1.4 * inch, 4.0 * inch]),
        Spacer(1, 0.12 * inch),
        Paragraph("Investor Dilution (at $12M Valuation Cap)", S["h2"]),
        _bullets([
            "<b>Scenario A ($500K raise):</b> ≈ 4.17% post-round investor ownership via SAFE cap math",
            "<b>Scenario B ($1M raise):</b> ≈ 8.33% post-round investor ownership via SAFE cap math",
        ], S["bullet"]),
        Paragraph(
            "Note: Actual ownership depends on SAFE discount, MFN, and future priced-round terms. "
            "Have counsel finalize instrument language before circulating.",
            S["small"],
        ),
        Paragraph("60-Day Use of Proceeds (illustrative)", S["h2"]),
        _table([
            ["Workstream", "Allocation", "Outcome"],
            ["Engineering payroll / QA", "~70%", "Subscription engine feature qualification + load QA"],
            ["Customer acquisition", "~30%", "Q3 marketing launch + B2B pipeline acceleration"],
        ], [2.2 * inch, 1.2 * inch, 3.2 * inch]),
        PageBreak(),
    ]

    # Closing CTA
    story += [
        Paragraph("6. Call-to-Action Script (for the Tuesday meeting)", S["h1"]),
        _bullets([
            "Minute 0–2: Live architecture walkthrough (VKE + services + Theodore class)",
            "Minute 2–5: Product demo path — Drive Mode → Corporate assessment → Arcade/Worlds",
            "Minute 5–8: Business model + B2B run-rate narrative + subscription go-live gap",
            "Minute 8–10: SAFE ask ($500K–$1M / $12M target cap) and next diligence step",
        ], S["bullet"]),
        Paragraph("Related materials in-repo", S["h2"]),
        Paragraph(
            "<font face='Courier'>docs/fundraising-strategy.txt</font> (this source) · "
            "<font face='Courier'>docs/fundraising-strategy.pdf</font> · "
            "<font face='Courier'>docs/platform-overview.pdf</font> · "
            "<font face='Courier'>docs/architecture.pdf</font> · "
            "<font face='Courier'>docs/pitch/</font> (12-slide long-form deck) · "
            "<font face='Courier'>https://salareen.com</font>",
            S["small"],
        ),
        Spacer(1, 0.35 * inch),
        HRFlowable(width="100%", thickness=1.0, color=GOLD, spaceBefore=4, spaceAfter=10),
        Paragraph(
            f"© Salareen / GetSchoolled — Confidential fundraising pack v1.0 "
            f"(platform v{ver}, generated {today_iso}).",
            S["caption"],
        ),
    ]

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(PDF_PATH), pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title="Salareen Strategic Fundraising Document",
        author="Salareen / GetSchoolled",
    )
    doc.build(story)
    return PDF_PATH


def main() -> int:
    screens = _prep_screens()
    pdf = build_pdf(screens)
    print(f"TXT: {TXT_PATH.relative_to(ROOT)}")
    print(f"PDF: {pdf.relative_to(ROOT)} ({pdf.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
