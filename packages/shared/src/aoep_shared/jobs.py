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
# --------------------------------------------------------------------------- #
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
            loc = location.lower()
            rows = [j for j in rows if loc in j.location.lower()]
        return rows[:limit]


class LinkedInJobsProvider(JobsProvider):
    """Real LinkedIn jobs (requires LINKEDIN_API_KEY + network); stub offline."""

    source = "linkedin"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, *, query: str = "", location: str = "", limit: int = 50) -> List[JobPosting]:
        raise NotImplementedError(
            "LinkedIn jobs integration requires LINKEDIN_API_KEY and network access; "
            "not available in this environment.")


def get_jobs_provider(env: Optional[dict] = None) -> JobsProvider:
    env = env if env is not None else os.environ
    key = env.get("LINKEDIN_API_KEY") or env.get("JOBS_API_KEY")
    if key:
        return LinkedInJobsProvider(key)
    return MockJobsProvider()


def get_job(job_id: str) -> Optional[JobPosting]:
    for j in SAMPLE_JOBS:
        if j.id == job_id:
            return j
    return None
