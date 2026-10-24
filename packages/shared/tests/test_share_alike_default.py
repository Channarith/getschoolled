"""Share-alike (CC BY-SA, GFDL) is ON by default (owner decision 2026-10-24) and the wall is unchanged."""
import json

import pytest

from aoep_shared.config import AppConfig
from aoep_shared.harvest.licensing import (
    HarvestPolicy, LicenseConflictError, combine_course_license, decide, parse_license, policy_from_env,
)
from aoep_shared.harvest.provenance import Provenance, merge_course_provenance


def info(text):
    return parse_license(text)


def test_default_is_on_and_env_turns_it_off():
    assert HarvestPolicy().allow_share_alike is True
    assert policy_from_env({}).allow_share_alike is True
    for off in ("0", "false", "no", "off"):
        assert policy_from_env({"AOEP_HARVEST_ALLOW_SHARE_ALIKE": off}).allow_share_alike is False


def test_app_config_default_follows_the_decision():
    assert AppConfig().harvest_allow_share_alike is True


@pytest.mark.parametrize("lic", ["cc-by-nc", "cc-by-nc-sa", "cc-by-nd", "all rights reserved", "oer", ""])
def test_wall_unchanged_these_never_enter_the_product_corpus(lic):
    for policy in (HarvestPolicy(), HarvestPolicy(allow_share_alike=True), HarvestPolicy(allow_share_alike=False)):
        d = decide(parse_license(lic), policy)
        assert not d.ingest, (lic, policy)
        assert d.corpus in ("", "research")


def test_share_alike_makes_the_course_share_alike_and_cc_by_inputs_may_be_mixed_in():
    lic = combine_course_license([info("CC BY-SA 4.0"), info("CC BY 4.0"), info("public domain"), info("MIT")])
    assert lic["share_alike"] is True and lic["spdx"] == "CC-BY-SA-4.0"
    assert {"CC-BY-SA-4.0", "CC-BY-4.0"} <= set(lic["inputs"])
    plain = combine_course_license([info("CC BY 4.0"), info("public domain")])
    assert plain["share_alike"] is False and plain["spdx"] == "CC-BY-4.0"


@pytest.mark.parametrize("other", ["cc-by-nc", "cc-by-nd", "cc-by-nc-sa", "all rights reserved", "oer", ""])
def test_share_alike_mixed_with_an_incompatible_source_is_refused(other):
    with pytest.raises(LicenseConflictError):
        combine_course_license([info("CC BY-SA 4.0"), info(other)])


def test_different_share_alike_licenses_cannot_be_mixed():
    with pytest.raises(LicenseConflictError, match="incompatible share-alike"):
        combine_course_license([info("CC BY-SA 4.0"), info("CC BY-SA 3.0")])
    with pytest.raises(LicenseConflictError, match="incompatible share-alike"):
        combine_course_license([info("CC BY-SA 4.0"), info("GFDL")])


def test_share_alike_source_is_refused_when_the_switch_is_off_and_empty_is_refused():
    with pytest.raises(LicenseConflictError, match="switched off"):
        combine_course_license([info("CC BY-SA 4.0")], HarvestPolicy(allow_share_alike=False))
    with pytest.raises(LicenseConflictError):
        combine_course_license([])


def prov(text, url):
    i = info(text)
    return Provenance(source_url=url, license=i.to_dict(), license_tier=i.tier.value,
                      attribution={"title": "T", "author": "A", "source_url": url, "license_name": i.spdx,
                                   "license_url": i.url, "text": f"credit {url}"})


def test_merge_course_provenance_returns_the_course_license_and_every_credit():
    out = merge_course_provenance([prov("CC BY-SA 4.0", "https://a.example/1"), prov("CC BY 4.0", "https://b.example/2")])
    assert out["course_license"]["share_alike"] and out["course_license"]["spdx"] == "CC-BY-SA-4.0"
    assert "same license" in out["course_license"]["note"]
    assert [a["source_url"] for a in out["attributions"]] == ["https://a.example/1", "https://b.example/2"]
    with pytest.raises(LicenseConflictError):
        merge_course_provenance([prov("CC BY-SA 4.0", "https://a.example/1"), prov("cc-by-nc", "https://c.example/3")])


def test_catalog_payload_and_course_json_carry_the_course_license():
    from aoep_shared.harvest.generate import GeneratedCourse
    p = prov("CC BY-SA 4.0", "https://a.example/1").to_dict()
    p["obligations"] = ["share-alike"]
    course = GeneratedCourse(course_id="c", title="T", subject="s", language="en", source="x", fmt="lecture",
                             provenance=p)
    payload = course.catalog_payload()
    assert payload["meta_course_license"] == "CC-BY-SA-4.0" and payload["meta_course_license_share_alike"] is True
    assert payload["meta_course_license_url"] == info("CC BY-SA 4.0").url
    data = json.loads(course.to_json())
    assert data["course_license"]["share_alike"] is True and data["course_license"]["spdx"] == "CC-BY-SA-4.0"
    assert data["attributions"][0]["source_url"] == "https://a.example/1"
