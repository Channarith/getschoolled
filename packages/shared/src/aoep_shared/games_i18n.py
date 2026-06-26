"""Arcade game UI labels + localized question content.

Hand-written strings for the 14 full catalog locales (see catalog_i18n).
All other platform languages (languages.SUPPORTED_LANGUAGES) fall back to
English via :func:`normalize_locale`.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .catalog_i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, normalize_locale
from .languages import SUPPORTED_LANGUAGES

# Re-export for callers that want the full platform language list.
GAME_CONTENT_LOCALES: tuple[str, ...] = SUPPORTED_LOCALES
GAME_PLATFORM_LANGUAGES: tuple[str, ...] = SUPPORTED_LANGUAGES


def _locales(*pairs: tuple[str, str]) -> Dict[str, str]:
    out = {DEFAULT_LOCALE: pairs[0][1]}
    for code, text in pairs:
        out[code] = text
    return out


# --------------------------------------------------------------------------- #
# Subject display names
# --------------------------------------------------------------------------- #
SUBJECT_LABELS: Dict[str, Dict[str, str]] = {
    "biology": _locales(("en", "Biology"), ("es", "Biología"), ("fr", "Biologie"),
                        ("de", "Biologie"), ("zh", "生物"), ("ja", "生物学"), ("ko", "생물"),
                        ("vi", "Sinh học"), ("km", "ជីវវិទ្យា")),
    "chemistry": _locales(("en", "Chemistry"), ("es", "Química"), ("fr", "Chimie"),
                          ("de", "Chemie"), ("zh", "化学"), ("ja", "化学"), ("ko", "화학"),
                          ("vi", "Hóa học"), ("km", "គីមី")),
    "physics": _locales(("en", "Physics"), ("es", "Física"), ("fr", "Physique"),
                        ("de", "Physik"), ("zh", "物理"), ("ja", "物理学"), ("ko", "물리"),
                        ("vi", "Vật lý"), ("km", "រូបវិទ្យា")),
    "math": _locales(("en", "Math"), ("es", "Matemáticas"), ("fr", "Maths"),
                     ("de", "Mathe"), ("zh", "数学"), ("ja", "数学"), ("ko", "수학"),
                     ("vi", "Toán"), ("km", "គណិតវិទ្យា")),
    "science": _locales(("en", "Science"), ("es", "Ciencia"), ("fr", "Sciences"),
                        ("de", "Wissenschaft"), ("zh", "科学"), ("ja", "科学"), ("ko", "과학"),
                        ("vi", "Khoa học"), ("km", "វិទ្យាសាស្ត្រ")),
    "history": _locales(("en", "History"), ("es", "Historia"), ("fr", "Histoire"),
                        ("de", "Geschichte"), ("zh", "历史"), ("ja", "歴史"), ("ko", "역사"),
                        ("vi", "Lịch sử"), ("km", "ប្រវត្តិ")),
    "art": _locales(("en", "Art"), ("es", "Arte"), ("fr", "Art"),
                    ("de", "Kunst"), ("zh", "艺术"), ("ja", "美術"), ("ko", "예술"),
                    ("vi", "Nghệ thuật"), ("km", "សិល្បៈ")),
    "technology": _locales(("en", "Technology"), ("es", "Tecnología"), ("fr", "Technologie"),
                            ("de", "Technologie"), ("zh", "科技"), ("ja", "テクノロジー"),
                            ("ko", "기술"), ("vi", "Công nghệ"), ("km", "បច្ចេកវិទ្យា")),
    "programming": _locales(("en", "Programming"), ("es", "Programación"), ("fr", "Programmation"),
                             ("de", "Programmierung"), ("zh", "编程"), ("ja", "プログラミング"),
                             ("ko", "프로그래밍"), ("vi", "Lập trình"), ("km", "កម្មវិធី")),
    "life_growth": _locales(("en", "Life & Growth"), ("es", "Vida y crecimiento"),
                            ("fr", "Vie et croissance"), ("de", "Leben & Wachstum"),
                            ("zh", "生活与成长"), ("ja", "人生と成長"), ("ko", "삶과 성장"),
                            ("vi", "Cuộc sống & phát triển"), ("km", "ជីវិត និង ការលូតលាស់")),
    "etiquette": _locales(("en", "Etiquette & Manners"), ("es", "Etiqueta y modales"),
                           ("fr", "Étiquette et manières"), ("de", "Etikette & Manieren"),
                           ("zh", "礼仪与礼貌"), ("ja", "マナーと礼儀"), ("ko", "예절과 매너"),
                           ("vi", "Phép lịch sự"), ("km", "របៀបរស់នៅ")),
    "wordplay": _locales(("en", "Words & Idioms"), ("es", "Palabras e idiomas"),
                          ("fr", "Mots et expressions"), ("de", "Wörter & Redewendungen"),
                          ("zh", "词语与成语"), ("ja", "ことばと慣用句"), ("ko", "단어와 관용구"),
                          ("vi", "Từ ngữ & thành ngữ"), ("km", "ពាក្យ និង សម្រង់ចំណុច")),
    "geometry": _locales(("en", "Geometry"), ("es", "Geometría"), ("fr", "Géométrie"),
                          ("de", "Geometrie"), ("zh", "几何"), ("ja", "幾何学"), ("ko", "기하"),
                          ("vi", "Hình học"), ("km", "ធរណីមាត្រ")),
    "creation": _locales(("en", "Create & Recognize"), ("es", "Crear y reconocer"),
                          ("fr", "Créer et reconnaître"), ("de", "Erstellen & Erkennen"),
                          ("zh", "创造与识别"), ("ja", "作って見分ける"), ("ko", "만들고 알아보기"),
                          ("vi", "Sáng tạo & nhận biết"), ("km", "បង្កើត និង ស្គាល់")),
    "farming": _locales(("en", "Farm & Character"), ("es", "Granja y personaje"),
                         ("fr", "Ferme et personnage"), ("de", "Farm & Charakter"),
                         ("zh", "农场与角色"), ("ja", "農場とキャラ"), ("ko", "농장과 캐릭터"),
                         ("vi", "Nông trại & nhân vật"), ("km", "កសិដ្ឋាន និង តួអង្គ")),
}


# --------------------------------------------------------------------------- #
# Game mode labels
# --------------------------------------------------------------------------- #
GAME_TYPE_LABELS: Dict[str, Dict[str, str]] = {
    "quiz": _locales(("en", "Quiz"), ("es", "Cuestionario"), ("fr", "Quiz"),
                     ("de", "Quiz"), ("zh", "测验"), ("ja", "クイズ"), ("ko", "퀴즈"),
                     ("vi", "Đố vui"), ("km", "ប្រលង")),
    "speed": _locales(("en", "Speed Round"), ("es", "Ronda rápida"), ("fr", "Ronde rapide"),
                      ("de", "Schnellrunde"), ("zh", "速战"), ("ja", "スピード"), ("ko", "스피드"),
                      ("vi", "Tốc độ"), ("km", "លឿន")),
    "match": _locales(("en", "Match"), ("es", "Emparejar"), ("fr", "Associer"),
                      ("de", "Zuordnen"), ("zh", "配对"), ("ja", "マッチ"), ("ko", "매칭"),
                      ("vi", "Ghép cặp"), ("km", "ផ្គូផ្គង")),
    "marathon": _locales(("en", "Marathon"), ("es", "Maratón"), ("fr", "Marathon"),
                          ("de", "Marathon"), ("zh", "马拉松"), ("ja", "マラソン"), ("ko", "마라톤"),
                          ("vi", "Marathon"), ("km", "ម៉ារ៉ាតុង")),
    "tiles": _locales(("en", "Word Tiles"), ("es", "Letras"), ("fr", "Tuiles de mots"),
                      ("de", "Buchstabenspiel"), ("zh", "拼词"), ("ja", "文字タイル"),
                      ("ko", "단어 타일"), ("vi", "Ghép chữ"), ("km", "ពាក្យឡូវ")),
    "resource": _locales(("en", "Resource Choices"), ("es", "Recursos"), ("fr", "Ressources"),
                          ("de", "Ressourcen"), ("zh", "资源抉择"), ("ja", "資源ゲーム"),
                          ("ko", "자원 게임"), ("vi", "Tài nguyên"), ("km", "ធនធាន")),
    "dependency": _locales(("en", "Order & Dependencies"), ("es", "Dependencias"),
                            ("fr", "Dépendances"), ("de", "Abhängigkeiten"), ("zh", "顺序依赖"),
                            ("ja", "順序と依存"), ("ko", "순서와 의존"), ("vi", "Thứ tự"), ("km", "លំដាប់")),
    "rpg": _locales(("en", "Story RPG"), ("es", "RPG de historia"), ("fr", "RPG narratif"),
                    ("de", "Story-RPG"), ("zh", "故事角色扮演"), ("ja", "ストーリーRPG"),
                    ("ko", "스토리 RPG"), ("vi", "RPG kể chuyện"), ("km", "រឿង RPG")),
    "cartoon": _locales(("en", "Cartoon Clips"), ("es", "Dibujos animados"), ("fr", "Dessins animés"),
                         ("de", "Zeichentrick"), ("zh", "卡通短片"), ("ja", "アニメクリップ"),
                         ("ko", "만화 클립"), ("vi", "Hoạt hình"), ("km", "គំនូរជីវចល")),
    "idiom": _locales(("en", "Slang & Idioms"), ("es", "Modismos"), ("fr", "Expressions"),
                       ("de", "Redewendungen"), ("zh", "俚语成语"), ("ja", "慣用句"),
                       ("ko", "관용구"), ("vi", "Thành ngữ"), ("km", "សម្រង់ចំណុច")),
    "create": _locales(("en", "Create & ID"), ("es", "Crear e identificar"), ("fr", "Créer et identifier"),
                        ("de", "Erstellen & erkennen"), ("zh", "创造识别"), ("ja", "作って見分ける"),
                        ("ko", "만들기"), ("vi", "Sáng tạo"), ("km", "បង្កើត")),
    "doing": _locales(("en", "Learn by Doing"), ("es", "Aprender haciendo"), ("fr", "Apprendre en faisant"),
                       ("de", "Lernen durch Tun"), ("zh", "做中学"), ("ja", "やって学ぶ"),
                       ("ko", "실습 학습"), ("vi", "Học qua thực hành"), ("km", "រៀនតាមធ្វើ")),
    "farm": _locales(("en", "Farm Sim"), ("es", "Granja"), ("fr", "Ferme"), ("de", "Farm"),
                      ("zh", "农场模拟"), ("ja", "農場シム"), ("ko", "농장 시뮬"), ("vi", "Nông trại"),
                      ("km", "កសិដ្ឋាន")),
    "spelling": _locales(("en", "Spelling"), ("es", "Ortografía"), ("fr", "Orthographe"),
                          ("de", "Rechtschreibung"), ("zh", "拼写"), ("ja", "スペル"),
                          ("ko", "철자"), ("vi", "Chính tả"), ("km", "អក្ខរាវិរុទ្ធ")),
    "geometry": _locales(("en", "Geometry Play"), ("es", "Geometría"), ("fr", "Géométrie"),
                          ("de", "Geometrie"), ("zh", "几何游戏"), ("ja", "図形ゲーム"),
                          ("ko", "기하 게임"), ("vi", "Hình học"), ("km", "ធរណីមាត្រ")),
}

GAME_TYPE_DESCS: Dict[str, Dict[str, str]] = {
    "tiles": _locales(("en", "Build words from letter tiles (Bananagrams-style)."),
                      ("es", "Forma palabras con letras."), ("zh", "用字母拼词。"),
                      ("ja", "文字タイルで単語を作る。"), ("km", "ប្រើអក្សរបង្កើតពាក្យ។")),
    "resource": _locales(("en", "Choose wisely with limited time, money, or materials."),
                         ("es", "Elige con recursos limitados."), ("zh", "在有限资源下做选择。"),
                         ("ja", "限られた資源で最善を選ぶ。"), ("km", "ជ្រើសរើសដោយមានធនធានមានកំណត់។")),
    "dependency": _locales(("en", "Put steps in the right order when tasks depend on each other."),
                            ("es", "Ordena pasos con dependencias."), ("zh", "按依赖关系排序。"),
                            ("ja", "依存関係のある手順を並べる。"), ("km", "រៀបលំដាប់ដែលពឹងផ្អែកគ្នា។")),
    "rpg": _locales(("en", "Role-play choices that teach real lessons."),
                    ("es", "Decisiones de rol con lecciones."), ("zh", "角色扮演中的抉择。"),
                    ("ja", "学びのあるストーリー選択。"), ("km", "ជ្រើសរើសក្នុងរឿងរៀនសូត្រ។")),
    "cartoon": _locales(("en", "Watch a scene, spot the moral or science idea."),
                         ("es", "Observa y encuentra la moraleja."), ("zh", "看场景，找道理或科学点。"),
                         ("ja", "シーンを見て教訓や科学を見つける。"), ("km", "មើលរូបភាព រកមេរៀន។")),
    "idiom": _locales(("en", "Match slang and idioms to their meanings."),
                       ("es", "Une modismos con su significado."), ("zh", "把俚语和意思配对。"),
                       ("ja", "慣用句と意味を合わせる。"), ("km", "ផ្គូផ្គងសម្រង់ចំណុច។")),
    "create": _locales(("en", "Identify what was built or created."),
                        ("es", "Reconoce lo que se creó."), ("zh", "识别创造出的东西。"),
                        ("ja", "作られたものを見分ける。"), ("km", "ស្គាល់អ្វីដែលបានបង្កើត។")),
    "doing": _locales(("en", "Practice skills step by step."),
                       ("es", "Practica paso a paso."), ("zh", "一步步动手练习。"),
                       ("ja", "手順で実践する。"), ("km", "ធ្វើតាមជំហាន។")),
    "farm": _locales(("en", "Grow crops and learn the subject along the way."),
                      ("es", "Cultiva y aprende."), ("zh", "种田同时学知识。"),
                      ("ja", "農場で育てながら学ぶ。"), ("km", "ដាំដុះហើយរៀន។")),
    "spelling": _locales(("en", "Pick the correct spelling."),
                          ("es", "Elige la ortografía correcta."), ("zh", "选出正确拼写。"),
                          ("ja", "正しい綴りを選ぶ。"), ("km", "ជ្រើសអក្ខរាវិជ្ជាត្រឹម។")),
    "geometry": _locales(("en", "Shapes, angles, and spatial reasoning."),
                          ("es", "Formas y ángulos."), ("zh", "图形、角度与空间。"),
                          ("ja", "図形・角度・空間。"), ("km", "រូបរាង និង មុំ។")),
}


def localize(label_map: Dict[str, Dict[str, str]], key: str, locale: Optional[str]) -> str:
    loc = normalize_locale(locale)
    block = label_map.get(key, {})
    return block.get(loc) or block.get(DEFAULT_LOCALE) or key.replace("_", " ").title()


# Content translations keyed by content_id -> field -> locale -> text
# Fields: prompt, explain, opt_0, opt_1, ...
CONTENT_I18N: Dict[str, Dict[str, Dict[str, str]]] = {}


def register_content_translation(content_id: str, field: str, locale: str, text: str) -> None:
    CONTENT_I18N.setdefault(content_id, {}).setdefault(field, {})[locale] = text


def localize_content_field(content_id: str, field: str, english: str, locale: Optional[str]) -> str:
    loc = normalize_locale(locale)
    if loc == DEFAULT_LOCALE:
        return english
    return CONTENT_I18N.get(content_id, {}).get(field, {}).get(loc, english)


def localize_mcq_item(item: dict, locale: Optional[str]) -> dict:
    """Return a client-safe MCQ dict with localized strings."""
    cid = item.get("content_id", "")
    opts = item.get("options", [])
    loc_opts: List[str] = []
    for i, opt in enumerate(opts):
        loc_opts.append(localize_content_field(cid, f"opt_{i}", opt, locale))
    return {
        "id": item["id"],
        "prompt": localize_content_field(cid, "prompt", item["prompt"], locale),
        "options": loc_opts,
        "meta": item.get("meta", {}),
        "kind": item.get("kind", "mcq"),
    }


def localized_catalog_game_types(base_types: list, locale: Optional[str]) -> list:
    out = []
    for gt in base_types:
        gid = gt["id"]
        out.append({
            **gt,
            "name": localize(GAME_TYPE_LABELS, gid, locale),
            "desc": localize(GAME_TYPE_DESCS, gid, locale) if gid in GAME_TYPE_DESCS else gt.get("desc", ""),
        })
    return out


def localized_subjects(subjects: list, locale: Optional[str]) -> list:
    return [{"id": s, "name": localize(SUBJECT_LABELS, s, locale)} for s in subjects]
