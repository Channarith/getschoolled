"""Spoken variety names are what the lab language menus show."""

from aoep_shared.spoken_varieties import list_spoken_varieties


def test_variety_menu_names_languages_and_dialects():
    rows = list_spoken_varieties()
    assert len(rows) >= 45
    labels = [row["label"] for row in rows]
    assert len(labels) == len(set(labels))
    assert labels == sorted(labels, key=str.casefold)
    for row in rows:
        assert "—" in row["label"]
        assert row["id"] not in row["label"]
        assert row["language"]
        assert row["whisper"]
    by_id = {row["id"]: row for row in rows}
    assert by_id["km_kh"]["label"] == "Khmer — Cambodia"
    assert by_id["yue_hk"]["whisper"] == "yue"
    assert by_id["en_california"]["dialect"] == "us_ca"
    assert by_id["tl_ph"]["language"] == "tl"
