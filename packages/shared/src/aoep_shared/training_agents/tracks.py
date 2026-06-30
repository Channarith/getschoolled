"""Learning tracks — curated scenario paths by career and skill."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class TrainingTrack:
    track_id: str
    title: str
    description: str
    domains: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    recommended_count: int = 12


TRAINING_TRACKS: tuple[TrainingTrack, ...] = (
    TrainingTrack(
        "pilot_emergency",
        "Pilot Emergency & Sim Procedures",
        "Engine failures, icing, gear, wind shear, IFR emergencies — for sim and checkride prep.",
        domains=["aviation", "aviation_ifr"],
        skills=["aviation", "emergency-procedures", "ifr"],
        keywords=["engine", "landing", "glide", "icing", "ifr"],
        recommended_count=20,
    ),
    TrainingTrack(
        "first_responder",
        "First Responder & Triage",
        "Mass casualty, cardiac, trauma, hazmat exposure — scene safety and triage order.",
        domains=["medical", "fire_safety", "hazmat", "search_rescue"],
        skills=["medical-triage", "emergency-procedures", "hazmat"],
        keywords=["triage", "scene", "victim", "ems"],
        recommended_count=18,
    ),
    TrainingTrack(
        "healthcare_clinical",
        "Healthcare & Nursing Judgment",
        "Bedside crises, rapid response, medication safety, patient elopement.",
        domains=["medical", "nursing", "pharma"],
        skills=["nursing", "clinical-judgment", "patient-safety"],
        keywords=["patient", "nurse", "bedside", "clinical"],
        recommended_count=16,
    ),
    TrainingTrack(
        "cyber_ir",
        "Cyber Incident Response",
        "Ransomware, breach, insider threat — contain without destroying evidence.",
        domains=["cybersecurity", "telecom"],
        skills=["cybersecurity", "incident-response"],
        keywords=["ransomware", "breach", "isolate", "phishing"],
        recommended_count=14,
    ),
    TrainingTrack(
        "leadership_crisis",
        "Leadership Under Crisis",
        "PR crises, outages, recalls — communicate when facts are incomplete.",
        domains=["leadership", "disaster_recovery", "finance"],
        skills=["leadership", "crisis-communication"],
        keywords=["stakeholder", "communicate", "crisis", "recall"],
        recommended_count=14,
    ),
    TrainingTrack(
        "educator_safety",
        "Educator & Campus Safety",
        "Lockdowns, medical events, weather dismissal, online harassment.",
        domains=["education", "child_safety", "security"],
        skills=["education-safety", "classroom-management"],
        keywords=["student", "classroom", "lockdown", "school"],
        recommended_count=14,
    ),
    TrainingTrack(
        "parent_caregiver",
        "Parent & Caregiver Readiness",
        "Choking, strangers, bullying, online safety — calm decisions at home.",
        domains=["parenting", "child_safety"],
        skills=["parenting", "child-safety"],
        keywords=["child", "parent", "home", "pool"],
        recommended_count=12,
    ),
    TrainingTrack(
        "critical_thinking",
        "Critical Thinking & Media Literacy",
        "Evaluate claims, evidence, bias — under time pressure.",
        domains=["media_literacy", "general", "legal", "finance"],
        skills=["critical-thinking", "media-literacy"],
        keywords=["evidence", "claim", "verify", "bias"],
        recommended_count=12,
    ),
    TrainingTrack(
        "maritime_industrial",
        "Maritime & Industrial Hazards",
        "Ship emergencies, plant spills, lockout, crane loads.",
        domains=["maritime", "industrial", "mining", "energy"],
        skills=["maritime", "industrial-safety", "mining"],
        keywords=["plant", "vessel", "spill", "lockout"],
        recommended_count=16,
    ),
    TrainingTrack(
        "mental_wellness",
        "Mental Health & De-escalation",
        "Suicidal ideation, psychosis, aggression — safety-first responses.",
        domains=["mental_health", "conflict", "social_work"],
        skills=["mental-health", "de-escalation"],
        keywords=["de-escalate", "safety", "wellness", "crisis"],
        recommended_count=14,
    ),
    TrainingTrack(
        "wilderness_sar",
        "Wilderness & Search and Rescue",
        "Lost hiker, avalanche, flood rescue, remote injury.",
        domains=["wilderness", "search_rescue", "water_safety", "weather"],
        skills=["wilderness", "search-rescue", "water-safety"],
        keywords=["trail", "rescue", "lost", "avalanche"],
        recommended_count=14,
    ),
    TrainingTrack(
        "transport_security",
        "Transport & Public Security",
        "Driving emergencies, active threat, evacuation, crowd control.",
        domains=["transport", "security", "fire_safety"],
        skills=["transport-safety", "security", "fire-safety"],
        keywords=["evacuate", "threat", "vehicle", "exit"],
        recommended_count=14,
    ),
    TrainingTrack(
        "food_retail_ops",
        "Food & Retail Operations",
        "Outbreak signals, slips, robberies, recalls on the floor.",
        domains=["food_safety", "retail", "hospitality"],
        skills=["food-safety", "retail", "hospitality"],
        keywords=["customer", "kitchen", "recall", "store"],
        recommended_count=12,
    ),
    TrainingTrack(
        "sports_coach",
        "Sports Coach Sideline Safety",
        "Concussion, heat, lightning, spinal precautions.",
        domains=["sports"],
        skills=["sports-safety", "first-aid"],
        keywords=["athlete", "concussion", "heat", "sideline"],
        recommended_count=10,
    ),
    TrainingTrack(
        "aviation_ifr_advanced",
        "IFR & Instrument Emergencies",
        "Partial panel, icing on approach, missed approach fuel, terrain warnings.",
        domains=["aviation_ifr"],
        skills=["ifr", "aviation"],
        keywords=["ifr", "approach", "icing", "terrain"],
        recommended_count=12,
    ),
    TrainingTrack(
        "road_safety",
        "Road & Vehicle Safety",
        "Car, motorcycle, truck, and bus emergencies — control, signal, escape.",
        domains=["road"],
        skills=["road-safety", "defensive-driving", "commercial-driving", "motorcycle-safety"],
        keywords=["brake", "tire", "skid", "lane", "vehicle"],
        recommended_count=24,
    ),
    TrainingTrack(
        "rail_safety",
        "Rail & Transit Safety",
        "Train operator and subway/passenger safety — tracks, crossings, evacuation.",
        domains=["rail"],
        skills=["rail-safety", "transit-safety"],
        keywords=["track", "platform", "crossing", "tunnel"],
        recommended_count=18,
    ),
    TrainingTrack(
        "micromobility_safety",
        "Bicycle & Scooter Safety",
        "Cycling and e-scooter hazards — dooring, hooks, surfaces, braking.",
        domains=["micromobility"],
        skills=["cycling-safety", "micromobility-safety"],
        keywords=["bike", "scooter", "dooring", "lane"],
        recommended_count=18,
    ),
    TrainingTrack(
        "marine_recreation",
        "Boating & Water Recreation Safety",
        "Boats, jet skis, paddle craft — overboard, capsize, current, rescue.",
        domains=["marine", "water_safety"],
        skills=["marine-safety", "water-safety", "water-rescue"],
        keywords=["boat", "overboard", "capsize", "current"],
        recommended_count=18,
    ),
    TrainingTrack(
        "pedestrian_safety",
        "Pedestrian Safety",
        "Crosswalks, distracted walking, low visibility, protecting children.",
        domains=["pedestrian"],
        skills=["pedestrian-safety", "situational-awareness"],
        keywords=["crosswalk", "pedestrian", "walk", "curb"],
        recommended_count=14,
    ),
    TrainingTrack(
        "police_public_safety",
        "Police & Public-Safety Officer",
        "Stops, welfare checks, crisis, de-escalation, active threats.",
        domains=["police"],
        skills=["public-safety", "de-escalation", "crisis-response"],
        keywords=["stop", "suspect", "de-escalate", "officer"],
        recommended_count=16,
    ),
    TrainingTrack(
        "school_community_safety",
        "Student & Teacher Safety",
        "Lockdowns, medical events, bullying, strangers, evacuations — for students and staff.",
        domains=["school_safety", "education", "child_safety"],
        skills=["student-safety", "teacher-safety", "classroom-management"],
        keywords=["lockdown", "student", "school", "bully"],
        recommended_count=20,
    ),
)


def list_tracks() -> List[TrainingTrack]:
    return list(TRAINING_TRACKS)


def get_track(track_id: str) -> Optional[TrainingTrack]:
    for t in TRAINING_TRACKS:
        if t.track_id == track_id:
            return t
    return None


def track_to_dict(track: TrainingTrack) -> dict:
    return {
        "track_id": track.track_id,
        "title": track.title,
        "description": track.description,
        "domains": track.domains,
        "skills": track.skills,
        "keywords": track.keywords,
        "recommended_count": track.recommended_count,
    }
