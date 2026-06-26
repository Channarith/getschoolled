"""Extended arcade content: Bananagrams-style tiles, resource/dependency sims,
RPG scenarios, cartoon morals, etiquette, idioms, creation, learn-by-doing,
farm sim, geometry, and spelling — localized via games_i18n."""

from __future__ import annotations

from typing import Dict, List, Optional

from .games import AgeGroup

# Each entry: subjects, game_types, ages (optional filter), content fields.
_EXTENDED_RAW: List[dict] = [
    # --- Word tiles (Bananagrams-style) ------------------------------------ #
    {
        "content_id": "tiles_wp_01", "subjects": ["wordplay"], "game_types": ["tiles"],
        "prompt": "Tiles: B A N A N A — which word can you spell?",
        "options": ["banana", "nab", "band", "cab"], "answer_index": 0,
        "explain": "All six letters spell banana.",
        "meta": {"letters": "BANANA", "style": "tiles"},
        "kind": "tiles",
    },
    {
        "content_id": "tiles_wp_02", "subjects": ["wordplay"], "game_types": ["tiles"],
        "prompt": "Tiles: T E A C H — pick a valid word.",
        "options": ["teach", "each", "heat", "All of the above"], "answer_index": 3,
        "explain": "teach, each, and heat all fit.",
        "meta": {"letters": "TEACH", "style": "tiles"},
        "kind": "tiles",
    },
    {
        "content_id": "tiles_wp_03", "subjects": ["wordplay", "spelling"], "game_types": ["tiles"],
        "prompt": "Tiles: S T A R — longest word you can make?",
        "options": ["star", "rats", "arts", "star and arts"], "answer_index": 3,
        "explain": "star and arts both use four letters.",
        "meta": {"letters": "STAR", "style": "tiles"},
        "kind": "tiles",
    },
    # --- Spelling ------------------------------------------------------------ #
    {
        "content_id": "spell_01", "subjects": ["wordplay"], "game_types": ["spelling"],
        "prompt": "Which spelling is correct?",
        "options": ["receive", "recieve", "receve", "receeve"], "answer_index": 0,
        "explain": "i before e except after c — receive.",
        "kind": "spelling",
    },
    {
        "content_id": "spell_02", "subjects": ["wordplay"], "game_types": ["spelling"],
        "prompt": "Pick the right spelling:",
        "options": ["necessary", "neccessary", "necesary", "neccesary"], "answer_index": 0,
        "explain": "One c, two s's — necessary.",
        "kind": "spelling",
    },
    {
        "content_id": "spell_03", "subjects": ["wordplay"], "game_types": ["spelling"],
        "prompt": "Which word is spelled correctly?",
        "options": ["accommodate", "acommodate", "accomodate", "accomadate"], "answer_index": 0,
        "explain": "Double c and double m in accommodate.",
        "kind": "spelling",
    },
    # --- Idioms & slang ------------------------------------------------------ #
    {
        "content_id": "idiom_01", "subjects": ["wordplay"], "game_types": ["idiom"],
        "prompt": "What does \"break the ice\" mean?",
        "options": ["Start a conversation", "Freeze water", "Break a cup", "Leave early"],
        "answer_index": 0,
        "explain": "It means to ease tension and start talking.",
        "kind": "idiom",
    },
    {
        "content_id": "idiom_02", "subjects": ["wordplay"], "game_types": ["idiom"],
        "prompt": "\"Piece of cake\" means…",
        "options": ["Very easy", "A dessert recipe", "A broken plate", "Sharing food"],
        "answer_index": 0,
        "explain": "Slang for something very easy.",
        "kind": "idiom",
    },
    {
        "content_id": "idiom_03", "subjects": ["wordplay"], "game_types": ["idiom"],
        "prompt": "Someone says \"that's cap\" — they mean…",
        "options": ["That's a lie", "Nice hat", "A bottle top", "A limit"],
        "answer_index": 0,
        "explain": "Modern slang: cap = lie, no cap = truth.",
        "kind": "idiom",
    },
    # --- Resource constraint ------------------------------------------------- #
    {
        "content_id": "res_farm_01", "subjects": ["farming", "life_growth"], "game_types": ["resource"],
        "prompt": "You have 10 coins, 1 worker, and 1 day. Best first move?",
        "options": ["Buy seeds", "Buy a second worker", "Decorate the barn", "Save all coins"],
        "answer_index": 0,
        "explain": "Seeds start production; decoration can wait.",
        "meta": {"coins": 10, "workers": 1, "days": 1},
        "kind": "resource",
    },
    {
        "content_id": "res_sci_01", "subjects": ["science", "farming"], "game_types": ["resource"],
        "prompt": "Lab budget: $100. Need data for a plant experiment. Spend on?",
        "options": ["Soil + seeds + light", "Fancy posters", "Extra chairs", "Nothing — wait"],
        "answer_index": 0,
        "explain": "Materials that produce measurable results first.",
        "meta": {"budget": 100},
        "kind": "resource",
    },
    {
        "content_id": "res_life_01", "subjects": ["life_growth"], "game_types": ["resource"],
        "prompt": "Saturday: 3 hours free, tired, homework due Monday. Best plan?",
        "options": ["45 min rest, then study blocks", "Play all day", "All-nighter Sunday", "Ignore homework"],
        "answer_index": 0,
        "explain": "Rest + spaced study beats cramming.",
        "kind": "resource",
    },
    # --- Dependency / order -------------------------------------------------- #
    {
        "content_id": "dep_prog_01", "subjects": ["programming", "technology"], "game_types": ["dependency"],
        "prompt": "To bake a web page: what comes first?",
        "options": ["Write HTML structure", "Add CSS polish", "Deploy to server", "Share link"],
        "answer_index": 0,
        "explain": "Structure before style; deploy after it works.",
        "meta": {"steps": ["HTML", "CSS", "Test", "Deploy"]},
        "kind": "dependency",
    },
    {
        "content_id": "dep_sci_01", "subjects": ["science", "chemistry"], "game_types": ["dependency"],
        "prompt": "Scientific method — first step?",
        "options": ["Ask a question", "Publish results", "Win a prize", "Ignore data"],
        "answer_index": 0,
        "explain": "Questions drive hypotheses and experiments.",
        "kind": "dependency",
    },
    {
        "content_id": "dep_life_01", "subjects": ["life_growth", "etiquette"], "game_types": ["dependency"],
        "prompt": "Before borrowing a friend's game, you should…",
        "options": ["Ask permission", "Take it quietly", "Lend it to others", "Sell it"],
        "answer_index": 0,
        "explain": "Ask first — respect builds trust.",
        "kind": "dependency",
    },
    # --- RPG / life growth --------------------------------------------------- #
    {
        "content_id": "rpg_life_01", "subjects": ["life_growth"], "game_types": ["rpg"],
        "prompt": "Your character failed a test. Best response?",
        "options": ["Review mistakes and ask for help", "Hide the paper", "Blame the teacher", "Quit school"],
        "answer_index": 0,
        "explain": "Growth mindset: learn from errors.",
        "meta": {"scene": "classroom", "avatar": "student"},
        "kind": "rpg",
    },
    {
        "content_id": "rpg_life_02", "subjects": ["life_growth", "history"], "game_types": ["rpg"],
        "prompt": "Team project: one member is quiet. You…",
        "options": ["Invite their ideas kindly", "Ignore them", "Do everything alone", "Complain to the teacher"],
        "answer_index": 0,
        "explain": "Inclusion helps the team and builds empathy.",
        "kind": "rpg",
    },
    {
        "content_id": "rpg_hist_01", "subjects": ["history"], "game_types": ["rpg"],
        "prompt": "You are a citizen in 1776. A fair leader should…",
        "options": ["Listen to the people", "Rule alone forever", "Ignore laws", "Hide information"],
        "answer_index": 0,
        "explain": "Representation and consent matter in democracy.",
        "kind": "rpg",
    },
    # --- Cartoon clips (scene + moral / STEM) -------------------------------- #
    {
        "content_id": "toon_moral_01", "subjects": ["life_growth"], "game_types": ["cartoon"],
        "prompt": "Scene: A fox tricks birds to drop their food, then eats alone. Moral?",
        "options": ["Cheating hurts trust", "Sharing is weak", "Tricks are always smart", "Birds should fly faster"],
        "answer_index": 0,
        "explain": "Dishonesty may win once but breaks relationships.",
        "meta": {"scene": "forest", "clip_hint": "trickster_fable", "focus": "moral"},
        "kind": "cartoon",
    },
    {
        "content_id": "toon_math_01", "subjects": ["math", "science"], "game_types": ["cartoon"],
        "prompt": "Cartoon: 3 friends share 12 cookies equally. Each gets…",
        "options": ["4", "3", "6", "12"], "answer_index": 0,
        "explain": "12 ÷ 3 = 4 cookies each.",
        "meta": {"scene": "kitchen", "focus": "math"},
        "kind": "cartoon",
    },
    {
        "content_id": "toon_sci_01", "subjects": ["science", "biology"], "game_types": ["cartoon"],
        "prompt": "Clip: Plant in dark closet vs sunny window. Sunny plant grows because…",
        "options": ["Photosynthesis needs light", "Plants fear dark", "Water stops in dark", "Roots sleep"],
        "answer_index": 0,
        "explain": "Light powers photosynthesis.",
        "meta": {"scene": "greenhouse", "focus": "science"},
        "kind": "cartoon",
    },
    # --- Etiquette & responsibilities ---------------------------------------- #
    {
        "content_id": "etiq_01", "subjects": ["etiquette"], "game_types": ["quiz", "doing", "rpg"],
        "prompt": "At a dinner table, where does your napkin go when you leave briefly?",
        "options": ["Loosely on your chair", "On the plate", "On the floor", "In your pocket"],
        "answer_index": 0,
        "explain": "Chair = returning; plate = finished.",
        "kind": "doing",
    },
    {
        "content_id": "etiq_02", "subjects": ["etiquette", "life_growth"], "game_types": ["doing", "rpg"],
        "prompt": "You receive a gift you already own. Polite reply?",
        "options": ["Thank them warmly", "Say it's duplicate loudly", "Return it immediately", "Ignore it"],
        "answer_index": 0,
        "explain": "Gratitude matters more than the item.",
        "kind": "doing",
    },
    {
        "content_id": "etiq_03", "subjects": ["etiquette"], "game_types": ["doing"],
        "prompt": "Group chat: someone shares bad news. You should…",
        "options": ["Respond with care", "Post jokes", "Share to others", "Leave the chat"],
        "answer_index": 0,
        "explain": "Kindness and privacy show digital manners.",
        "kind": "doing",
    },
    # --- Creation / recognition ---------------------------------------------- #
    {
        "content_id": "create_art_01", "subjects": ["creation", "art"], "game_types": ["create"],
        "prompt": "A student mixes red + yellow paint. What did they create?",
        "options": ["Orange", "Purple", "Green", "Brown"], "answer_index": 0,
        "explain": "Primary red + yellow = orange.",
        "meta": {"built": "orange paint"},
        "kind": "create",
    },
    {
        "content_id": "create_tech_01", "subjects": ["creation", "programming"], "game_types": ["create"],
        "prompt": "Code outputs \"Hello, world!\". What was built?",
        "options": ["A first program", "A virus", "A database", "A robot arm"],
        "answer_index": 0,
        "explain": "Hello world is the classic starter program.",
        "kind": "create",
    },
    {
        "content_id": "create_sci_01", "subjects": ["creation", "science"], "game_types": ["create"],
        "prompt": "Vinegar + baking soda bubbles. You created…",
        "options": ["Carbon dioxide gas", "Gold", "Electricity", "A new element"],
        "answer_index": 0,
        "explain": "Acid-base reaction releases CO₂ bubbles.",
        "kind": "create",
    },
    # --- Learn by doing ------------------------------------------------------ #
    {
        "content_id": "doing_math_01", "subjects": ["math"], "game_types": ["doing"],
        "prompt": "Fold paper in half twice, cut one corner. Unfold — you practiced…",
        "options": ["Symmetry", "Spelling", "History dates", "Cooking"],
        "answer_index": 0,
        "explain": "Folding shows mirror symmetry.",
        "meta": {"steps": ["fold", "fold", "cut", "unfold"]},
        "kind": "doing",
    },
    {
        "content_id": "doing_chem_01", "subjects": ["chemistry"], "game_types": ["doing"],
        "prompt": "First safe step when mixing household cleaners?",
        "options": ["Read labels — never mix blindly", "Mix everything", "Close your eyes", "Heat on stove"],
        "answer_index": 0,
        "explain": "Some mixes release toxic gas.",
        "kind": "doing",
    },
    # --- Farm sim / character teaching subject ------------------------------- #
    {
        "content_id": "farm_math_01", "subjects": ["farming", "math"], "game_types": ["farm"],
        "prompt": "Farm: 4 rows × 5 plants = how many crops?",
        "options": ["20", "9", "15", "25"], "answer_index": 0,
        "explain": "Multiplication: 4×5=20.",
        "meta": {"crop": "wheat", "character": "farmer"},
        "kind": "farm",
    },
    {
        "content_id": "farm_bio_01", "subjects": ["farming", "biology"], "game_types": ["farm"],
        "prompt": "Your farm character needs healthy soil. Add…",
        "options": ["Compost", "Plastic chips", "Salt only", "Paint"],
        "answer_index": 0,
        "explain": "Compost feeds soil organisms and plants.",
        "meta": {"crop": "tomato"},
        "kind": "farm",
    },
    {
        "content_id": "farm_char_01", "subjects": ["farming", "life_growth"], "game_types": ["farm", "rpg"],
        "prompt": "Create your farmer: trait that helps long-term growth?",
        "options": ["Patience", "Giving up fast", "Ignoring weather", "Wasting water"],
        "answer_index": 0,
        "explain": "Farming and learning both reward patience.",
        "meta": {"character_creation": True},
        "kind": "farm",
    },
    # --- Geometry ------------------------------------------------------------ #
    {
        "content_id": "geo_01", "subjects": ["geometry", "math"], "game_types": ["geometry"],
        "prompt": "A shape with 3 sides and 3 angles is a…",
        "options": ["Triangle", "Square", "Circle", "Pentagon"], "answer_index": 0,
        "explain": "Tri = three; triangle has 3 sides.",
        "kind": "geometry",
    },
    {
        "content_id": "geo_02", "subjects": ["geometry"], "game_types": ["geometry"],
        "prompt": "All corners of a rectangle are…",
        "options": ["90° (right angles)", "45°", "180°", "0°"], "answer_index": 0,
        "explain": "Rectangles have four right angles.",
        "kind": "geometry",
    },
    {
        "content_id": "geo_03", "subjects": ["geometry", "math"], "game_types": ["geometry"],
        "prompt": "Area of a rectangle 3 cm × 4 cm?",
        "options": ["12 cm²", "7 cm²", "12 cm", "14 cm²"], "answer_index": 0,
        "explain": "Area = length × width = 12 square cm.",
        "kind": "geometry",
    },
]

# Spanish + Chinese + Khmer sample translations (pattern for all content IDs).
_TRANSLATION_SEED: Dict[str, Dict[str, Dict[str, str]]] = {
    "tiles_wp_01": {
        "prompt": {
            "es": "Letras: B A N A N A — ¿qué palabra puedes formar?",
            "zh": "字母：B A N A N A — 能拼出什么词？",
            "km": "អក្សរ៖ B A N A N A — អ្នក拼ពាក្យអ្វីបាន?",
        },
        "opt_0": {"es": "banana", "zh": "香蕉 banana", "km": "banana"},
    },
    "idiom_01": {
        "prompt": {
            "es": "¿Qué significa \"break the ice\"?",
            "zh": "“打破僵局”是什么意思？",
            "km": "\"break the ice\" មានន័យយ៉ាងម៉េច?",
        },
        "opt_0": {"es": "Iniciar una conversación", "zh": "开始交谈", "km": "ចាប់ផ្តើមសន្ទនា"},
    },
    "toon_moral_01": {
        "prompt": {
            "es": "Escena: un zorro engaña a los pájaros. ¿Moraleja?",
            "zh": "场景：狐狸骗鸟放下食物。寓意是？",
            "km": "រូបភាព៖ កញ្ជ្រោងបោកបញ្ឆោតបក្សី។ មេរៀន?",
        },
        "opt_0": {"es": "Engañar daña la confianza", "zh": "欺骗伤害信任", "km": "ការបោកបញ្ឆោតធ្វើឱ្យខូចទំនុកចិត្ត"},
    },
    "etiq_01": {
        "prompt": {
            "es": "En la mesa, ¿dónde pones la servilleta al levantarte un momento?",
            "zh": "餐桌上，暂时离开时应把餐巾放在哪里？",
            "km": "តុបាយ របៀបដាក់ក្រណាត់ដៃពេលឈប់បាយបន្តិច?",
        },
        "opt_0": {"es": "Sobre la silla", "zh": "椅子上", "km": "លើកៅអី"},
    },
    "geo_01": {
        "prompt": {
            "es": "Una figura con 3 lados es un…",
            "zh": "有三条边的图形是…",
            "km": "រូបមាន ៣ ជ្រុងគឺ…",
        },
        "opt_0": {"es": "Triángulo", "zh": "三角形", "km": "ត្រីកោណ"},
    },
}


def _load_translations() -> None:
    from . import games_i18n

    for cid, fields in _TRANSLATION_SEED.items():
        for field, locs in fields.items():
            for loc, text in locs.items():
                games_i18n.register_content_translation(cid, field, loc, text)


_load_translations()


def extended_bank(
    subject: str,
    game_type: str,
    age: AgeGroup,
) -> List[dict]:
    """Filter extended content for subject + mode + age tier."""
    age_id = age.value
    out: List[dict] = []
    for row in _EXTENDED_RAW:
        if subject not in row["subjects"]:
            continue
        if game_type not in row["game_types"]:
            continue
        ages = row.get("ages")
        if ages and age_id not in ages:
            continue
        out.append(row)
    # Kids: prefer shorter prompts (first half) when many items
    if age is AgeGroup.KIDS and len(out) > 4:
        out = out[: max(3, len(out) // 2)]
    return out


def extended_bank_for_subject(subject: str, age: AgeGroup) -> List[dict]:
    """All extended items for a subject (quiz/speed fallback on life-skills subjects)."""
    age_id = age.value
    out: List[dict] = []
    for row in _EXTENDED_RAW:
        if subject not in row["subjects"]:
            continue
        ages = row.get("ages")
        if ages and age_id not in ages:
            continue
        out.append(row)
    if age is AgeGroup.KIDS and len(out) > 4:
        out = out[: max(3, len(out) // 2)]
    return out


def subjects_for_extended() -> List[str]:
    seen = set()
    for row in _EXTENDED_RAW:
        for s in row["subjects"]:
            seen.add(s)
    return sorted(seen)
