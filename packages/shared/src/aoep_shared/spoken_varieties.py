"""Spoken language and dialect names for lab pickers.

Each row is one variety a person can choose without knowing a language code.
``language`` is the base code (dictionary, feedback, read-aloud). ``whisper``
is the speech code (Cantonese is ``yue``, not Mandarin). ``dialect`` is set
when the narration catalog has a regional voice for that place.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SpokenVariety:
    id: str
    language: str
    whisper: str
    dialect: str
    label: str
    country: str

    def to_dict(self) -> dict:
        return asdict(self)


# Full name first. Codes stay in the fields above, not in the label.
_VARIETIES: tuple[SpokenVariety, ...] = (
    SpokenVariety("en_us", "en", "en", "us_general", "English — United States", "United States"),
    SpokenVariety("en_california", "en", "en", "us_ca", "English — California", "United States"),
    SpokenVariety("en_texas", "en", "en", "us_tx", "English — Texas", "United States"),
    SpokenVariety("en_south", "en", "en", "us_south", "English — Southern United States", "United States"),
    SpokenVariety("en_new_york", "en", "en", "us_ny", "English — New York", "United States"),
    SpokenVariety("en_new_england", "en", "en", "us_ne", "English — New England", "United States"),
    SpokenVariety("en_gb", "en", "en", "en_gb", "English — United Kingdom", "United Kingdom"),
    SpokenVariety("en_au", "en", "en", "en_au", "English — Australia", "Australia"),
    SpokenVariety("en_ca", "en", "en", "en_ca", "English — Canada", "Canada"),
    SpokenVariety("en_ie", "en", "en", "en_ie", "English — Ireland", "Ireland"),
    SpokenVariety("en_in", "en", "en", "en_in", "English — India", "India"),
    SpokenVariety("en_sg", "en", "en", "en_sg", "English — Singapore", "Singapore"),
    SpokenVariety("en_za", "en", "en", "en_za", "English — South Africa", "South Africa"),
    SpokenVariety("es_es", "es", "es", "", "Spanish — Spain", "Spain"),
    SpokenVariety("es_mx", "es", "es", "es_mx", "Spanish — Mexico", "Mexico"),
    SpokenVariety("es_ar", "es", "es", "", "Spanish — Argentina", "Argentina"),
    SpokenVariety("es_us", "es", "es", "", "Spanish — United States", "United States"),
    SpokenVariety("fr_fr", "fr", "fr", "", "French — France", "France"),
    SpokenVariety("fr_ca", "fr", "fr", "", "French — Canada", "Canada"),
    SpokenVariety("de_de", "de", "de", "", "German — Germany", "Germany"),
    SpokenVariety("it_it", "it", "it", "", "Italian — Italy", "Italy"),
    SpokenVariety("pt_pt", "pt", "pt", "", "Portuguese — Portugal", "Portugal"),
    SpokenVariety("pt_br", "pt", "pt", "pt_br", "Portuguese — Brazil", "Brazil"),
    SpokenVariety("nl_nl", "nl", "nl", "", "Dutch — Netherlands", "Netherlands"),
    SpokenVariety("pl_pl", "pl", "pl", "", "Polish — Poland", "Poland"),
    SpokenVariety("ru_ru", "ru", "ru", "", "Russian — Russia", "Russia"),
    SpokenVariety("uk_ua", "uk", "uk", "", "Ukrainian — Ukraine", "Ukraine"),
    SpokenVariety("cs_cz", "cs", "cs", "", "Czech — Czechia", "Czechia"),
    SpokenVariety("el_gr", "el", "el", "", "Greek — Greece", "Greece"),
    SpokenVariety("tr_tr", "tr", "tr", "", "Turkish — Turkey", "Turkey"),
    SpokenVariety("ar_sa", "ar", "ar", "", "Arabic — Gulf", "Saudi Arabia"),
    SpokenVariety("ar_eg", "ar", "ar", "", "Arabic — Egypt", "Egypt"),
    SpokenVariety("he_il", "he", "he", "", "Hebrew — Israel", "Israel"),
    SpokenVariety("fa_ir", "fa", "fa", "", "Persian — Iran", "Iran"),
    SpokenVariety("hi_in", "hi", "hi", "", "Hindi — India", "India"),
    SpokenVariety("bn_bd", "bn", "bn", "", "Bengali — Bangladesh", "Bangladesh"),
    SpokenVariety("ur_pk", "ur", "ur", "", "Urdu — Pakistan", "Pakistan"),
    SpokenVariety("zh_cn", "zh", "zh", "zh_bj", "Mandarin — China", "China"),
    SpokenVariety("zh_beijing", "zh", "zh", "zh_bj", "Mandarin — Beijing", "China"),
    SpokenVariety("zh_shanghai", "zh", "zh", "zh_sh", "Chinese — Shanghai", "China"),
    SpokenVariety("zh_tw", "zh", "zh", "", "Mandarin — Taiwan", "Taiwan"),
    SpokenVariety("yue_hk", "yue", "yue", "zh_yue_gz", "Cantonese — Hong Kong", "Hong Kong"),
    SpokenVariety("yue_gz", "yue", "yue", "zh_yue_gz", "Cantonese — Guangzhou", "China"),
    SpokenVariety("zh_min", "zh", "zh", "zh_min_fj", "Chinese — Fujian (Hokkien)", "China"),
    SpokenVariety("ja_jp", "ja", "ja", "", "Japanese — Japan", "Japan"),
    SpokenVariety("ko_kr", "ko", "ko", "", "Korean — Korea", "Korea"),
    SpokenVariety("vi_vn", "vi", "vi", "", "Vietnamese — Vietnam", "Vietnam"),
    SpokenVariety("th_th", "th", "th", "", "Thai — Thailand", "Thailand"),
    SpokenVariety("km_kh", "km", "km", "", "Cambodian — Khmer", "Cambodia"),
    SpokenVariety("tl_ph", "tl", "tl", "", "Tagalog — Philippines", "Philippines"),
    SpokenVariety("id_id", "id", "id", "", "Indonesian — Indonesia", "Indonesia"),
    SpokenVariety("sw_ke", "sw", "sw", "", "Swahili — Kenya", "Kenya"),
)


def list_spoken_varieties() -> list[dict]:
    """Varieties sorted by the name a person reads, not by the code."""
    rows = [item.to_dict() for item in _VARIETIES]
    rows.sort(key=lambda row: row["label"].casefold())
    return rows
