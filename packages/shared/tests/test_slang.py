"""Slang/idiom lexicon + normalizer tests."""

from aoep_shared.slang import SlangEntry, SlangLexicon, default_lexicon


def test_detect_english_idiom():
    lex = default_lexicon()
    dets = lex.detect("Honestly the exam was a piece of cake for me", language="en")
    phrases = {d.phrase for d in dets}
    assert "piece of cake" in phrases


def test_normalize_expands_meaning_for_rag():
    lex = default_lexicon()
    norm = lex.normalize("I need to hit the books tonight", language="en")
    assert "study hard" in norm.plain
    assert any("hit the books" in g for g in norm.glossed)


def test_region_filter_uk_vs_us():
    lex = default_lexicon()
    uk = lex.detect("I'm absolutely knackered", language="en", region="uk")
    assert any(d.phrase == "knackered" for d in uk)
    # A US-region scope should still see global, but not necessarily uk slang.
    us = lex.lookup("knackered", language="en", region="us")
    assert us is None


def test_spanish_and_french_entries():
    lex = default_lexicon()
    es = lex.detect("oye, que onda con la tarea", language="es")
    assert any(d.phrase == "que onda" for d in es)
    fr = lex.normalize("ce probleme c'est du gateau", language="fr")
    assert "piece of cake" in fr.plain or "very easy" in fr.plain


def test_longest_match_wins_no_overlap():
    lex = SlangLexicon([
        SlangEntry("cake", "dessert", "en", "global", "slang"),
        SlangEntry("piece of cake", "very easy", "en", "global", "idiom"),
    ])
    dets = lex.detect("it is a piece of cake", language="en")
    assert len(dets) == 1 and dets[0].phrase == "piece of cake"


def test_no_false_positive():
    lex = default_lexicon()
    assert lex.detect("the quadratic formula solves equations", language="en") == []


def test_custom_entry_added():
    lex = SlangLexicon([])
    lex.add(SlangEntry("rizz", "charisma / charm", "en", "us", "slang"))
    assert lex.lookup("rizz", language="en") is not None
