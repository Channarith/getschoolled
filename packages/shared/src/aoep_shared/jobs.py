"""Jobs <-> skills <-> courses: link classes to real job openings.

Connects the catalog to the job market so students can see "take these courses to
qualify for this role." A ``JobsProvider`` abstracts the source of openings
(LinkedIn / Indeed / etc.); offline we use a curated, representative job board
(``MockJobsProvider``). Real providers are env-keyed and wired behind the same
interface. The matcher maps a job's required skills onto catalog courses,
computing coverage %, the skill gap, and a recommended learning path.

Pure/offline + stdlib + pydantic. The curriculum service exposes it over HTTP
(it owns the course catalog used for matching).
"""

from __future__ import annotations

import abc
import os
import re
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

_STOP = {"the", "a", "an", "to", "of", "for", "and", "with", "in", "on", "intro",
         "introduction", "basics", "essentials", "101", "audio", "fundamentals",
         "foundations", "your", "how", "what", "is", "works"}


class JobPosting(BaseModel):
    id: str
    title: str
    company: str
    location: str = "Remote"
    source: str = "sample"          # linkedin | indeed | sample | ...
    url: str = ""
    employment_type: str = "Full-time"
    salary_range: str = ""
    posted_days_ago: int = 0
    category: str = ""
    skills: List[str] = Field(default_factory=list)        # required (tokens)
    nice_to_have: List[str] = Field(default_factory=list)
    description: str = ""


def pretty_skill(s: str) -> str:
    return s.replace("-", " ").title()


# Map a required skill token to the set of tokens that, if found in a course,
# indicate the course teaches it (skill itself + components + synonyms).
SKILL_SYNONYMS: Dict[str, set] = {
    "python": {"python", "coding", "programming"},
    "sql": {"sql", "database", "data"},
    "data-analysis": {"data", "analysis", "analytics", "sql", "statistics"},
    "statistics": {"statistics", "stats", "math", "probability"},
    "machine-learning": {"machine", "learning", "ml", "ai", "python"},
    "cloud": {"cloud", "aws", "azure", "devops"},
    "devops": {"devops", "cloud", "docker", "ci", "linux"},
    "linux": {"linux", "shell", "unix"},
    "git": {"git", "version", "github"},
    "excel": {"excel", "spreadsheets", "spreadsheet"},
    "finance": {"finance", "financial", "accounting", "investing"},
    "accounting": {"accounting", "bookkeeping", "finance"},
    "marketing": {"marketing", "seo", "content", "growth"},
    "seo": {"seo", "search", "marketing"},
    "design": {"design", "ux", "ui", "figma", "graphic"},
    "ux": {"ux", "ui", "design", "usability"},
    "project-management": {"project", "management", "agile", "scrum", "pmp"},
    "leadership": {"leadership", "management", "lead"},
    "communication": {"communication", "presentation", "writing", "speaking"},
    "negotiation": {"negotiation", "sales", "deals"},
    "sales": {"sales", "selling", "negotiation"},
    "customer-service": {"customer", "service", "support"},
    "spanish": {"spanish", "espanol", "es"},
    "anatomy": {"anatomy", "body", "physiology", "medical"},
    "patient-care": {"patient", "care", "nursing", "medical"},
    "networking": {"networking", "network", "tcp", "wifi"},
    "troubleshooting": {"troubleshooting", "support", "debug", "it"},
    "problem-solving": {"problem", "solving", "logic", "math", "coding"},
    "agile": {"agile", "scrum", "kanban"},
}


def _tokens(text: str) -> set:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if w and w not in _STOP}


# US-centric location aliases for careers search (Remotive uses "Remote (US)" etc.).
_US_LOC_ALIASES = frozenset({
    "usa", "us", "u.s.", "u.s.a.", "united states", "america", "american",
})
_US_MARKERS = (
    "united states", "u.s.", "usa", "remote (us)", "remote us", "anywhere in us",
    "us only", "us-based", "us based",
)
_US_STATE_ABBR = re.compile(r",\s*[a-z]{2}\b")
_NON_US_MARKERS = (
    "brazil", "são paulo", "sao paulo", "florianópolis", "florianopolis",
    "germany", "france", "spain", "portugal", "india", "canada", "mexico",
    "uk", "united kingdom", "europe", "latam", "latin america",
)


def location_matches(filter_loc: str, job_loc: str) -> bool:
    """Return True when ``job_loc`` satisfies the user's location filter."""
    if not filter_loc or not str(filter_loc).strip():
        return True
    f = str(filter_loc).lower().strip()
    j = str(job_loc or "Remote").lower().strip()
    if f in _US_LOC_ALIASES or f in {"united states", "united states of america"}:
        if any(m in j for m in _NON_US_MARKERS):
            return False
        if any(m in j for m in _US_MARKERS):
            return True
        if _US_STATE_ABBR.search(j):
            return True
        if j in {"remote", "worldwide", "anywhere"}:
            return True
        return False
    return f in j


def filter_jobs_by_location(jobs: Sequence[JobPosting], location: str) -> List[JobPosting]:
    if not location:
        return list(jobs)
    return [j for j in jobs if location_matches(location, j.location)]


def course_tokens(course: dict) -> set:
    """All skill-bearing tokens for a course (tags + title + subject + category)."""
    toks: set = set()
    for t in course.get("tags", []) or []:
        toks |= _tokens(str(t))
        toks.add(str(t).lower())
    toks |= _tokens(course.get("title", ""))
    toks |= _tokens(course.get("subject", ""))
    toks |= _tokens(course.get("category", ""))
    return toks


def skill_covered_by(skill: str, toks: set) -> bool:
    s = skill.lower()
    want = {s, *s.split("-")} | SKILL_SYNONYMS.get(s, set())
    return bool(want & toks)


class CourseMatch(BaseModel):
    course_id: str
    title: str
    covered_skills: List[str]
    match: int


class JobMatch(BaseModel):
    job: JobPosting
    required: List[str]
    matched_courses: List[CourseMatch]
    covered: List[str]
    missing: List[str]
    coverage_pct: int
    recommended_path: List[str]   # course ids that together cover the most skills


def match_courses_to_job(job: JobPosting, courses: Sequence[dict], *, top: int = 8) -> JobMatch:
    req = [s.lower() for s in job.skills]
    matches: List[CourseMatch] = []
    for c in courses:
        toks = course_tokens(c)
        covered = [s for s in req if skill_covered_by(s, toks)]
        if covered:
            matches.append(CourseMatch(
                course_id=c.get("course_id") or c.get("id", ""),
                title=c.get("title", ""), covered_skills=covered, match=len(covered)))
    matches.sort(key=lambda m: (-m.match, m.title))

    # Greedy learning path: add courses that cover new skills until none left.
    covered_union: set = set()
    path: List[str] = []
    for m in matches:
        new = set(m.covered_skills) - covered_union
        if new:
            path.append(m.course_id)
            covered_union |= set(m.covered_skills)
        if covered_union >= set(req):
            break
    coverage = round(100 * len(covered_union) / len(req)) if req else 0
    missing = [s for s in req if s not in covered_union]
    return JobMatch(
        job=job, required=req, matched_courses=matches[:top],
        covered=sorted(covered_union), missing=missing,
        coverage_pct=coverage, recommended_path=path)


def jobs_for_course(course: dict, jobs: Sequence[JobPosting], *, top: int = 10) -> List[dict]:
    """Reverse view: openings whose required skills this course helps with."""
    toks = course_tokens(course)
    out = []
    for j in jobs:
        hit = [s for s in j.skills if skill_covered_by(s, toks)]
        if hit:
            out.append({"job": j, "relevant_skills": hit, "match": len(hit)})
    out.sort(key=lambda x: -x["match"])
    return out[:top]


# --------------------------------------------------------------------------- #
# Curated, representative job board (offline). Skills use tokens the catalog can
# cover; pretty names are derived for display.
# --------------------------------------------------------------------------- #
SAMPLE_JOBS: List[JobPosting] = [
    JobPosting(id="job-swe", title="Junior Software Engineer", company="Northwind Tech",
               location="Remote (US)", source="linkedin", salary_range="$85k-$110k",
               posted_days_ago=2, category="Engineering",
               skills=["python", "git", "sql", "problem-solving"], nice_to_have=["cloud"],
               description="Build and ship features in Python; collaborate via Git."),
    JobPosting(id="job-data", title="Data Analyst", company="BrightMetrics",
               location="Austin, TX", source="indeed", salary_range="$70k-$95k",
               posted_days_ago=5, category="Data",
               skills=["sql", "excel", "data-analysis", "statistics"], nice_to_have=["python"],
               description="Turn data into insights with SQL, Excel and statistics."),
    JobPosting(id="job-cloud", title="Cloud / DevOps Engineer", company="Skylift Cloud",
               location="Remote", source="linkedin", salary_range="$120k-$150k",
               posted_days_ago=1, category="Engineering",
               skills=["cloud", "devops", "linux", "python"],
               description="Run resilient cloud infra; automate everything."),
    JobPosting(id="job-ml", title="Machine Learning Engineer", company="Cortex Labs",
               location="Remote", source="linkedin", salary_range="$140k-$180k",
               posted_days_ago=7, category="Data",
               skills=["python", "machine-learning", "statistics", "data-analysis"],
               description="Train and deploy ML models in production."),
    JobPosting(id="job-mktg", title="Digital Marketing Specialist", company="Lumen Media",
               location="New York, NY", source="indeed", salary_range="$55k-$75k",
               posted_days_ago=3, category="Marketing",
               skills=["marketing", "seo", "communication"],
               description="Grow audiences with SEO and content campaigns."),
    JobPosting(id="job-ux", title="UX/UI Designer", company="Forma Studio",
               location="Remote", source="linkedin", salary_range="$90k-$120k",
               posted_days_ago=4, category="Design",
               skills=["design", "ux", "communication"],
               description="Design delightful, usable product experiences."),
    JobPosting(id="job-pm", title="Project Manager", company="Apex Solutions",
               location="Chicago, IL", source="indeed", salary_range="$95k-$120k",
               posted_days_ago=6, category="Operations",
               skills=["project-management", "communication", "leadership", "agile"],
               description="Lead cross-functional teams to deliver on time."),
    JobPosting(id="job-cs-es", title="Bilingual Customer Success (Spanish)", company="Hola Health",
               location="Miami, FL", source="indeed", salary_range="$50k-$68k",
               posted_days_ago=2, category="Customer",
               skills=["spanish", "communication", "customer-service"],
               description="Support Spanish-speaking customers and drive retention."),
    JobPosting(id="job-fin", title="Financial Analyst", company="Sterling Capital",
               location="Remote (US)", source="linkedin", salary_range="$80k-$105k",
               posted_days_ago=8, category="Finance",
               skills=["finance", "excel", "accounting"],
               description="Build models and analyze company performance."),
    JobPosting(id="job-sales", title="Sales Representative", company="Pinnacle Group",
               location="Denver, CO", source="indeed", salary_range="$50k + commission",
               posted_days_ago=3, category="Sales",
               skills=["sales", "communication", "negotiation"],
               description="Own the full sales cycle for SMB accounts."),
    JobPosting(id="job-it", title="IT Support Specialist", company="HelpDesk Heroes",
               location="Remote", source="indeed", salary_range="$48k-$62k",
               posted_days_ago=1, category="IT",
               skills=["troubleshooting", "networking", "communication"],
               description="Resolve technical issues and keep teams productive."),
    JobPosting(id="job-rn", title="Registered Nurse (Med-Surg)", company="Cedar Valley Hospital",
               location="Portland, OR", source="indeed", salary_range="$75k-$98k",
               posted_days_ago=5, category="Healthcare",
               skills=["anatomy", "patient-care", "communication"],
               description="Provide compassionate, high-quality patient care."),
]


# --------------------------------------------------------------------------- #
# Providers (connect to LinkedIn / other job sites)
#
# LinkedIn has no open public jobs API (partner-only), so "connect to LinkedIn"
# in practice means one of:
#   * Free public job boards with open APIs (Remotive, Arbeitnow, RemoteOK) -
#     real listings, no key.
#   * Keyed aggregators that index LinkedIn/Indeed/Glassdoor postings: JSearch
#     (RapidAPI, indexes Google-for-Jobs incl. LinkedIn) and Adzuna.
#   * A real LinkedIn partner key (LINKEDIN_API_KEY).
# Selection is by env only (dual-mode): with no flag/keys we serve the curated
# offline board (so tests + air-gapped demos work); set JOBS_LIVE=1 (or a key,
# or JOBS_PROVIDER) to pull real openings. Every live provider falls back to the
# sample board on any network/parse failure, so /jobs never breaks.
# --------------------------------------------------------------------------- #
import html as _html  # noqa: E402
import json as _json  # noqa: E402
import time as _time  # noqa: E402
import urllib.request as _urlreq  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

_HTTP_TIMEOUT = float(os.environ.get("JOBS_HTTP_TIMEOUT", "8"))
_CACHE_TTL = int(os.environ.get("JOBS_CACHE_TTL", "900"))   # 15 min
_USER_AGENT = "SalareenCareers/1.0 (+https://salareen.com)"

# Live results cached by id so /jobs/{id} (the course-match view) resolves jobs
# that aren't in SAMPLE_JOBS. Capped at 5000 entries to prevent unbounded growth
# in long-running processes under JOBS_LIVE=1 with diverse queries.
_LIVE_BY_ID: Dict[str, JobPosting] = {}
_LIVE_BY_ID_MAX = 5000
# TTL cache: key -> (expires_at, postings).
_RESULT_CACHE: Dict[str, tuple] = {}


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _strip_html(text: str, *, limit: int = 320) -> str:
    if not text:
        return ""
    plain = _html.unescape(re.sub(r"<[^>]+>", " ", text))
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:limit].rstrip() + ("…" if len(plain) > limit else "")


def _days_ago(value) -> int:
    """Days since an ISO-8601 string or epoch seconds; 0 if unparseable."""
    if value in (None, "", 0):
        return 0
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except (ValueError, OSError, OverflowError):
        return 0


def _category_for(text: str, fallback: str = "") -> str:
    low = (text or "").lower()
    table = [
        ("Engineering", ("software", "developer", "engineer", "backend", "frontend", "devops")),
        ("Data", ("data", "analyst", "machine learning", "ml", "scientist")),
        ("Design", ("design", "ux", "ui", "product design")),
        ("Marketing", ("marketing", "seo", "growth", "content")),
        ("Sales", ("sales", "account executive", "business development")),
        ("Customer", ("customer", "support", "success")),
        ("Finance", ("finance", "accountant", "financial")),
        ("Operations", ("operations", "project manager", "program manager")),
        ("Healthcare", ("nurse", "clinical", "medical", "health")),
        ("IT", ("it support", "help desk", "system admin", "network")),
    ]
    for cat, kws in table:
        if any(k in low for k in kws):
            return cat
    return fallback or "General"


def _derive_skills(title: str, description: str, tags: Optional[Sequence[str]] = None) -> List[str]:
    """Best-effort required-skill tokens from a real posting (so the catalog
    matcher and skill pills work for live jobs too)."""
    parsed = parse_job_description(f"{title}\n{description}")
    skills = list(parsed.get("skills", []))
    for t in tags or []:
        s = str(t).strip().lower().replace(" ", "-")
        if s and s in SKILL_SYNONYMS and s not in skills:
            skills.append(s)
    return skills[:8]


def _http_get_json(url: str, headers: Optional[dict] = None, timeout: Optional[float] = None):
    req = _urlreq.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json",
                                        **(headers or {})})
    with _urlreq.urlopen(req, timeout=timeout or _HTTP_TIMEOUT) as resp:
        return _json.loads(resp.read().decode("utf-8", "replace"))


def _http_get_text(url: str, headers: Optional[dict] = None, timeout: Optional[float] = None) -> str:
    """Fetch a URL and return the raw response body as a string (for RSS/XML feeds)."""
    req = _urlreq.Request(url, headers={"User-Agent": _USER_AGENT,
                                        "Accept": "application/rss+xml, application/xml, text/xml",
                                        **(headers or {})})
    with _urlreq.urlopen(req, timeout=timeout or _HTTP_TIMEOUT) as resp:
        return resp.read().decode("utf-8", "replace")


def _cache_get(key: str) -> Optional[List[JobPosting]]:
    hit = _RESULT_CACHE.get(key)
    if hit and hit[0] > _time.time():
        return hit[1]
    return None


def _cache_put(key: str, postings: List[JobPosting]) -> None:
    _RESULT_CACHE[key] = (_time.time() + _CACHE_TTL, postings)
    for j in postings:
        _LIVE_BY_ID[j.id] = j
    # Evict oldest half when cap is hit to prevent unbounded memory growth.
    if len(_LIVE_BY_ID) > _LIVE_BY_ID_MAX:
        evict = list(_LIVE_BY_ID.keys())[: _LIVE_BY_ID_MAX // 2]
        for k in evict:
            _LIVE_BY_ID.pop(k, None)


class JobsProvider(abc.ABC):
    source = "sample"

    @abc.abstractmethod
    def search(self, *, query: str = "", location: str = "",
               limit: int = 50) -> List[JobPosting]:
        ...


class MockJobsProvider(JobsProvider):
    """Offline, curated board representative of LinkedIn/Indeed listings."""

    source = "sample"

    def search(self, *, query: str = "", location: str = "", limit: int = 50) -> List[JobPosting]:
        rows = SAMPLE_JOBS
        if query:
            q = query.lower()
            rows = [j for j in rows if q in j.title.lower() or q in j.company.lower()
                    or q in j.category.lower() or any(q in s for s in j.skills)]
        if location:
            rows = filter_jobs_by_location(rows, location)
        return rows[:limit]


class _LiveJobsProvider(JobsProvider):
    """Base for network-backed providers: cache + graceful fallback to sample.

    Subclasses implement ``_fetch`` (the raw HTTP call) and ``_parse`` (rows ->
    JobPosting). ``search`` adds TTL caching and, on any failure or empty result,
    falls back to the curated board so the careers page always renders.
    """

    source = "live"

    def _fetch(self, query: str, location: str, limit: int):  # -> raw rows
        raise NotImplementedError

    def _parse(self, rows) -> List[JobPosting]:
        raise NotImplementedError

    def search(self, *, query: str = "", location: str = "", limit: int = 50) -> List[JobPosting]:
        key = f"{self.source}|{query}|{location}|{limit}"
        cached = _cache_get(key)
        if cached is not None:
            return cached
        try:
            rows = self._fetch(query, location, limit)
            postings = [p for p in self._parse(rows) if p]
            if location:
                postings = filter_jobs_by_location(postings, location)
            postings = postings[:limit]
        except Exception:  # noqa: BLE001 - any network/parse error -> fallback
            postings = []
        if not postings:
            # Air-gapped / provider down. Return [] so CompositeJobsProvider can
            # exclude this provider and fall back to the sample board at its level.
            # Serving the sample board here would corrupt the composite's merge.
            # When this provider is used standalone (not in a composite), callers
            # that need a non-empty result must handle the empty list themselves.
            return []
        _cache_put(key, postings)
        return postings


class RemotiveJobsProvider(_LiveJobsProvider):
    """Real remote jobs from remotive.com (free, no key)."""

    source = "remotive"

    def _fetch(self, query, location, limit):
        from urllib.parse import urlencode
        qs = urlencode({k: v for k, v in {"search": query, "limit": max(limit, 1)}.items() if v})
        data = _http_get_json(f"https://remotive.com/api/remote-jobs?{qs}")
        return data.get("jobs", []) if isinstance(data, dict) else []

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for r in rows:
            title = r.get("title", "")
            desc = _strip_html(r.get("description", ""))
            tags = r.get("tags") or []
            out.append(JobPosting(
                id=f"remotive-{r.get('id')}",
                title=title, company=r.get("company_name", ""),
                location=r.get("candidate_required_location") or "Remote",
                source="remotive", url=r.get("url", ""),
                employment_type=(r.get("job_type") or "full_time").replace("_", "-").title(),
                salary_range=r.get("salary", "") or "",
                posted_days_ago=_days_ago(r.get("publication_date")),
                category=_category_for(f"{title} {r.get('category','')}", r.get("category", "")),
                skills=_derive_skills(title, desc, tags), description=desc))
        return out


class ArbeitnowJobsProvider(_LiveJobsProvider):
    """Real jobs from arbeitnow.com job board (free, no key)."""

    source = "arbeitnow"

    def _fetch(self, query, location, limit):
        data = _http_get_json("https://www.arbeitnow.com/api/job-board-api")
        rows = data.get("data", []) if isinstance(data, dict) else []
        ql = query.lower()
        if ql:
            rows = [r for r in rows if ql in (r.get("title", "") + " "
                    + " ".join(r.get("tags") or [])).lower()]
        return rows

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for r in rows:
            title = r.get("title", "")
            desc = _strip_html(r.get("description", ""))
            tags = r.get("tags") or []
            loc = r.get("location") or ("Remote" if r.get("remote") else "")
            out.append(JobPosting(
                id=f"arbeitnow-{r.get('slug')}",
                title=title, company=r.get("company_name", ""), location=loc or "Remote",
                source="arbeitnow", url=r.get("url", ""),
                employment_type=(", ".join(r.get("job_types") or []) or "Full-time").title(),
                posted_days_ago=_days_ago(r.get("created_at")),
                category=_category_for(f"{title} {' '.join(tags)}"),
                skills=_derive_skills(title, desc, tags), description=desc))
        return out


class AdzunaJobsProvider(_LiveJobsProvider):
    """Adzuna aggregator (real, multi-board). Needs ADZUNA_APP_ID + ADZUNA_APP_KEY."""

    source = "adzuna"

    def __init__(self, app_id: str, app_key: str, country: str = "us") -> None:
        self.app_id, self.app_key, self.country = app_id, app_key, country

    def _fetch(self, query, location, limit):
        from urllib.parse import urlencode
        params = {"app_id": self.app_id, "app_key": self.app_key,
                  "results_per_page": max(min(limit, 50), 1), "content-type": "application/json"}
        if query:
            params["what"] = query
        if location:
            params["where"] = location
        url = f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/1?{urlencode(params)}"
        data = _http_get_json(url)
        return data.get("results", []) if isinstance(data, dict) else []

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for r in rows:
            title = r.get("title", "")
            desc = _strip_html(r.get("description", ""))
            smin, smax = r.get("salary_min"), r.get("salary_max")
            salary = f"${int(smin/1000)}k-${int(smax/1000)}k" if smin and smax else ""
            out.append(JobPosting(
                id=f"adzuna-{r.get('id')}",
                title=title, company=(r.get("company") or {}).get("display_name", ""),
                location=(r.get("location") or {}).get("display_name", "") or "Remote",
                source="adzuna", url=r.get("redirect_url", ""),
                employment_type=(r.get("contract_time") or "full_time").replace("_", "-").title(),
                salary_range=salary, posted_days_ago=_days_ago(r.get("created")),
                category=_category_for(f"{title} {(r.get('category') or {}).get('label','')}"),
                skills=_derive_skills(title, desc), description=desc))
        return out


class JSearchJobsProvider(_LiveJobsProvider):
    """JSearch (RapidAPI) - indexes Google-for-Jobs incl. LinkedIn, Indeed,
    Glassdoor, ZipRecruiter. Needs RAPIDAPI_KEY (the closest to real LinkedIn)."""

    source = "jsearch"

    def __init__(self, rapidapi_key: str) -> None:
        self.rapidapi_key = rapidapi_key

    def _fetch(self, query, location, limit):
        from urllib.parse import urlencode
        q = (f"{query} in {location}" if location else query) or "software engineer"
        url = f"https://jsearch.p.rapidapi.com/search?{urlencode({'query': q, 'num_pages': 1})}"
        data = _http_get_json(url, headers={
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"})
        return data.get("data", []) if isinstance(data, dict) else []

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for r in rows:
            title = r.get("job_title", "")
            desc = _strip_html(r.get("job_description", ""))
            city, country = r.get("job_city"), r.get("job_country")
            loc = ", ".join([p for p in (city, country) if p]) or (
                "Remote" if r.get("job_is_remote") else "")
            smin, smax = r.get("job_min_salary"), r.get("job_max_salary")
            salary = f"${int(smin/1000)}k-${int(smax/1000)}k" if smin and smax else ""
            publisher = r.get("job_publisher") or "jsearch"   # e.g. "LinkedIn"
            out.append(JobPosting(
                id=f"jsearch-{r.get('job_id')}",
                title=title, company=r.get("employer_name", ""), location=loc or "Remote",
                source=publisher.lower(), url=r.get("job_apply_link") or r.get("job_google_link", ""),
                employment_type=(r.get("job_employment_type") or "FULLTIME").title(),
                salary_range=salary, posted_days_ago=_days_ago(r.get("job_posted_at_timestamp")),
                category=_category_for(title),
                skills=_derive_skills(title, desc), description=desc))
        return out


class LinkedInRapidApiProvider(_LiveJobsProvider):
    """LinkedIn job search via RapidAPI (linkedin-api8.p.rapidapi.com).

    The key is rate-limited to ~25 requests/month (250 jobs total). To stay
    within budget this provider:
      - Caches results for 24 hours (JOBS_CACHE_TTL is overridden per-call)
      - Tracks monthly usage in a module-level counter and refuses to make
        further requests once LINKEDIN_RAPIDAPI_MONTHLY_LIMIT is reached.
    Set RAPIDAPI_KEY in aoep-secrets to activate.
    """

    source = "linkedin"
    MONTHLY_LIMIT = 24          # leave 1 in reserve
    _month_key: str = ""        # "YYYY-MM" when counter was last reset
    _month_calls: int = 0       # API calls made this calendar month

    def __init__(self, rapidapi_key: str) -> None:
        self.rapidapi_key = rapidapi_key

    def _within_limit(self) -> bool:
        import time as _t
        import datetime as _dt
        month = _dt.datetime.fromtimestamp(_t.time(), tz=_dt.timezone.utc).strftime("%Y-%m")
        if LinkedInRapidApiProvider._month_key != month:
            LinkedInRapidApiProvider._month_key = month
            LinkedInRapidApiProvider._month_calls = 0
        return LinkedInRapidApiProvider._month_calls < self.MONTHLY_LIMIT

    def _fetch(self, query, location, limit):
        if not self._within_limit():
            return []   # quota exhausted for this month; fall through to free boards
        from urllib.parse import urlencode
        params: dict[str, object] = {
            "keywords": query or "software engineer",
            "datePosted": "anyTime",
            "sort": "mostRelevant",
            "start": "0",
        }
        if location:
            params["locationId"] = location  # RapidAPI accepts free-text too
        url = f"https://linkedin-api8.p.rapidapi.com/search-jobs?{urlencode(params)}"
        data = _http_get_json(url, headers={
            "x-rapidapi-key": self.rapidapi_key,
            "x-rapidapi-host": "linkedin-api8.p.rapidapi.com",
        })
        LinkedInRapidApiProvider._month_calls += 1
        if isinstance(data, dict):
            return data.get("data", []) or []
        if isinstance(data, list):
            return data
        return []

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for r in rows:
            title = r.get("title", "") or r.get("jobTitle", "")
            company = (r.get("company") or {}).get("name", "") or r.get("companyName", "")
            loc = (r.get("location") or {}).get("displayName", "") or r.get("locationName", "") or "United States"
            url = r.get("url", "") or r.get("jobPostingUrl", "")
            emp = (r.get("employmentStatus") or "full-time").replace("_", "-").title()
            posted = r.get("postedAt") or r.get("listedAt") or ""
            desc = _strip_html(r.get("description", "") or "")
            job_id = r.get("id", "") or url.split("/")[-1].split("?")[0]
            out.append(JobPosting(
                id=f"linkedin-{job_id}",
                title=title, company=company, location=loc,
                source="linkedin", url=url,
                employment_type=emp,
                posted_days_ago=_days_ago(posted),
                category=_category_for(title),
                skills=_derive_skills(title, desc), description=desc))
        return out


class USAJobsProvider(_LiveJobsProvider):
    """U.S. federal government jobs from usajobs.gov (free, no key required).

    Open API: https://data.usajobs.gov/api/search
    Best for education, technology, healthcare, and government roles.
    """

    source = "usajobs"

    def _fetch(self, query, location, limit):
        from urllib.parse import urlencode
        api_key = os.environ.get("USAJOBS_API_KEY", "").strip()
        if not api_key:
            return []  # skip gracefully without key — avoids 403 on every request
        params: dict[str, object] = {"ResultsPerPage": max(min(limit, 25), 1)}
        if query:
            params["Keyword"] = query
        if location:
            params["LocationName"] = location
        url = f"https://data.usajobs.gov/api/search?{urlencode(params)}"
        data = _http_get_json(url, headers={
            "Host": "data.usajobs.gov",
            "User-Agent": "salareen-jobs/1.0 (jobs@salareen.com)",
            "Authorization-Key": api_key,
        })
        search_result = (data or {}).get("SearchResult", {})
        return (search_result or {}).get("SearchResultItems", [])

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for item in rows:
            mv = item.get("MatchedObjectDescriptor", {})
            if not mv:
                continue
            title = mv.get("PositionTitle", "")
            company = (mv.get("OrganizationName") or mv.get("DepartmentName") or "US Government")
            locations = mv.get("PositionLocation", [{}])
            loc = locations[0].get("LocationName", "United States") if locations else "United States"
            url = mv.get("PositionURI", "")
            pay = mv.get("PositionRemuneration", [{}])
            salary = ""
            if pay:
                lo, hi = pay[0].get("MinimumRange", ""), pay[0].get("MaximumRange", "")
                if lo and hi:
                    salary = f"${int(float(lo)/1000)}k–${int(float(hi)/1000)}k"
            desc = _strip_html(mv.get("QualificationSummary", "") or mv.get("UserArea", {}).get("Details", {}).get("MajorDuties", ""))
            out.append(JobPosting(
                id=f"usajobs-{mv.get('PositionID', '')}",
                title=title, company=company, location=loc,
                source="usajobs", url=url,
                employment_type="Full-time",
                salary_range=salary,
                posted_days_ago=_days_ago(mv.get("PublicationStartDate")),
                category=_category_for(title),
                skills=_derive_skills(title, desc), description=desc))
        return out


class WeWorkRemotelyProvider(_LiveJobsProvider):
    """Remote jobs from weworkremotely.com (free RSS feed, no key required).

    Best for fully-remote software, design, marketing, and business roles.
    """

    source = "weworkremotely"

    def _fetch(self, query, location, limit):
        import xml.etree.ElementTree as ET
        raw = _http_get_text("https://weworkremotely.com/remote-jobs.rss")
        if not raw:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        items = root.findall(".//item")
        if query:
            ql = query.lower()
            items = [i for i in items
                     if ql in ((i.findtext("title") or "") + " " + (i.findtext("description") or "")).lower()]
        return items[:max(limit, 1)]

    def _parse(self, rows) -> List[JobPosting]:
        NS = "https://weworkremotely.com/"
        out = []
        for item in rows:
            def _t(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""
            title_raw = _t("title")  # "Company: Job Title"
            parts = title_raw.split(": ", 1)
            company = parts[0].strip() if len(parts) > 1 else ""
            title = parts[1].strip() if len(parts) > 1 else title_raw
            link = _t("link")
            desc = _strip_html(_t("description"))
            pub = _t("pubDate")
            region = _t(f"{{{NS}}}region") or "Remote"
            out.append(JobPosting(
                id=f"wwr-{link.split('/')[-2] if '/' in link else link[-16:]}",
                title=title, company=company, location=region or "Remote",
                source="weworkremotely", url=link,
                employment_type="Full-time",
                posted_days_ago=_days_ago(pub),
                category=_category_for(title),
                skills=_derive_skills(title, desc), description=desc))
        return out


class JobspressoProvider(_LiveJobsProvider):
    """Curated remote jobs from jobspresso.co (free RSS feed, no key required).

    Covers tech, marketing, customer support, and design remote roles.
    """

    source = "jobspresso"

    def _fetch(self, query, location, limit):
        import xml.etree.ElementTree as ET
        raw = _http_get_text("https://jobspresso.co/feed/")
        if not raw:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        items = root.findall(".//item")
        if query:
            ql = query.lower()
            items = [i for i in items
                     if ql in ((i.findtext("title") or "") + " " + (i.findtext("description") or "")).lower()]
        return items[:max(limit, 1)]

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for item in rows:
            def _t(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""
            title = _t("title")
            link = _t("link")
            desc = _strip_html(_t("description"))
            pub = _t("pubDate")
            creator = _t("{http://purl.org/dc/elements/1.1/}creator") or ""
            out.append(JobPosting(
                id=f"jobspresso-{link.split('/')[-2] if '/' in link else link[-16:]}",
                title=title, company=creator,
                location="Remote",
                source="jobspresso", url=link,
                employment_type="Full-time",
                posted_days_ago=_days_ago(pub),
                category=_category_for(title),
                skills=_derive_skills(title, desc), description=desc))
        return out


class IndeedScraperProvider(_LiveJobsProvider):
    """Indeed jobs via the Indeed Scraper API on RapidAPI.

    POST https://indeed-scraper-api.p.rapidapi.com/api/job
    Needs RAPIDAPI_KEY. Free tier allows ~10 calls/day; this provider
    tracks usage in a module-level day counter and stops once the limit
    is reached (falling through to the free RSS feed instead).
    """

    source = "indeed-api"
    DAILY_LIMIT = 10
    _day_key: str = ""
    _day_calls: int = 0

    def __init__(self, rapidapi_key: str) -> None:
        self.rapidapi_key = rapidapi_key

    def _within_limit(self) -> bool:
        import datetime as _dt
        day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
        if IndeedScraperProvider._day_key != day:
            IndeedScraperProvider._day_key = day
            IndeedScraperProvider._day_calls = 0
        return IndeedScraperProvider._day_calls < self.DAILY_LIMIT

    def _fetch(self, query, location, limit):
        if not self._within_limit():
            return []
        payload = _json.dumps({
            "scraper": {
                "maxRows": min(limit, 15),
                "query": query or "software engineer",
                "location": location or "United States",
                "jobType": "fulltime",
                "radius": "50",
                "sort": "relevance",
                "fromDays": "7",
                "country": "us",
            }
        }).encode("utf-8")
        req = _urlreq.Request(
            "https://indeed-scraper-api.p.rapidapi.com/api/job",
            data=payload,
            headers={
                "User-Agent": _USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-rapidapi-host": "indeed-scraper-api.p.rapidapi.com",
                "x-rapidapi-key": self.rapidapi_key,
            },
        )
        with _urlreq.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            data = _json.loads(resp.read().decode("utf-8", "replace"))
        IndeedScraperProvider._day_calls += 1
        if isinstance(data, dict):
            for key in ("jobs", "results", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        if isinstance(data, list):
            return data
        return []

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for r in rows:
            title = r.get("title", "") or r.get("jobTitle", "")
            company = (r.get("company", "") or r.get("companyName", "")
                       or r.get("employer", "") or "")
            location_raw = (r.get("location", "") or r.get("jobLocation", "")
                            or "United States")
            link = r.get("url", "") or r.get("link", "") or r.get("jobUrl", "")
            desc = _strip_html(r.get("description", "")
                               or r.get("jobDescription", "") or "")
            pub = (r.get("datePosted", "") or r.get("posted", "")
                   or r.get("date", "") or "")
            salary = r.get("salary", "") or r.get("salaryRange", "") or ""
            job_id = (r.get("id", "") or r.get("jobId", "")
                      or (link.split("jk=")[-1].split("&")[0] if "jk=" in link
                          else link[-20:]))
            out.append(JobPosting(
                id=f"indeed-api-{job_id}",
                title=title, company=company,
                location=location_raw or "United States",
                source="indeed-api", url=link,
                employment_type="Full-time",
                salary_range=str(salary),
                posted_days_ago=_days_ago(pub),
                category=_category_for(title),
                skills=_derive_skills(title, desc), description=desc))
        return out


class IndeedRssProvider(_LiveJobsProvider):
    """Indeed jobs via their public RSS feed (free, no key required).

    RSS endpoint: https://www.indeed.com/rss?q=<query>&l=<location>
    Returns real listings from Indeed's job board — same ones you see on
    the website. Results are tagged source="indeed".
    """

    source = "indeed"

    def _fetch(self, query, location, limit):
        from urllib.parse import urlencode
        import xml.etree.ElementTree as ET
        params: dict[str, object] = {"fromage": 30, "limit": max(min(limit, 50), 1)}
        if query:
            params["q"] = query
        if location:
            params["l"] = location
        url = f"https://www.indeed.com/rss?{urlencode(params)}"
        raw = _http_get_text(url)
        if not raw:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        return root.findall(".//item")

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for item in rows:
            def _t(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""
            title = _t("title")
            company = _t("{http://www.google.com/schemas/sitemap/0.84}name") or _t("author") or ""
            location_raw = _t("{http://www.google.com/schemas/sitemap/0.84}location") or ""
            # Indeed RSS puts "Company - Location" in title sometimes; best-effort parse
            link = _t("link")
            desc = _strip_html(_t("description"))
            pub = _t("pubDate")
            job_id = link.split("jk=")[-1].split("&")[0] if "jk=" in link else link[-20:]
            out.append(JobPosting(
                id=f"indeed-{job_id}",
                title=title, company=company,
                location=location_raw or "United States",
                source="indeed", url=link,
                employment_type="Full-time",
                posted_days_ago=_days_ago(pub),
                category=_category_for(title),
                skills=_derive_skills(title, desc), description=desc))
        return out


class RemoteOkProvider(_LiveJobsProvider):
    """RemoteOK remote-only job board (free, no key required).

    Covers software, design, marketing, sales and other remote roles.
    API: https://remoteok.com/api — returns JSON array directly.
    """

    source = "remoteok"

    def _fetch(self, query, location, limit):
        tag = query.replace(" ", "-").lower() if query else ""
        url = f"https://remoteok.com/api{'?tags=' + tag if tag else ''}"
        data = _http_get_json(url, headers={"User-Agent": "salareen-jobs/1.0"})
        if not isinstance(data, list):
            return []
        # First element is a metadata dict, skip it
        rows = [r for r in data if isinstance(r, dict) and "position" in r]
        if query:
            ql = query.lower()
            rows = [r for r in rows
                    if ql in (r.get("position", "") + " " + " ".join(r.get("tags") or [])).lower()]
        return rows[:max(limit, 1)]

    def _parse(self, rows) -> List[JobPosting]:
        out = []
        for r in rows:
            title = r.get("position", "")
            desc = _strip_html(r.get("description", ""))
            tags = r.get("tags") or []
            out.append(JobPosting(
                id=f"remoteok-{r.get('id', '')}",
                title=title, company=r.get("company", ""),
                location="Remote", source="remoteok",
                url=r.get("url", "") or f"https://remoteok.com/remote-jobs/{r.get('slug','')}",
                salary_range=r.get("salary", "") or "",
                posted_days_ago=_days_ago(r.get("date")),
                category=_category_for(f"{title} {' '.join(tags)}"),
                skills=_derive_skills(title, desc, tags), description=desc))
        return out


class LinkedInJobsProvider(JobsProvider):
    """Real LinkedIn jobs via a partner key (LINKEDIN_API_KEY). LinkedIn has no
    open public API, so without partner access use JSearch/Adzuna instead; this
    raises so the caller falls back to the curated board."""

    source = "linkedin"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, *, query: str = "", location: str = "", limit: int = 50) -> List[JobPosting]:
        raise NotImplementedError(
            "Direct LinkedIn jobs need LinkedIn partner API access. Set RAPIDAPI_KEY "
            "(JSearch indexes LinkedIn postings) or ADZUNA_APP_ID/ADZUNA_APP_KEY for "
            "real listings instead.")


class CompositeJobsProvider(_LiveJobsProvider):
    """Query several live providers, merge + de-dup, fall back to sample."""

    def __init__(self, providers: Sequence[JobsProvider]) -> None:
        self.providers = list(providers)
        self.source = "+".join(p.source for p in providers) or "live"

    def search(self, *, query: str = "", location: str = "", limit: int = 50) -> List[JobPosting]:
        merged: List[JobPosting] = []
        seen = set()
        used = []
        for p in self.providers:
            try:
                rows = p.search(query=query, location=location, limit=limit)
            except Exception:  # noqa: BLE001
                rows = []
            if getattr(p, "source", "") == "sample":
                continue  # standalone sample provider; skip in composite
            for j in rows:
                dedup = (j.title.lower(), j.company.lower())
                if dedup in seen:
                    continue
                seen.add(dedup)
                merged.append(j)
            if rows:
                used.append(p.source)
        if not merged:
            self.source = "sample"
            return MockJobsProvider().search(query=query, location=location, limit=limit)
        self.source = "+".join(dict.fromkeys(used)) or "live"
        for j in merged:
            _LIVE_BY_ID[j.id] = j
        return merged[:limit]


def get_jobs_provider(env: Optional[dict] = None) -> JobsProvider:
    env = env if env is not None else os.environ
    choice = (env.get("JOBS_PROVIDER") or "").strip().lower()

    def _build(name: str) -> Optional[JobsProvider]:
        if name in ("sample", "mock"):
            return MockJobsProvider()
        if name == "remotive":
            return RemotiveJobsProvider()
        if name == "arbeitnow":
            return ArbeitnowJobsProvider()
        if name in ("indeed-api", "indeed_api") and env.get("RAPIDAPI_KEY"):
            return IndeedScraperProvider(env["RAPIDAPI_KEY"])
        if name == "indeed":
            return IndeedRssProvider()
        if name == "remoteok":
            return RemoteOkProvider()
        if name == "usajobs":
            return USAJobsProvider()
        if name == "weworkremotely":
            return WeWorkRemotelyProvider()
        if name == "jobspresso":
            return JobspressoProvider()
        if name == "linkedin" and env.get("RAPIDAPI_KEY"):
            return LinkedInRapidApiProvider(env["RAPIDAPI_KEY"])
        if name == "jsearch" and env.get("RAPIDAPI_KEY"):
            return JSearchJobsProvider(env["RAPIDAPI_KEY"])
        if name == "adzuna" and env.get("ADZUNA_APP_ID") and env.get("ADZUNA_APP_KEY"):
            return AdzunaJobsProvider(env["ADZUNA_APP_ID"], env["ADZUNA_APP_KEY"],
                                      env.get("ADZUNA_COUNTRY", "us"))
        if name == "linkedin" and (env.get("LINKEDIN_API_KEY") or env.get("JOBS_API_KEY")):
            return LinkedInJobsProvider(env.get("LINKEDIN_API_KEY") or env["JOBS_API_KEY"])
        if name == "live":
            return None  # handled below
        return None

    if choice and choice != "live":
        prov = _build(choice)
        if prov:
            return prov

    # RapidAPI key activates JSearch as the single provider when JOBS_LIVE is not
    # set. When JOBS_LIVE=1 is also present, fall through to the composite block
    # below so IndeedScraperProvider (and other boards) are included as well.
    if env.get("RAPIDAPI_KEY") and not _truthy(env.get("JOBS_LIVE")):
        return JSearchJobsProvider(env["RAPIDAPI_KEY"])
    if env.get("ADZUNA_APP_ID") and env.get("ADZUNA_APP_KEY"):
        return AdzunaJobsProvider(env["ADZUNA_APP_ID"], env["ADZUNA_APP_KEY"],
                                  env.get("ADZUNA_COUNTRY", "us"))
    if env.get("LINKEDIN_API_KEY") or env.get("JOBS_API_KEY"):
        return LinkedInJobsProvider(env.get("LINKEDIN_API_KEY") or env["JOBS_API_KEY"])

    # Live free boards when explicitly enabled (JOBS_LIVE=1 or JOBS_PROVIDER=live).
    # NOTE: LinkedInRapidApiProvider and IndeedScraperProvider are disabled —
    # the linkedin-api8 endpoint was shut down ("no longer providing this service")
    # and the indeed-scraper-api returns 403 with the current key. Both are kept
    # in the codebase for when new API keys are sourced. Free sources only for now.
    if _truthy(env.get("JOBS_LIVE")) or choice == "live":
        providers: List[JobsProvider] = [
            IndeedRssProvider(),
            USAJobsProvider(),
            WeWorkRemotelyProvider(),
            JobspressoProvider(),
            RemoteOkProvider(),
            RemotiveJobsProvider(),
            ArbeitnowJobsProvider(),
        ]
        return CompositeJobsProvider(providers)

    # Default (tests / air-gapped): the curated sample board.
    return MockJobsProvider()


def get_job(job_id: str) -> Optional[JobPosting]:
    for j in SAMPLE_JOBS:
        if j.id == job_id:
            return j
    return _LIVE_BY_ID.get(job_id)


# --------------------------------------------------------------------------- #
# Job-description parsing -> targeted classes (incl. certifications).
# Once we have a real LinkedIn/Indeed job description, extract the concrete
# skills + certifications it asks for and recommend specific classes/cert prep.
# --------------------------------------------------------------------------- #
# canonical certification -> alias phrases to detect in free text.
KNOWN_CERTS: Dict[str, List[str]] = {
    "Cisco UCS Manager (UCSM)": ["ucsm", "ucs manager", "cisco ucs", "unified computing"],
    "Cisco CCNA": ["ccna"],
    "Cisco CCNP": ["ccnp"],
    "AWS Certified Solutions Architect": ["aws certified", "aws solutions architect", "aws saa"],
    "Microsoft Azure (AZ-104)": ["az-104", "azure administrator", "azure certified"],
    "Google Cloud (GCP) Certification": ["gcp certified", "google cloud certified"],
    "CompTIA A+": ["comptia a+", "a+ certification"],
    "CompTIA Network+": ["network+"],
    "CompTIA Security+": ["security+"],
    "CISSP": ["cissp"],
    "Certified Kubernetes Administrator (CKA)": ["cka", "kubernetes administrator", "ckad"],
    "PMP (Project Management Professional)": ["pmp", "project management professional"],
    "Certified ScrumMaster (CSM)": ["scrum master", "certified scrummaster", "csm"],
    "Six Sigma": ["six sigma", "lean six sigma"],
    "CPA (Certified Public Accountant)": ["cpa", "certified public accountant"],
    "RN / NCLEX": ["nclex", "registered nurse license", "rn license"],
    "Google Analytics Certification": ["google analytics", "ga4 certified"],
    "Salesforce Administrator": ["salesforce administrator", "salesforce certified"],
}

# Extra skill aliases to scan for (beyond SKILL_SYNONYMS keys).
_SKILL_ALIASES: Dict[str, List[str]] = {
    "python": ["python"], "java": ["java"], "javascript": ["javascript", "node.js", "react"],
    "sql": ["sql", "postgres", "mysql"], "linux": ["linux", "unix"],
    "cloud": ["aws", "azure", "gcp", "cloud"], "devops": ["devops", "ci/cd", "terraform"],
    "docker": ["docker"], "kubernetes": ["kubernetes", "k8s"],
    "networking": ["networking", "tcp/ip", "routing", "switching", "vlan", "cisco"],
    "excel": ["excel", "spreadsheets"], "statistics": ["statistics", "statistical"],
    "machine-learning": ["machine learning", "ml", "deep learning"],
    "communication": ["communication", "stakeholder"], "leadership": ["leadership"],
    "project-management": ["project management", "agile", "scrum", "jira"],
    "marketing": ["marketing", "seo", "content"], "design": ["figma", "ux", "ui"],
    "finance": ["financial modeling", "accounting", "finance"],
    "spanish": ["spanish", "bilingual"], "data-analysis": ["data analysis", "analytics", "tableau"],
    "anatomy": ["anatomy", "patient care", "clinical"],
}

# job-title keyword -> profession slug (for inferring who the role is for).
_TITLE_PROFESSION = {
    "software": "software-engineer", "data analyst": "data-analyst",
    "data scientist": "data-scientist", "network": "network-engineer",
    "civil engineer": "civil-engineer", "aerospace": "aerospace-engineer",
    "mechanical engineer": "mechanical-engineer", "electrical engineer": "electrical-engineer",
    "nurse": "nurse", "chef": "chef", "accountant": "accountant",
    "financial analyst": "financial-analyst", "marketing": "marketer",
    "designer": "designer", "project manager": "project-manager", "engineer": "engineer",
}


def _alias_present(alias: str, text: str) -> bool:
    # Boundary match that respects alphanumerics so "csm" doesn't match "ucsm"
    # but "a+"/"network+"/"ci/cd" still match.
    return re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text) is not None


def parse_job_description(text: str) -> dict:
    """Extract skills, certifications, and likely professions from a JD."""
    low = (text or "").lower()
    certs = [canon for canon, aliases in KNOWN_CERTS.items()
             if any(_alias_present(a, low) for a in aliases)]
    skills: List[str] = []
    for skill, aliases in _SKILL_ALIASES.items():
        if any(_alias_present(a, low) for a in aliases):
            skills.append(skill)
    professions: List[str] = []
    for kw, prof in _TITLE_PROFESSION.items():
        if kw in low and prof not in professions:
            professions.append(prof)
    return {"skills": sorted(set(skills)), "certifications": certs, "professions": professions}


def recommend_from_description(text: str, courses: Sequence[dict], *, top: int = 8) -> dict:
    """Parse a JD and recommend catalog courses + targeted specialized/cert classes."""
    parsed = parse_job_description(text)
    synthetic = JobPosting(id="jd", title="Pasted role", company="", skills=parsed["skills"])
    match = match_courses_to_job(synthetic, courses, top=top)
    # Targeted classes the catalog doesn't yet cover - especially certifications.
    specialized = [{"title": f"{c} - Certification Prep", "kind": "certification", "for": c}
                   for c in parsed["certifications"]]
    for s in match.missing:
        specialized.append({"title": f"{pretty_skill(s)} - Targeted Class",
                            "kind": "skill", "for": s})
    return {
        "parsed": parsed,
        "matched_courses": [m.model_dump() for m in match.matched_courses],
        "covered": match.covered, "missing": match.missing,
        "coverage_pct": match.coverage_pct, "recommended_path": match.recommended_path,
        "specialized_classes": specialized,
    }
