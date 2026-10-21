"""Paid-learning topic backlog.

People pay for career, certification, and trade skills. This catalog crosses
those domains with a focus, a study method, an audience, and a goal so the
harvester can queue more than a million distinct topics without calling a
search API once per topic.

A topic is a search-shaped phrase, for example
``cybersecurity: threat detection certification prep for job seekers to pass a certification``.
The crawl claims a few at a time and turns each into open-catalog seed URLs.
"""

from __future__ import annotations

from typing import Iterator
from urllib.parse import quote

from .sources import SourceSpec

# Study shapes that stay meaningful across career, cert, and trade topics.
_METHODS: tuple[str, ...] = (
    "fundamentals",
    "hands-on labs",
    "practice exams",
    "case studies",
    "a project portfolio",
    "interview questions",
    "certification prep",
    "a capstone",
)

_AUDIENCES: tuple[str, ...] = (
    "beginners",
    "career changers",
    "working professionals",
    "managers",
    "job seekers",
    "college students",
    "freelancers",
    "small business owners",
    "team leads",
    "analysts",
    "engineers",
    "consultants",
    "executives",
    "recent graduates",
    "career switchers",
    "independent learners",
)

_GOALS: tuple[str, ...] = (
    "pass a certification",
    "get hired",
    "earn a promotion",
    "start freelancing",
    "switch careers",
    "build a portfolio",
    "prepare for interviews",
    "run a small business",
    "lead a team",
    "meet compliance requirements",
    "raise earning power",
    "teach the skill",
    "finish a bootcamp",
    "refresh rusty skills",
)

# Eight focuses each. The domain name is part of every topic, so focuses may
# repeat across domains without colliding.
_DOMAINS: dict[str, tuple[str, ...]] = {
    "generative AI": (
        "prompt design", "retrieval augmented generation", "tool use", "evaluation",
        "fine tuning", "safety", "multimodal models", "agent workflows",
    ),
    "python programming": (
        "syntax", "functions", "files", "APIs", "testing", "packaging",
        "automation", "data structures",
    ),
    "AWS cloud": (
        "IAM", "EC2", "S3", "VPC", "Lambda", "RDS", "CloudWatch", "cost control",
    ),
    "Azure cloud": (
        "Entra ID", "virtual machines", "storage accounts", "virtual networks",
        "functions", "Azure SQL", "Monitor", "cost management",
    ),
    "Google Cloud": (
        "IAM", "Compute Engine", "Cloud Storage", "VPC", "Cloud Functions",
        "BigQuery", "Cloud Monitoring", "billing",
    ),
    "cybersecurity": (
        "threat detection", "vulnerability management", "identity security",
        "incident response", "security operations", "risk assessment",
        "endpoint protection", "security awareness",
    ),
    "data analytics": (
        "data cleaning", "dashboards", "spreadsheets", "statistics",
        "storytelling", "SQL queries", "sampling", "stakeholder reporting",
    ),
    "SQL": (
        "SELECT queries", "joins", "aggregations", "indexes", "window functions",
        "data modeling", "query tuning", "transactions",
    ),
    "Excel": (
        "formulas", "pivot tables", "charts", "Power Query", "data validation",
        "dashboards", "macros", "financial models",
    ),
    "machine learning": (
        "supervised learning", "model evaluation", "feature engineering",
        "regression", "classification", "clustering", "scikit-learn",
        "model deployment",
    ),
    "web development": (
        "HTML", "CSS", "JavaScript", "accessibility", "forms", "APIs",
        "responsive layout", "deployment",
    ),
    "project management": (
        "scope", "schedules", "budgets", "risk", "stakeholders",
        "agile delivery", "status reporting", "project closure",
    ),
    "digital marketing": (
        "audience research", "content planning", "email campaigns", "analytics",
        "conversion", "social channels", "branding", "campaign measurement",
    ),
    "personal finance": (
        "budgeting", "debt payoff", "emergency funds", "credit scores",
        "retirement accounts", "insurance", "taxes", "net worth",
    ),
    "investing": (
        "index funds", "ETFs", "asset allocation", "retirement accounts",
        "risk tolerance", "brokerage accounts", "compounding",
        "portfolio rebalancing",
    ),
    "DevOps": (
        "CI pipelines", "containers", "infrastructure as code", "monitoring",
        "release management", "Linux servers", "incident handoffs",
        "configuration management",
    ),
    "Kubernetes": (
        "pods", "deployments", "services", "ingress", "config maps",
        "Helm charts", "cluster security", "troubleshooting",
    ),
    "data engineering": (
        "pipelines", "warehouses", "orchestration", "data quality", "batch jobs",
        "streaming", "schemas", "lakehouse storage",
    ),
    "product management": (
        "discovery", "roadmaps", "user stories", "prioritization", "metrics",
        "stakeholder alignment", "launch plans", "experiments",
    ),
    "UX design": (
        "user research", "wireframes", "prototypes", "usability tests",
        "information architecture", "design systems", "accessibility",
        "interaction design",
    ),
    "leadership": (
        "feedback", "coaching", "delegation", "one on ones", "conflict",
        "hiring", "performance reviews", "team goals",
    ),
    "accounting": (
        "debits and credits", "financial statements", "accruals",
        "reconciliation", "accounts payable", "accounts receivable",
        "payroll basics", "month end close",
    ),
    "nursing": (
        "vital signs", "medication safety", "patient assessment", "care plans",
        "infection control", "documentation", "clinical judgment",
        "patient education",
    ),
    "real estate": (
        "property valuation", "financing", "contracts", "fair housing",
        "listings", "buyer representation", "inspections", "closing",
    ),
    "English communication": (
        "pronunciation", "business writing", "presentations", "meetings",
        "email tone", "vocabulary", "listening", "interviews",
    ),
    "Spanish": (
        "greetings", "travel phrases", "grammar", "workplace Spanish",
        "listening", "conversation", "reading", "writing",
    ),
    "public speaking": (
        "speech structure", "storytelling", "slides", "vocal delivery",
        "handling questions", "nervousness", "persuasive talks",
        "audience analysis",
    ),
    "Salesforce": (
        "objects", "reports", "dashboards", "flows", "security", "data import",
        "Service Cloud", "the sales process",
    ),
    "Power BI": (
        "data models", "DAX", "visuals", "Power Query", "dashboards",
        "row level security", "refresh", "storytelling",
    ),
    "Linux administration": (
        "the shell", "users and permissions", "systemd", "networking", "disks",
        "logs", "SSH", "package management",
    ),
    "network security": (
        "firewalls", "VPNs", "segmentation", "intrusion detection",
        "secure protocols", "wireless security", "access control",
        "packet analysis",
    ),
    "ethical hacking": (
        "reconnaissance", "scanning", "exploitation basics", "web app testing",
        "reporting", "privilege boundaries", "password safety", "legal scope",
    ),
    "incident response": (
        "detection", "containment", "eradication", "recovery",
        "evidence handling", "playbooks", "communication", "lessons learned",
    ),
    "CompTIA": (
        "hardware", "operating systems", "networking", "security controls",
        "troubleshooting", "operational procedures", "ports and protocols",
        "exam strategy",
    ),
    "PMP certification": (
        "process groups", "knowledge areas", "earned value",
        "stakeholder engagement", "agile hybrid delivery", "the risk register",
        "change control", "exam formulas",
    ),
    "agile and scrum": (
        "sprints", "backlogs", "standups", "retrospectives", "story points",
        "product ownership", "kanban", "release planning",
    ),
    "SEO": (
        "keyword research", "on page SEO", "technical SEO", "links",
        "search intent", "content briefs", "analytics", "local SEO",
    ),
    "Google Ads": (
        "search campaigns", "keywords", "ad copy", "bidding",
        "conversion tracking", "quality score", "budgets", "reporting",
    ),
    "email marketing": (
        "list building", "segmentation", "subject lines", "automation",
        "deliverability", "compliance", "templates", "campaign tests",
    ),
    "copywriting": (
        "headlines", "offers", "landing pages", "calls to action",
        "brand voice", "editing", "sales pages", "email sequences",
    ),
    "financial modeling": (
        "three statement models", "forecasts", "valuation", "scenarios",
        "Excel structure", "unit economics", "sensitivity", "presentation",
    ),
    "statistics": (
        "descriptive stats", "probability", "hypothesis tests", "regression",
        "sampling", "confidence intervals", "data visualization",
        "experiment design",
    ),
    "data science": (
        "exploratory analysis", "pandas workflows", "model selection",
        "communication", "reproducibility", "notebooks", "ethics",
        "business questions",
    ),
    "LLM engineering": (
        "prompting", "retrieval", "evaluation", "tool calling", "embeddings",
        "context windows", "latency", "safety filters",
    ),
    "RAG systems": (
        "chunking", "embeddings", "vector search", "citations",
        "evaluation sets", "reranking", "document ingestion",
        "failure analysis",
    ),
    "MLOps": (
        "the model registry", "training pipelines", "drift monitoring",
        "deployment", "feature stores", "reproducibility", "rollback",
        "cost tracking",
    ),
    "Terraform": (
        "providers", "state", "modules", "variables", "plans",
        "remote backends", "drift", "policy",
    ),
    "Docker": (
        "images", "containers", "Dockerfiles", "volumes", "networks",
        "Compose", "registries", "security scanning",
    ),
    "mobile development": (
        "layouts", "navigation", "local storage", "APIs", "app store release",
        "accessibility", "offline behavior", "testing",
    ),
    "JavaScript": (
        "variables", "functions", "the DOM", "async code", "modules",
        "errors", "fetch", "testing",
    ),
    "React": (
        "components", "state", "props", "hooks", "forms", "routing",
        "data fetching", "testing",
    ),
    "Tableau": (
        "connections", "worksheets", "dashboards", "calculations", "filters",
        "maps", "stories", "publishing",
    ),
    "human resources": (
        "recruiting", "interviewing", "onboarding", "employee relations",
        "compensation basics", "policy", "performance", "compliance",
    ),
    "sales": (
        "discovery calls", "qualification", "demos", "objections", "pipeline",
        "forecasting", "negotiation", "follow up",
    ),
    "customer success": (
        "onboarding", "health scores", "renewals", "QBRs", "adoption",
        "escalation", "playbooks", "feedback",
    ),
    "supply chain": (
        "demand planning", "inventory", "procurement", "logistics",
        "suppliers", "lead times", "risk", "cost",
    ),
    "business analysis": (
        "requirements", "process maps", "user stories", "stakeholders",
        "gap analysis", "acceptance criteria", "workshops", "documentation",
    ),
    "bookkeeping": (
        "the chart of accounts", "invoices", "bills", "bank reconciliation",
        "sales tax", "payroll entries", "reports", "software setup",
    ),
    "entrepreneurship": (
        "offers", "customers", "pricing", "validation", "operations",
        "cash flow", "hiring", "go to market",
    ),
    "graphic design": (
        "layout", "typography", "color", "branding", "image editing",
        "export formats", "critique", "client briefs",
    ),
    "photography": (
        "exposure", "composition", "lighting", "editing", "portraits",
        "product photos", "file management", "client delivery",
    ),
    "video editing": (
        "cuts", "audio", "color", "titles", "pacing", "export settings",
        "b roll", "storytelling",
    ),
    "nutrition coaching": (
        "energy balance", "protein", "meal planning", "behavior change",
        "hydration", "label reading", "client check ins", "scope of practice",
    ),
    "electrical trade": (
        "circuits", "code basics", "safety", "wiring methods",
        "troubleshooting", "blueprints", "tools", "test equipment",
    ),
    "HVAC": (
        "the refrigeration cycle", "airflow", "electrical safety",
        "installation", "maintenance", "diagnostics", "customer explanations",
        "code basics",
    ),
    "welding": (
        "joint prep", "processes", "safety", "blueprint symbols", "defects",
        "positions", "inspection", "machine setup",
    ),
    "CDL and driving": (
        "vehicle inspection", "hours of service", "backing", "coupling",
        "road signs", "cargo securement", "trip planning", "safety",
    ),
    "medical coding": (
        "ICD codes", "CPT codes", "modifiers", "claim forms", "documentation",
        "compliance", "anatomy terms", "denial follow up",
    ),
    "pharmacology": (
        "drug classes", "dosage calculation", "side effects",
        "administration routes", "interactions", "patient teaching",
        "safety checks", "abbreviations",
    ),
    "privacy and compliance": (
        "data inventories", "consent", "retention", "vendor risk",
        "incident notice", "policies", "access reviews", "training records",
    ),
    "Six Sigma": (
        "DMAIC", "process mapping", "variation", "control charts",
        "root cause", "voice of the customer", "project charters",
        "sustainment",
    ),
    "negotiation": (
        "preparation", "interests", "offers", "concessions", "deadlines",
        "difficult counterparts", "written agreements", "salary talks",
    ),
    "cloud security": (
        "identity", "encryption", "logging", "network controls",
        "shared responsibility", "misconfiguration", "incident response",
        "compliance",
    ),
    "information security": (
        "policies", "access control", "asset inventory", "awareness",
        "vulnerability intake", "backup", "third parties", "metrics",
    ),
    "English for work": (
        "meetings", "presentations", "email", "small talk", "phone calls",
        "interviews", "reports", "clarification",
    ),
    "investing for retirement": (
        "401k accounts", "IRA accounts", "target date funds",
        "contribution limits", "employer match", "withdrawal rules", "fees",
        "allocation",
    ),
    "SQL for analysts": (
        "SELECT", "JOIN", "GROUP BY", "subqueries", "CTEs", "date functions",
        "data quality checks", "dashboard extracts",
    ),
    "python automation": (
        "scripts", "spreadsheets", "files", "email", "APIs", "scheduling",
        "logging", "error handling",
    ),
    "web accessibility": (
        "semantic HTML", "keyboard access", "contrast", "screen readers",
        "forms", "ARIA", "testing", "remediation",
    ),
    "product analytics": (
        "events", "funnels", "retention", "cohorts", "experimentation",
        "dashboards", "definitions", "stakeholder reviews",
    ),
}


def paid_topic_count() -> int:
    """How many distinct topics the catalog can yield."""
    bad = [name for name, focuses in _DOMAINS.items() if len(focuses) != 8]
    if bad:
        raise RuntimeError(f"each domain needs 8 focuses, fix: {bad}")
    return (
        len(_DOMAINS) * 8 * len(_METHODS) * len(_AUDIENCES) * len(_GOALS)
    )


def iter_paid_topics() -> Iterator[str]:
    """Yield every paid-learning topic in a stable order."""
    for domain, focuses in _DOMAINS.items():
        for focus in focuses:
            for method in _METHODS:
                for audience in _AUDIENCES:
                    for goal in _GOALS:
                        yield (
                            f"{domain}: {focus} {method} for {audience} to {goal}"
                        )


def open_seed_specs(topic: str) -> list[SourceSpec]:
    """Open-catalog pages for one backlog topic. No search-API call."""
    q = quote(topic)
    subject = topic.split(":", 1)[0][:64]
    title = topic[:180]
    rows = (
        (
            f"https://archive.org/search?query={q}",
            "public-domain",
            "Internet Archive",
        ),
        (
            f"https://en.wikibooks.org/w/index.php?search={q}",
            "cc-by-sa",
            "Wikibooks",
        ),
        (
            f"https://www.oercommons.org/search?f.search={q}",
            "cc-by",
            "OER Commons",
        ),
    )
    return [
        SourceSpec(
            url=url,
            license=license,
            subject=subject,
            title=f"{title} — {label}",
            source_type="html",
            meta={"topic": topic, "kind": "topic-backlog", "priority": 10},
        )
        for url, license, label in rows
    ]


def fill_topic_backlog(store, *, limit: int = 0, progress=None) -> int:
    """Insert catalog topics into ``store``. ``limit`` 0 inserts the full catalog."""
    return store.enqueue_topics(iter_paid_topics(), limit=limit, progress=progress)
