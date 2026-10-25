from aoep_shared import tone_presets as tp


def test_neutral_empty_and_unknown_tones_change_nothing():
    for t in (None, "", "neutral", "NEUTRAL", "nope", "blend-nope", "blend-"):
        assert tp.tone_prosody(t) is None


def test_presets_and_blends():
    assert tp.tone_prosody("anime") == ("+18%", "+40Hz", "+10%")
    assert tp.tone_prosody(" Cute ") == ("+8%", "+30Hz", "+0%")
    rate, pitch, volume = tp.tone_prosody("blend-professional50-cute50")
    assert (rate, pitch, volume) == ("+2%", "+15Hz", "+0%")     # mean of (-3, +8), (0, 30), (0, 0), rounded
    assert len(tp.TONE_IDS) == 1 + 9 + 13 and tp.TONE_IDS[0] == "neutral"


def test_every_tone_id_resolves_except_neutral():
    for t in tp.TONE_IDS[1:]:
        r, p, v = tp.tone_prosody(t)
        assert r.endswith("%") and p.endswith("Hz") and v.endswith("%")


def test_table_matches_the_tts_bakeoff_voice_types():
    from tts_bakeoff import voice_types as vt   # the clip renderer's copy: the numbers must be identical

    assert tp.PRESETS == vt.PRESETS
    assert tp.BLEND_WEIGHTS == vt.BLEND_WEIGHTS
    for label, weights in tp.BLEND_WEIGHTS.items():
        assert tp.blend(weights) == vt.blend(weights), label
