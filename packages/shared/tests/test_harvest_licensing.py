"""License tiers, parsing, page-level detection and the harvest decision."""

import pytest

from aoep_shared.harvest.licensing import (
    HarvestPolicy,
    Tier,
    decide,
    parse_license,
    policy_from_env,
    resolve_page_license,
    scan_page,
    verify_page,
)
from aoep_shared.harvest.vetted_sources import vetted_for


@pytest.mark.parametrize(
    "text,spdx,tier",
    [
        ("CC BY 4.0", "CC-BY-4.0", Tier.COMMERCIAL_OK),
        ("cc-by", "CC-BY", Tier.COMMERCIAL_OK),
        ("CC-BY-3.0", "CC-BY-3.0", Tier.COMMERCIAL_OK),
        ("Attribution 4.0 International", "CC-BY-4.0", Tier.COMMERCIAL_OK),
        ("Creative Commons Attribution 4.0 International", "CC-BY-4.0", Tier.COMMERCIAL_OK),
        ("https://creativecommons.org/licenses/by/3.0/us/", "CC-BY-3.0-US", Tier.COMMERCIAL_OK),
        ("//creativecommons.org/licenses/by/4.0/", "CC-BY-4.0", Tier.COMMERCIAL_OK),
        ("CC0", "CC0-1.0", Tier.COMMERCIAL_OK),
        ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0-1.0", Tier.COMMERCIAL_OK),
        ("https://creativecommons.org/publicdomain/mark/1.0/", "PDM-1.0", Tier.COMMERCIAL_OK),
        ("public domain", "PD", Tier.COMMERCIAL_OK),
        ("public-domain", "PD", Tier.COMMERCIAL_OK),
        ("US Government Work", "PD", Tier.COMMERCIAL_OK),
        ("MIT", "MIT", Tier.COMMERCIAL_OK),
        ("Apache-2.0", "Apache-2.0", Tier.COMMERCIAL_OK),
        ("BSD-3-Clause", "BSD", Tier.COMMERCIAL_OK),
        ("CC BY-SA 4.0", "CC-BY-SA-4.0", Tier.SHARE_ALIKE),
        ("cc-by-sa", "CC-BY-SA", Tier.SHARE_ALIKE),
        ("//creativecommons.org/licenses/by-sa/4.0/", "CC-BY-SA-4.0", Tier.SHARE_ALIKE),
        ("GFDL", "GFDL", Tier.SHARE_ALIKE),
        ("GNU Free Documentation License", "GFDL", Tier.SHARE_ALIKE),
        ("cc-by-nc", "CC-BY-NC", Tier.NON_COMMERCIAL),
        ("cc-by-nc-sa", "CC-BY-NC-SA", Tier.NON_COMMERCIAL),
        ("CC BY-NC-ND 4.0", "CC-BY-NC-ND-4.0", Tier.NON_COMMERCIAL),
        ("Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International", "CC-BY-NC-SA-4.0", Tier.NON_COMMERCIAL),
        ("https://creativecommons.org/licenses/by-nc/4.0/", "CC-BY-NC-4.0", Tier.NON_COMMERCIAL),
        ("noncommercial", "NON-COMMERCIAL", Tier.NON_COMMERCIAL),
        ("cc-by-nd", "CC-BY-ND", Tier.NO_DERIVATIVES),
        ("Creative Commons Attribution-NoDerivatives 4.0", "CC-BY-ND-4.0", Tier.NO_DERIVATIVES),
        ("All Rights Reserved", "ALL-RIGHTS-RESERVED", Tier.PROPRIETARY),
        ("proprietary", "ALL-RIGHTS-RESERVED", Tier.PROPRIETARY),
        ("oer", "UNKNOWN", Tier.UNKNOWN),
        ("creative commons", "UNKNOWN", Tier.UNKNOWN),
        ("", "UNKNOWN", Tier.UNKNOWN),
        (None, "UNKNOWN", Tier.UNKNOWN),
    ],
)
def test_parse_license(text, spdx, tier):
    info = parse_license(text)
    assert info.spdx == spdx
    assert info.tier is tier


def test_port_and_version_are_read_from_license_urls():
    info = parse_license("https://creativecommons.org/licenses/by/3.0/igo/")
    assert (info.family, info.version, info.port) == ("by", "3.0", "igo")


def test_noncommercial_wins_over_other_words():
    assert parse_license("CC BY-NC-SA 4.0 (non-commercial, share alike)").tier is Tier.NON_COMMERCIAL


def test_policy_tiers_and_switches():
    off = HarvestPolicy()
    assert off.tier_allowed(Tier.COMMERCIAL_OK)
    assert not off.tier_allowed(Tier.SHARE_ALIKE)
    assert HarvestPolicy(allow_share_alike=True).tier_allowed(Tier.SHARE_ALIKE)
    for tier in (Tier.NON_COMMERCIAL, Tier.NO_DERIVATIVES, Tier.PROPRIETARY, Tier.UNKNOWN):
        assert not HarvestPolicy(allow_share_alike=True, research_only=True).tier_allowed(tier)


def test_policy_from_env_defaults_off_and_reads_switches():
    assert policy_from_env({}) == HarvestPolicy(False, False)
    p = policy_from_env({"AOEP_HARVEST_ALLOW_SHARE_ALIKE": "1", "AOEP_HARVEST_RESEARCH_ONLY": "true"})
    assert p.allow_share_alike and p.research_only


def test_decide_obligations_and_actions():
    by = decide(parse_license("CC BY 4.0"))
    assert by.ingest and any("attribution" in o for o in by.obligations)
    pd = decide(parse_license("public domain"))
    assert pd.ingest and pd.obligations == []
    sa_off = decide(parse_license("CC BY-SA 4.0"))
    assert sa_off.action == "reject" and "allow_share_alike" in sa_off.reason
    sa_on = decide(parse_license("CC BY-SA 4.0"), HarvestPolicy(allow_share_alike=True))
    assert sa_on.ingest and any("share-alike" in o for o in sa_on.obligations)
    nc = decide(parse_license("cc-by-nc"))
    assert nc.action == "reject"
    assert decide(parse_license("cc-by-nc"), HarvestPolicy(research_only=True)).action == "research_only"
    assert decide(parse_license("cc-by"), conflict=True).action == "reject"


# ------------------------------------------------------------ page detection

def _page(head="", body="", footer=""):
    return f"<html><head><title>T</title>{head}</head><body>{body}<footer>{footer}</footer></body></html>"


def test_scan_finds_rel_license_link_and_anchor():
    link = scan_page(_page('<link rel="license" href="https://creativecommons.org/licenses/by/4.0/">'))
    assert [i.spdx for i in link.licenses] == ["CC-BY-4.0"]
    assert link.licenses[0].kind == "rel-license"
    anchor = scan_page(_page(body='<a rel="license" href="//creativecommons.org/licenses/by-sa/4.0/">CC BY-SA</a>'))
    assert anchor.licenses[0].tier is Tier.SHARE_ALIKE


def test_scan_finds_meta_schema_and_jsonld():
    meta = scan_page(_page('<meta name="DC.rights" content="CC BY-NC 4.0">'))
    assert meta.licenses[0].tier is Tier.NON_COMMERCIAL
    schema = scan_page(_page(body='<link itemprop="license" href="https://creativecommons.org/licenses/by/4.0/">'))
    assert schema.licenses[0].kind == "schema"
    ld = scan_page(_page('<script type="application/ld+json">{"@type":"Article","license":'
                         '"https://creativecommons.org/licenses/by/4.0/"}</script>'))
    assert ld.licenses[0].kind == "jsonld" and ld.licenses[0].tier is Tier.COMMERCIAL_OK


def test_scan_reads_footer_text_but_ignores_script_text():
    s = scan_page(_page(footer="Text is available under the Creative Commons Attribution-ShareAlike 4.0 License."))
    assert s.licenses and s.licenses[0].kind == "footer" and s.licenses[0].tier is Tier.SHARE_ALIKE
    quiet = scan_page(_page(body="<script>var x = 'licensed under CC BY-NC 4.0';</script><p>hello</p>"))
    assert quiet.licenses == []


def test_scan_crawl_directives_and_paywall():
    s = scan_page(_page('<meta name="robots" content="noindex, noai">'))
    assert s.noai and s.noindex
    h = scan_page(_page(), headers={"X-Robots-Tag": "noai"})
    assert h.noai and not h.noindex
    wall = scan_page(_page(body="<p>Please subscribe to continue reading this lesson.</p>"))
    assert wall.paywalled
    ld = scan_page(_page('<script type="application/ld+json">{"isAccessibleForFree": "False"}</script>'))
    assert ld.paywalled


def test_resolve_conflict_rules():
    same = scan_page(_page('<link rel="license" href="//creativecommons.org/licenses/by/4.0/">'
                           '<meta name="license" content="CC BY 3.0">'))
    info, conflict = resolve_page_license(same)
    assert not conflict and info.tier is Tier.COMMERCIAL_OK
    mixed = scan_page(_page('<link rel="license" href="//creativecommons.org/licenses/by/4.0/">'
                            '<meta name="license" content="CC BY-NC 4.0">'))
    info, conflict = resolve_page_license(mixed)
    assert conflict and info.tier is Tier.NON_COMMERCIAL     # the stricter claim is reported
    footer_disagrees = scan_page(_page('<link rel="license" href="//creativecommons.org/licenses/by/4.0/">',
                                       footer="All rights reserved."))
    assert resolve_page_license(footer_disagrees)[1] is True


# ------------------------------------------------------------ verification

CC_BY_PAGE = _page('<link rel="license" href="https://creativecommons.org/licenses/by/4.0/">')


def test_declared_license_is_a_claim_the_page_must_confirm():
    ok, _ = verify_page(declared_license="cc-by", html=CC_BY_PAGE, url="https://x.example.net/a")
    assert ok.decision.ingest and ok.verified_by == "page"
    # Seed says CC BY, page says NonCommercial: rejected as a conflict.
    nc_page = _page('<link rel="license" href="https://creativecommons.org/licenses/by-nc/4.0/">')
    bad, _ = verify_page(declared_license="cc-by", html=nc_page, url="https://x.example.net/a")
    assert not bad.decision.ingest and bad.decision.conflict
    # No seed claim at all: the page alone decides.
    none, _ = verify_page(declared_license=None, html=CC_BY_PAGE, url="https://x.example.net/a")
    assert none.decision.ingest


def test_page_without_license_evidence_is_rejected_unless_vetted():
    bare = _page(body="<p>Some text</p>")
    ver, _ = verify_page(declared_license="cc-by", html=bare, url="https://x.example.net/a")
    assert not ver.decision.ingest and "no license evidence" in ver.decision.reason
    vet = vetted_for("https://www.nasa.gov/learning-resources/").info()
    vetted, _ = verify_page(declared_license="public-domain", html=bare, url="https://www.nasa.gov/x", vetted=vet)
    assert vetted.decision.ingest and vetted.verified_by == "vetted-site"
    clash, _ = verify_page(declared_license="cc-by-nc", html=bare, url="https://www.nasa.gov/x", vetted=vet)
    assert not clash.decision.ingest and clash.decision.conflict


def test_page_evidence_overrides_a_vetted_site():
    vet = vetted_for("https://www.nasa.gov/x").info()
    third_party = _page(footer="Copyright 2024 Example Corp. All rights reserved.")
    ver, _ = verify_page(declared_license=None, html=third_party, url="https://www.nasa.gov/x", vetted=vet)
    assert not ver.decision.ingest


def test_share_alike_page_needs_the_policy_switch():
    sa = _page('<link rel="license" href="//creativecommons.org/licenses/by-sa/4.0/">')
    off, _ = verify_page(declared_license=None, html=sa, url="https://x.example.net/a")
    assert not off.decision.ingest
    on, _ = verify_page(declared_license=None, html=sa, url="https://x.example.net/a",
                        policy=HarvestPolicy(allow_share_alike=True))
    assert on.decision.ingest and on.decision.obligations


@pytest.mark.parametrize(
    "html,reason",
    [
        (_page('<meta name="robots" content="noai">' + CC_BY_PAGE), "noai"),
        (_page(body="<p>Sign in to continue</p>") + CC_BY_PAGE, "paywalled"),
    ],
)
def test_noai_and_paywall_reject_even_with_a_good_license(html, reason):
    ver, _ = verify_page(declared_license="cc-by", html=html, url="https://x.example.net/a")
    assert not ver.decision.ingest and reason in ver.decision.reason


def test_no_derivatives_and_all_rights_reserved_are_rejected():
    for lic in ("by-nd/4.0", "by-nc-nd/4.0"):
        page = _page(f'<link rel="license" href="https://creativecommons.org/licenses/{lic}/">')
        ver, _ = verify_page(declared_license=None, html=page, url="https://x.example.net/a")
        assert not ver.decision.ingest
    arr, _ = verify_page(declared_license=None, html=_page(footer="All rights reserved."), url="https://x.example.net/a")
    assert not arr.decision.ingest
