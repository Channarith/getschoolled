from aoep_shared.nllb import flores_code


def test_cantonese_is_not_mandarin():
    assert flores_code("yue") == "yue_Hant"
    assert flores_code("zh") == "zho_Hans"
    assert flores_code("yue") != flores_code("zh")
