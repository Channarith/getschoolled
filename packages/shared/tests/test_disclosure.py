"""AI disclosure model tests (Trust layer, Phase 1)."""

from aoep_shared.config import AppConfig, DeployMode
from aoep_shared.disclosure import Disclosure, disclosure_from_config


def test_ai_disclosure_line_mentions_model_and_persona():
    d = Disclosure(model_name="edu-7b", persona="strict")
    line = d.disclosure_line()
    assert "AI instructor" in line
    assert "edu-7b" in line
    assert "strict" in line


def test_human_of_record_included():
    d = Disclosure(human_of_record="Dr. Lee")
    assert "Dr. Lee" in d.disclosure_line()


def test_non_ai_disclosure():
    d = Disclosure(is_ai=False, human_of_record="Ms. Ortiz")
    line = d.disclosure_line()
    assert "Ms. Ortiz" in line
    assert "AI instructor" not in line


def test_disclosure_from_config_uses_llm_model():
    cfg = AppConfig(deploy_mode=DeployMode.LOCAL, llm_model="aoep-edu-2")
    d = disclosure_from_config(cfg, persona="scientific")
    assert d.model_name == "aoep-edu-2"
    assert d.persona == "scientific"
    assert d.is_ai is True
