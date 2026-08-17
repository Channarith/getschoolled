"""SVG sprites and backdrops for food-safety and driving storyboards.

All art is self-contained SVG (no external assets). Sprites are 120×200 viewBox
figures; backdrops are 800×450 stage scenes. Render composes them into an
animated scene with CSS keyframes for motion and camera moves.
"""

from __future__ import annotations


# --------------------------------------------------------------------------
# Sprite builders
# --------------------------------------------------------------------------

def _car(body: str = "#2563eb", roof: str = "#1e40af") -> str:
    return f"""<svg viewBox="0 0 160 90" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <ellipse cx="80" cy="82" rx="55" ry="6" fill="#0b1220" opacity=".3"/>
      <rect x="18" y="38" width="124" height="32" rx="10" fill="{body}"/>
      <path d="M40 38 L55 18 H105 L120 38 Z" fill="{roof}"/>
      <rect x="58" y="22" width="22" height="16" rx="3" fill="#bfdbfe" opacity=".9"/>
      <rect x="84" y="22" width="22" height="16" rx="3" fill="#bfdbfe" opacity=".85"/>
      <circle cx="42" cy="70" r="12" fill="#1f2937"/><circle cx="42" cy="70" r="5" fill="#9ca3af"/>
      <circle cx="118" cy="70" r="12" fill="#1f2937"/><circle cx="118" cy="70" r="5" fill="#9ca3af"/>
      <rect x="128" y="44" width="10" height="8" rx="2" fill="#fef08a"/>
      <rect x="22" y="44" width="8" height="8" rx="2" fill="#fca5a5"/>
    </svg>"""


def _truck(body: str = "#64748b") -> str:
    return f"""<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <ellipse cx="100" cy="92" rx="70" ry="6" fill="#0b1220" opacity=".3"/>
      <rect x="70" y="22" width="110" height="50" rx="4" fill="{body}"/>
      <rect x="18" y="38" width="55" height="34" rx="6" fill="#334155"/>
      <rect x="28" y="44" width="28" height="16" rx="3" fill="#93c5fd"/>
      <circle cx="40" cy="78" r="12" fill="#1f2937"/><circle cx="40" cy="78" r="5" fill="#9ca3af"/>
      <circle cx="100" cy="78" r="12" fill="#1f2937"/><circle cx="100" cy="78" r="5" fill="#9ca3af"/>
      <circle cx="155" cy="78" r="12" fill="#1f2937"/><circle cx="155" cy="78" r="5" fill="#9ca3af"/>
    </svg>"""


def _school_bus() -> str:
    return """<svg viewBox="0 0 220 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <ellipse cx="110" cy="92" rx="80" ry="6" fill="#0b1220" opacity=".3"/>
      <rect x="20" y="28" width="180" height="42" rx="8" fill="#f59e0b"/>
      <rect x="20" y="28" width="180" height="12" rx="6" fill="#d97706"/>
      <rect x="35" y="42" width="22" height="16" rx="2" fill="#1e3a8a"/>
      <rect x="65" y="42" width="22" height="16" rx="2" fill="#1e3a8a"/>
      <rect x="95" y="42" width="22" height="16" rx="2" fill="#1e3a8a"/>
      <rect x="125" y="42" width="22" height="16" rx="2" fill="#1e3a8a"/>
      <rect x="155" y="42" width="28" height="16" rx="2" fill="#93c5fd"/>
      <circle cx="50" cy="78" r="11" fill="#1f2937"/><circle cx="50" cy="78" r="4" fill="#9ca3af"/>
      <circle cx="160" cy="78" r="11" fill="#1f2937"/><circle cx="160" cy="78" r="4" fill="#9ca3af"/>
      <rect x="8" y="48" width="14" height="18" rx="2" fill="#ef4444"/>
      <line x1="15" y1="48" x2="15" y2="28" stroke="#ef4444" stroke-width="3"/>
      <rect x="10" y="22" width="10" height="8" rx="1" fill="#ef4444"/>
    </svg>"""


def _motorcycle() -> str:
    return """<svg viewBox="0 0 140 90" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="30" cy="68" r="16" fill="none" stroke="#1f2937" stroke-width="6"/>
      <circle cx="110" cy="68" r="16" fill="none" stroke="#1f2937" stroke-width="6"/>
      <path d="M30 68 L55 40 L90 40 L110 68" stroke="#334155" stroke-width="5" fill="none"/>
      <rect x="55" y="32" width="35" height="12" rx="4" fill="#dc2626"/>
      <circle cx="90" cy="28" r="8" fill="#fbbf24"/>
    </svg>"""


def _bike() -> str:
    return """<svg viewBox="0 0 140 90" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="32" cy="62" r="18" fill="none" stroke="#1f2937" stroke-width="4"/>
      <circle cx="108" cy="62" r="18" fill="none" stroke="#1f2937" stroke-width="4"/>
      <path d="M32 62 L60 30 L95 30 L108 62 M60 30 L70 62 M95 30 L70 62"
        stroke="#2563eb" stroke-width="3.5" fill="none"/>
      <circle cx="60" cy="28" r="5" fill="#1f2937"/>
    </svg>"""


def _pedestrian(shirt: str = "#3b82f6", pants: str = "#1e3a8a") -> str:
    return f"""<svg viewBox="0 0 80 160" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <ellipse cx="40" cy="152" rx="18" ry="5" fill="#0b1220" opacity=".3"/>
      <circle cx="40" cy="28" r="16" fill="#f6d3ac"/>
      <circle cx="34" cy="26" r="2" fill="#1f2937"/><circle cx="46" cy="26" r="2" fill="#1f2937"/>
      <path d="M34 34 Q40 38 46 34" stroke="#1f2937" stroke-width="1.5" fill="none"/>
      <rect x="26" y="46" width="28" height="40" rx="8" fill="{shirt}"/>
      <rect x="28" y="88" width="10" height="42" rx="4" fill="{pants}"/>
      <rect x="42" y="88" width="10" height="42" rx="4" fill="{pants}"/>
      <rect x="14" y="50" width="10" height="32" rx="4" fill="{shirt}"/>
      <rect x="56" y="50" width="10" height="32" rx="4" fill="{shirt}"/>
    </svg>"""


def _stop_sign() -> str:
    return """<svg viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="46" y="70" width="8" height="60" fill="#6b7280"/>
      <polygon points="50,8 78,22 92,50 78,78 50,92 22,78 8,50 22,22" fill="#dc2626" stroke="#fff" stroke-width="3"/>
      <text x="50" y="56" text-anchor="middle" font-family="Arial Black,Arial,sans-serif"
        font-size="18" font-weight="800" fill="#fff">STOP</text>
    </svg>"""


def _yield_sign() -> str:
    return """<svg viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="46" y="78" width="8" height="52" fill="#6b7280"/>
      <polygon points="50,10 90,78 10,78" fill="#fff" stroke="#dc2626" stroke-width="6"/>
      <text x="50" y="68" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="12" font-weight="800" fill="#dc2626">YIELD</text>
    </svg>"""


def _speed_sign(mph: str = "25") -> str:
    return f"""<svg viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="46" y="78" width="8" height="52" fill="#6b7280"/>
      <rect x="18" y="8" width="64" height="72" rx="8" fill="#fff" stroke="#1f2937" stroke-width="4"/>
      <text x="50" y="38" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="11" font-weight="700" fill="#1f2937">SPEED</text>
      <text x="50" y="58" text-anchor="middle" font-family="Arial Black,Arial,sans-serif"
        font-size="22" font-weight="800" fill="#1f2937">{mph}</text>
      <text x="50" y="72" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="10" fill="#1f2937">LIMIT</text>
    </svg>"""


def _warning_sign(symbol: str = "⚠") -> str:
    return f"""<svg viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="46" y="78" width="8" height="52" fill="#6b7280"/>
      <polygon points="50,8 92,78 8,78" fill="#facc15" stroke="#1f2937" stroke-width="3"/>
      <text x="50" y="62" text-anchor="middle" font-size="28">{symbol}</text>
    </svg>"""


def _traffic_light(state: str = "red") -> str:
    r = "#ef4444" if state == "red" else "#7f1d1d"
    y = "#facc15" if state == "yellow" else "#713f12"
    g = "#22c55e" if state == "green" else "#14532d"
    return f"""<svg viewBox="0 0 60 140" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="26" y="100" width="8" height="36" fill="#6b7280"/>
      <rect x="10" y="8" width="40" height="96" rx="8" fill="#1f2937"/>
      <circle cx="30" cy="30" r="10" fill="{r}"/>
      <circle cx="30" cy="56" r="10" fill="{y}"/>
      <circle cx="30" cy="82" r="10" fill="{g}"/>
    </svg>"""


def _crosswalk_mark() -> str:
    return """<svg viewBox="0 0 200 40" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="0" y="4" width="18" height="32" fill="#fff" opacity=".9"/>
      <rect x="28" y="4" width="18" height="32" fill="#fff" opacity=".9"/>
      <rect x="56" y="4" width="18" height="32" fill="#fff" opacity=".9"/>
      <rect x="84" y="4" width="18" height="32" fill="#fff" opacity=".9"/>
      <rect x="112" y="4" width="18" height="32" fill="#fff" opacity=".9"/>
      <rect x="140" y="4" width="18" height="32" fill="#fff" opacity=".9"/>
      <rect x="168" y="4" width="18" height="32" fill="#fff" opacity=".9"/>
    </svg>"""


def _thermometer(temp_label: str = "165°") -> str:
    return f"""<svg viewBox="0 0 60 160" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="22" y="10" width="16" height="100" rx="8" fill="#e5e7eb" stroke="#6b7280" stroke-width="2"/>
      <rect x="26" y="40" width="8" height="70" rx="4" fill="#ef4444"/>
      <circle cx="30" cy="128" r="18" fill="#ef4444" stroke="#6b7280" stroke-width="2"/>
      <text x="30" y="155" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="14" font-weight="700" fill="#1f2937">{temp_label}</text>
    </svg>"""


def _fridge() -> str:
    return """<svg viewBox="0 0 100 160" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="10" y="8" width="80" height="140" rx="8" fill="#94a3b8" stroke="#475569" stroke-width="2"/>
      <rect x="16" y="14" width="68" height="55" rx="4" fill="#cbd5e1"/>
      <rect x="16" y="78" width="68" height="62" rx="4" fill="#cbd5e1"/>
      <rect x="70" y="30" width="6" height="20" rx="2" fill="#64748b"/>
      <rect x="70" y="100" width="6" height="20" rx="2" fill="#64748b"/>
      <text x="50" y="48" text-anchor="middle" font-size="11" fill="#1e40af" font-weight="700">41°F</text>
    </svg>"""


def _stove() -> str:
    return """<svg viewBox="0 0 120 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="8" y="30" width="104" height="60" rx="6" fill="#374151"/>
      <circle cx="35" cy="55" r="16" fill="#1f2937" stroke="#6b7280" stroke-width="3"/>
      <circle cx="85" cy="55" r="16" fill="#1f2937" stroke="#6b7280" stroke-width="3"/>
      <circle cx="35" cy="55" r="6" fill="#f97316" opacity=".8">
        <animate attributeName="opacity" values=".4;1;.4" dur="1.2s" repeatCount="indefinite"/>
      </circle>
      <circle cx="85" cy="55" r="6" fill="#f97316" opacity=".7"/>
      <rect x="20" y="8" width="80" height="22" rx="4" fill="#9ca3af"/>
    </svg>"""


def _sink() -> str:
    return """<svg viewBox="0 0 140 90" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="10" y="30" width="120" height="50" rx="8" fill="#94a3b8"/>
      <ellipse cx="70" cy="55" rx="45" ry="18" fill="#67e8f9" opacity=".55"/>
      <rect x="62" y="8" width="16" height="28" rx="4" fill="#64748b"/>
      <circle cx="70" cy="10" r="8" fill="#94a3b8"/>
      <path d="M70 18 Q90 30 85 45" stroke="#38bdf8" stroke-width="4" fill="none" opacity=".8">
        <animate attributeName="opacity" values=".3;1;.3" dur="1s" repeatCount="indefinite"/>
      </path>
    </svg>"""


def _cutting_board() -> str:
    return """<svg viewBox="0 0 140 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="8" y="12" width="124" height="56" rx="8" fill="#d6a56a"/>
      <rect x="20" y="24" width="50" height="32" rx="4" fill="#fca5a5" opacity=".85"/>
      <rect x="78" y="28" width="40" height="24" rx="4" fill="#86efac" opacity=".9"/>
      <text x="45" y="46" text-anchor="middle" font-size="10" fill="#7f1d1d" font-weight="700">RAW</text>
      <text x="98" y="46" text-anchor="middle" font-size="10" fill="#14532d" font-weight="700">RTE</text>
    </svg>"""


def _soap_bottle() -> str:
    return """<svg viewBox="0 0 60 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="18" y="28" width="24" height="70" rx="6" fill="#38bdf8"/>
      <rect x="22" y="12" width="16" height="20" rx="3" fill="#0ea5e9"/>
      <circle cx="30" cy="10" r="6" fill="#0284c7"/>
      <text x="30" y="70" text-anchor="middle" font-size="10" fill="#fff" font-weight="700">SOAP</text>
    </svg>"""


def _glove() -> str:
    return """<svg viewBox="0 0 80 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <ellipse cx="40" cy="55" rx="22" ry="30" fill="#f8fafc" stroke="#94a3b8" stroke-width="2"/>
      <rect x="28" y="78" width="24" height="16" rx="4" fill="#e2e8f0"/>
      <rect x="18" y="30" width="8" height="28" rx="3" fill="#f8fafc" stroke="#94a3b8"/>
      <rect x="28" y="22" width="8" height="30" rx="3" fill="#f8fafc" stroke="#94a3b8"/>
      <rect x="38" y="20" width="8" height="30" rx="3" fill="#f8fafc" stroke="#94a3b8"/>
      <rect x="48" y="24" width="8" height="28" rx="3" fill="#f8fafc" stroke="#94a3b8"/>
    </svg>"""


def _plate_food() -> str:
    return """<svg viewBox="0 0 100 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <ellipse cx="50" cy="48" rx="40" ry="22" fill="#f1f5f9" stroke="#94a3b8" stroke-width="3"/>
      <ellipse cx="40" cy="44" rx="12" ry="8" fill="#f97316"/>
      <ellipse cx="58" cy="42" rx="10" ry="7" fill="#22c55e"/>
      <ellipse cx="52" cy="52" rx="14" ry="6" fill="#eab308"/>
    </svg>"""


def _pest() -> str:
    return """<svg viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <ellipse cx="30" cy="22" rx="16" ry="10" fill="#78716c"/>
      <circle cx="42" cy="18" r="7" fill="#57534e"/>
      <line x1="14" y1="16" x2="4" y2="8" stroke="#57534e" stroke-width="2"/>
      <line x1="14" y1="22" x2="2" y2="22" stroke="#57534e" stroke-width="2"/>
      <line x1="14" y1="28" x2="4" y2="34" stroke="#57534e" stroke-width="2"/>
      <line x1="46" y1="16" x2="56" y2="8" stroke="#57534e" stroke-width="2"/>
      <line x1="46" y1="22" x2="58" y2="22" stroke="#57534e" stroke-width="2"/>
      <line x1="46" y1="28" x2="56" y2="34" stroke="#57534e" stroke-width="2"/>
    </svg>"""


def _ambulance() -> str:
    return """<svg viewBox="0 0 180 90" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="20" y="30" width="140" height="40" rx="6" fill="#f8fafc" stroke="#dc2626" stroke-width="3"/>
      <rect x="20" y="30" width="40" height="40" rx="6" fill="#dc2626"/>
      <rect x="70" y="38" width="24" height="8" fill="#dc2626"/>
      <rect x="78" y="30" width="8" height="24" fill="#dc2626"/>
      <circle cx="50" cy="78" r="10" fill="#1f2937"/><circle cx="130" cy="78" r="10" fill="#1f2937"/>
      <rect x="145" y="18" width="14" height="10" rx="2" fill="#ef4444">
        <animate attributeName="opacity" values="1;0.2;1" dur="0.6s" repeatCount="indefinite"/>
      </rect>
    </svg>"""


def _phone_ban() -> str:
    return """<svg viewBox="0 0 80 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="22" y="8" width="36" height="70" rx="6" fill="#1f2937"/>
      <rect x="26" y="14" width="28" height="50" rx="2" fill="#38bdf8"/>
      <circle cx="40" cy="70" r="3" fill="#9ca3af"/>
      <circle cx="40" cy="50" r="28" fill="none" stroke="#ef4444" stroke-width="5"/>
      <line x1="20" y1="30" x2="60" y2="70" stroke="#ef4444" stroke-width="5"/>
    </svg>"""


def _cone() -> str:
    return """<svg viewBox="0 0 60 90" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <polygon points="30,8 52,78 8,78" fill="#f97316"/>
      <rect x="18" y="28" width="24" height="8" fill="#fff"/>
      <rect x="14" y="48" width="32" height="8" fill="#fff"/>
      <ellipse cx="30" cy="82" rx="26" ry="6" fill="#1f2937" opacity=".35"/>
    </svg>"""


def _guide_sign() -> str:
    return """<svg viewBox="0 0 160 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="8" y="10" width="144" height="56" rx="6" fill="#15803d" stroke="#fff" stroke-width="3"/>
      <text x="80" y="44" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="16" font-weight="700" fill="#fff">EXIT 12 →</text>
    </svg>"""


SPRITES: dict[str, str] = {
    "car": _car(),
    "car-blue": _car("#2563eb", "#1e40af"),
    "car-red": _car("#dc2626", "#991b1b"),
    "car-green": _car("#16a34a", "#166534"),
    "car-white": _car("#f8fafc", "#cbd5e1"),
    "truck": _truck(),
    "school-bus": _school_bus(),
    "motorcycle": _motorcycle(),
    "bike": _bike(),
    "pedestrian": _pedestrian(),
    "pedestrian-yellow": _pedestrian("#eab308", "#854d0e"),
    "pedestrian-red": _pedestrian("#ef4444", "#7f1d1d"),
    "adult": _pedestrian("#2563eb", "#1e3a8a"),
    "teen": _pedestrian("#8b5cf6", "#4c1d95"),
    "child": _pedestrian("#f59e0b", "#92400e"),
    "stop-sign": _stop_sign(),
    "sign-stop": _stop_sign(),
    "yield-sign": _yield_sign(),
    "sign-yield": _yield_sign(),
    "speed-25": _speed_sign("25"),
    "speed-65": _speed_sign("65"),
    "sign-speed": _speed_sign("25"),
    "warning-sign": _warning_sign("⚠"),
    "sign-warning": _warning_sign("⚠"),
    "sign-curve": _warning_sign("⤴"),
    "sign-rail": _warning_sign("🚂"),
    "sign-work": _warning_sign("🚧"),
    "sign-bike": _warning_sign("🚲"),
    "school-sign": _warning_sign("🏫"),
    "sign-school": _warning_sign("🏫"),
    "sign-guide": _guide_sign(),
    "sign-do-not-enter": _warning_sign("⛔"),
    "sign-one-way": _warning_sign("➡"),
    "sign-no-turn": _warning_sign("↺"),
    "traffic-light": _traffic_light("red"),
    "traffic-light-red": _traffic_light("red"),
    "traffic-light-green": _traffic_light("green"),
    "traffic-light-yellow": _traffic_light("yellow"),
    "crosswalk": _crosswalk_mark(),
    "cone": _cone(),
    "thermometer-165": _thermometer("165°"),
    "thermometer-155": _thermometer("155°"),
    "thermometer-145": _thermometer("145°"),
    "thermometer-41": _thermometer("41°"),
    "thermometer-135": _thermometer("135°"),
    "fridge": _fridge(),
    "stove": _stove(),
    "sink": _sink(),
    "cutting-board": _cutting_board(),
    "soap": _soap_bottle(),
    "glove": _glove(),
    "plate": _plate_food(),
    "pest": _pest(),
    "ambulance": _ambulance(),
    "phone-ban": _phone_ban(),
}


# Approximate sprite width % of stage for layout helpers
SPRITE_WIDTH: dict[str, float] = {
    "car": 18, "car-blue": 18, "car-red": 18, "car-green": 18, "car-white": 18,
    "truck": 22, "school-bus": 24, "motorcycle": 14, "bike": 14,
    "pedestrian": 8, "pedestrian-yellow": 8, "pedestrian-red": 8,
    "adult": 8, "teen": 8, "child": 7,
    "stop-sign": 8, "sign-stop": 8, "yield-sign": 8, "sign-yield": 8,
    "speed-25": 8, "speed-65": 8, "sign-speed": 8,
    "warning-sign": 8, "sign-warning": 8, "sign-curve": 8, "sign-rail": 8,
    "sign-work": 8, "sign-bike": 8, "school-sign": 8, "sign-school": 8,
    "sign-guide": 16, "sign-do-not-enter": 8, "sign-one-way": 8, "sign-no-turn": 8,
    "traffic-light": 5, "traffic-light-red": 5, "traffic-light-green": 5,
    "traffic-light-yellow": 5, "crosswalk": 22, "cone": 5,
    "thermometer-165": 5, "thermometer-155": 5,
    "thermometer-145": 5, "thermometer-41": 5, "thermometer-135": 5,
    "fridge": 10, "stove": 12, "sink": 14, "cutting-board": 14,
    "soap": 5, "glove": 7, "plate": 10, "pest": 6, "ambulance": 20,
    "phone-ban": 7,
}


# --------------------------------------------------------------------------
# Backdrops (800×450)
# --------------------------------------------------------------------------

def _backdrop_intersection() -> str:
    return """
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#7dd3fc"/><stop offset="1" stop-color="#e0f2fe"/>
        </linearGradient>
      </defs>
      <rect width="800" height="450" fill="url(#sky)"/>
      <rect y="260" width="800" height="190" fill="#4b5563"/>
      <rect y="340" width="800" height="18" fill="#fbbf24" opacity=".85"/>
      <rect x="0" y="260" width="800" height="8" fill="#9ca3af"/>
      <rect x="380" y="260" width="40" height="190" fill="#6b7280"/>
      <rect x="100" y="160" width="90" height="100" fill="#94a3b8"/>
      <rect x="220" y="140" width="70" height="120" fill="#64748b"/>
      <rect x="520" y="150" width="100" height="110" fill="#78716c"/>
      <rect x="640" y="170" width="80" height="90" fill="#57534e"/>
      <circle cx="700" cy="70" r="36" fill="#fde68a" opacity=".9"/>
    """


def _backdrop_residential() -> str:
    return """
      <defs>
        <linearGradient id="sky2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#93c5fd"/><stop offset="1" stop-color="#dbeafe"/>
        </linearGradient>
      </defs>
      <rect width="800" height="450" fill="url(#sky2)"/>
      <rect y="280" width="800" height="170" fill="#6b7280"/>
      <rect y="350" width="800" height="14" fill="#fbbf24"/>
      <rect x="60" y="180" width="120" height="100" fill="#fca5a5"/>
      <polygon points="60,180 120,130 180,180" fill="#b91c1c"/>
      <rect x="280" y="170" width="130" height="110" fill="#86efac"/>
      <polygon points="280,170 345,120 410,170" fill="#166534"/>
      <rect x="520" y="190" width="110" height="90" fill="#fdba74"/>
      <polygon points="520,190 575,145 630,190" fill="#c2410c"/>
      <circle cx="100" cy="250" r="8" fill="#38bdf8"/>
      <circle cx="320" cy="240" r="8" fill="#38bdf8"/>
    """


def _backdrop_freeway() -> str:
    return """
      <defs>
        <linearGradient id="sky3" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#38bdf8"/><stop offset="1" stop-color="#bae6fd"/>
        </linearGradient>
      </defs>
      <rect width="800" height="450" fill="url(#sky3)"/>
      <rect y="200" width="800" height="250" fill="#374151"/>
      <rect y="300" width="800" height="16" fill="#fbbf24"/>
      <rect y="220" width="800" height="6" fill="#9ca3af" opacity=".6"/>
      <rect y="400" width="800" height="6" fill="#9ca3af" opacity=".6"/>
      <polygon points="0,200 800,200 800,180 0,160" fill="#4ade80" opacity=".35"/>
    """


def _backdrop_school_zone() -> str:
    return """
      <defs>
        <linearGradient id="sky4" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#a5b4fc"/><stop offset="1" stop-color="#e0e7ff"/>
        </linearGradient>
      </defs>
      <rect width="800" height="450" fill="url(#sky4)"/>
      <rect y="270" width="800" height="180" fill="#57534e"/>
      <rect x="200" y="360" width="400" height="40" fill="#fff" opacity=".85"/>
      <rect x="220" y="360" width="30" height="40" fill="#1f2937"/>
      <rect x="280" y="360" width="30" height="40" fill="#1f2937"/>
      <rect x="340" y="360" width="30" height="40" fill="#1f2937"/>
      <rect x="400" y="360" width="30" height="40" fill="#1f2937"/>
      <rect x="460" y="360" width="30" height="40" fill="#1f2937"/>
      <rect x="520" y="360" width="30" height="40" fill="#1f2937"/>
      <rect x="80" y="120" width="220" height="150" fill="#fbbf24"/>
      <rect x="100" y="150" width="40" height="40" fill="#1e3a8a"/>
      <rect x="160" y="150" width="40" height="40" fill="#1e3a8a"/>
      <rect x="220" y="150" width="40" height="40" fill="#1e3a8a"/>
      <rect x="160" y="210" width="50" height="60" fill="#78350f"/>
      <text x="190" y="110" text-anchor="middle" font-size="22" font-weight="700" fill="#1e3a8a">SCHOOL</text>
    """


def _backdrop_kitchen() -> str:
    return """
      <defs>
        <linearGradient id="kit" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#f8fafc"/><stop offset="1" stop-color="#e2e8f0"/>
        </linearGradient>
      </defs>
      <rect width="800" height="450" fill="url(#kit)"/>
      <rect y="0" width="800" height="80" fill="#cbd5e1"/>
      <rect y="320" width="800" height="130" fill="#94a3b8"/>
      <rect y="300" width="800" height="24" fill="#64748b"/>
      <rect x="40" y="100" width="200" height="200" rx="8" fill="#e2e8f0" stroke="#94a3b8" stroke-width="3"/>
      <rect x="560" y="100" width="200" height="200" rx="8" fill="#e2e8f0" stroke="#94a3b8" stroke-width="3"/>
      <circle cx="700" cy="40" r="18" fill="#fef08a"/>
      <circle cx="100" cy="40" r="14" fill="#fef08a" opacity=".7"/>
    """


def _backdrop_cold_storage() -> str:
    return """
      <defs>
        <linearGradient id="cold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#e0f2fe"/><stop offset="1" stop-color="#bae6fd"/>
        </linearGradient>
      </defs>
      <rect width="800" height="450" fill="url(#cold)"/>
      <rect x="60" y="60" width="280" height="330" rx="12" fill="#94a3b8" stroke="#475569" stroke-width="4"/>
      <rect x="80" y="80" width="240" height="100" rx="6" fill="#cbd5e1"/>
      <rect x="80" y="200" width="240" height="100" rx="6" fill="#cbd5e1"/>
      <rect x="80" y="320" width="240" height="50" rx="6" fill="#67e8f9" opacity=".5"/>
      <rect x="460" y="80" width="280" height="300" rx="12" fill="#64748b"/>
      <text x="200" y="140" text-anchor="middle" font-size="28" font-weight="700" fill="#0c4a6e">≤ 41°F</text>
      <text x="600" y="240" text-anchor="middle" font-size="22" fill="#e0f2fe">RAW BELOW RTE</text>
    """


def _backdrop_prep_station() -> str:
    return """
      <rect width="800" height="450" fill="#f1f5f9"/>
      <rect y="280" width="800" height="170" fill="#a8a29e"/>
      <rect y="260" width="800" height="28" fill="#78716c"/>
      <rect x="80" y="100" width="280" height="160" rx="10" fill="#d6a56a"/>
      <rect x="440" y="100" width="280" height="160" rx="10" fill="#86efac" opacity=".5"/>
      <text x="220" y="190" text-anchor="middle" font-size="24" font-weight="700" fill="#7c2d12">RAW ZONE</text>
      <text x="580" y="190" text-anchor="middle" font-size="24" font-weight="700" fill="#14532d">RTE ZONE</text>
    """


def _backdrop_night_road() -> str:
    return """
      <rect width="800" height="450" fill="#0f172a"/>
      <circle cx="650" cy="80" r="40" fill="#fef9c3" opacity=".85"/>
      <rect y="260" width="800" height="190" fill="#1e293b"/>
      <rect y="340" width="800" height="12" fill="#fbbf24" opacity=".6"/>
      <rect x="100" y="300" width="40" height="8" fill="#f8fafc" opacity=".4"/>
      <rect x="200" y="300" width="40" height="8" fill="#f8fafc" opacity=".4"/>
      <rect x="300" y="300" width="40" height="8" fill="#f8fafc" opacity=".4"/>
      <rect x="400" y="300" width="40" height="8" fill="#f8fafc" opacity=".4"/>
      <rect x="500" y="300" width="40" height="8" fill="#f8fafc" opacity=".4"/>
      <rect x="600" y="300" width="40" height="8" fill="#f8fafc" opacity=".4"/>
    """


def _backdrop_work_zone() -> str:
    return """
      <rect width="800" height="450" fill="#fef3c7"/>
      <rect y="260" width="800" height="190" fill="#57534e"/>
      <rect y="300" width="800" height="20" fill="#f97316"/>
      <polygon points="100,200 140,260 60,260" fill="#facc15" stroke="#1f2937" stroke-width="3"/>
      <polygon points="200,200 240,260 160,260" fill="#facc15" stroke="#1f2937" stroke-width="3"/>
      <polygon points="300,200 340,260 260,260" fill="#facc15" stroke="#1f2937" stroke-width="3"/>
      <rect x="500" y="140" width="200" height="120" fill="#78716c"/>
      <text x="200" y="245" text-anchor="middle" font-size="14" font-weight="800" fill="#1f2937">WORK</text>
    """


def _backdrop_dock() -> str:
    return """
      <rect width="800" height="450" fill="#e2e8f0"/>
      <rect y="300" width="800" height="150" fill="#94a3b8"/>
      <rect x="40" y="80" width="320" height="220" rx="8" fill="#64748b"/>
      <rect x="60" y="100" width="280" height="160" fill="#1e293b" opacity=".4"/>
      <rect x="420" y="120" width="320" height="180" rx="6" fill="#f8fafc" stroke="#475569" stroke-width="3"/>
      <text x="580" y="220" text-anchor="middle" font-size="22" font-weight="700" fill="#334155">DELIVERY</text>
      <rect x="100" y="320" width="80" height="50" fill="#22c55e" opacity=".7"/>
      <text x="140" y="352" text-anchor="middle" font-size="14" fill="#fff" font-weight="700">OK</text>
    """


BACKDROPS: dict[str, str] = {
    "intersection": _backdrop_intersection(),
    "residential": _backdrop_residential(),
    "freeway": _backdrop_freeway(),
    "school-zone": _backdrop_school_zone(),
    "kitchen": _backdrop_kitchen(),
    "cold-storage": _backdrop_cold_storage(),
    "prep-station": _backdrop_prep_station(),
    "night-road": _backdrop_night_road(),
    "work-zone": _backdrop_work_zone(),
    "dock": _backdrop_dock(),
}
