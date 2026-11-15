from datetime import date

import pytest

from ubo_mapper.analysis import build_ownership, jurisdiction_risk, load_jurisdictions, parse_natures
from ubo_mapper.client import CompanyNotFound, normalise_company_number
from ubo_mapper.demo import DemoProvider


class FakeProvider:
    """Small in memory provider so each test controls exactly what the register 'says'."""

    def __init__(self, companies, pscs, statements=None, exemptions=None):
        self.companies, self.pscs = companies, pscs
        self.statements, self.exemptions = statements or {}, exemptions or {}

    def get_company(self, n):
        return self.companies.get(n)

    def get_pscs(self, n):
        return self.pscs.get(n, [])

    def get_psc_statements(self, n):
        return self.statements.get(n, [])

    def get_exemptions(self, n):
        return self.exemptions.get(n, {})


def company(name, status="active", created="2010-01-01"):
    return {"company_name": name, "company_status": status, "date_of_creation": created,
            "jurisdiction": "england-wales"}


def person(name, natures, birth=(1980, 1), **extra):
    return {"kind": "individual-person-with-significant-control", "name": name,
            "natures_of_control": natures, "date_of_birth": {"year": birth[0], "month": birth[1]}, **extra}


def corp(name, reg, natures, country="England and Wales", **extra):
    return {"kind": "corporate-entity-person-with-significant-control", "name": name,
            "natures_of_control": natures,
            "identification": {"registration_number": reg, "country_registered": country,
                               "legal_authority": "Companies Act 2006"}, **extra}


S25, S50, S75 = ("ownership-of-shares-25-to-50-percent", "ownership-of-shares-50-to-75-percent",
                 "ownership-of-shares-75-to-100-percent")


# ---------------------------------------------------------------- parsing
def test_parse_natures_bands_and_flags():
    parsed = parse_natures([S25, S25 + "-as-trust", "voting-rights-50-to-75-percent",
                            "right-to-appoint-and-remove-directors-as-firm"])
    assert parsed["shares"] == (25.0, 50.0)
    assert parsed["voting"] == (50.0, 75.0)
    assert parsed["control_rights"] == ["right-to-appoint-and-remove-directors"]
    assert parsed["as_trust"] and parsed["as_firm"]


def test_parse_overseas_entity_more_than_25():
    parsed = parse_natures(["ownership-of-shares-more-than-25-percent-registered-overseas-entity"])
    assert parsed["shares"] == (25.0, 100.0)


def test_normalise_company_number():
    assert normalise_company_number(" 445790 ") == "00445790"
    assert normalise_company_number("sc 123456") == "SC123456"


def test_jurisdiction_matching_ignores_case_and_punctuation():
    cfg = load_jurisdictions()
    assert jurisdiction_risk("british virgin islands", cfg) == "offshore_centres"
    assert jurisdiction_risk("IRAN", cfg) == "call_for_action"
    assert jurisdiction_risk("France", cfg) is None


# ------------------------------------------------------------- ownership maths
def test_direct_individual_over_threshold_is_likely_ubo():
    provider = FakeProvider({"00000001": company("Target Ltd")}, {"00000001": [person("A Person", [S75])]})
    result = build_ownership(provider, "1")
    assert result.people[0].classification == "LIKELY_UBO"
    assert (result.people[0].low, result.people[0].high) == (75.0, 100.0)


def test_chain_multiplies_bands_into_a_range():
    provider = DemoProvider()
    result = build_ownership(provider, "DEMO0001")
    by_name = {p.name: p for p in result.people}
    jordan = by_name["Jordan Ellis"]
    assert (jordan.low, jordan.high) == (18.75, 50.0)
    assert jordan.classification == "POSSIBLE_UBO"
    casey = by_name["Casey Morgan"]
    assert (casey.low, casey.high) == (18.75, 56.25)


def test_offshore_owner_is_unresolved_and_flagged_high():
    result = build_ownership(DemoProvider(), "DEMO0001")
    assert [u.name for u in result.unresolved] == ["Meridian Ventures Ltd (fictional)"]
    assert result.unresolved[0].high == 37.5
    codes = {(f.code, f.severity) for f in result.flags}
    assert ("OVERSEAS_OWNER", "HIGH") in codes


def test_same_person_in_two_chains_is_summed():
    pscs = {
        "00000001": [corp("Mid A", "00000002", [S50]), corp("Mid B", "00000003", [S50])],
        "00000002": [person("Shared Owner", [S75], birth=(1970, 3))],
        "00000003": [person("Shared Owner", [S75], birth=(1970, 3))],
    }
    companies = {n: company(n) for n in ("00000001", "00000002", "00000003")}
    result = build_ownership(FakeProvider(companies, pscs), "00000001")
    assert len(result.people) == 1
    # 0.75*0.5 + 0.75*0.5 at the low end, 1.0*0.75 + 1.0*0.75 capped at 100 at the high end
    assert result.people[0].low == 75.0
    assert result.people[0].high == 100.0


def test_same_name_without_birth_date_is_not_merged():
    pscs = {
        "00000001": [corp("Mid A", "00000002", [S50]), corp("Mid B", "00000003", [S50])],
        "00000002": [{"kind": "individual-person-with-significant-control", "name": "Common Name",
                      "natures_of_control": [S75]}],
        "00000003": [{"kind": "individual-person-with-significant-control", "name": "Common Name",
                      "natures_of_control": [S75]}],
    }
    companies = {n: company(n) for n in ("00000001", "00000002", "00000003")}
    result = build_ownership(FakeProvider(companies, pscs), "00000001")
    assert len(result.people) == 2


def test_control_only_person_is_not_given_a_percentage():
    pscs = {"00000001": [person("Director Type", ["right-to-appoint-and-remove-directors"])]}
    result = build_ownership(FakeProvider({"00000001": company("T")}, pscs), "00000001")
    person_result = result.people[0]
    assert person_result.classification == "CONTROL"
    assert person_result.high == 0


def test_ceased_psc_is_ignored_by_default_and_shown_when_asked():
    ceased = person("Former Owner", [S75], ceased_on="2022-01-01")
    provider = FakeProvider({"00000001": company("T")}, {"00000001": [ceased, person("Current", [S50])]})
    default = build_ownership(provider, "00000001")
    assert [p.name for p in default.people] == ["Current"]
    shown = build_ownership(provider, "00000001", include_ceased=True)
    assert "Former Owner" in {n.name for n in shown.nodes.values()}
    assert "Former Owner" not in [p.name for p in shown.people]  # history never counts as ownership


# ------------------------------------------------------------------- flags
def test_circular_ownership_is_flagged():
    result = build_ownership(DemoProvider(), "DEMO0010")
    assert "CIRCULAR_OWNERSHIP" in {f.code for f in result.flags}


def test_inactive_owner_and_trust_and_statement_flags():
    result = build_ownership(DemoProvider(), "DEMO0010")
    codes = {f.code for f in result.flags}
    assert {"COMPANY_NOT_ACTIVE", "TRUST_OR_FIRM", "PSC_STATEMENT"} <= codes


def test_no_psc_data_on_target_is_high():
    result = build_ownership(FakeProvider({"00000001": company("T")}, {}), "00000001")
    flag = next(f for f in result.flags if f.code == "NO_PSC_DATA")
    assert flag.severity == "HIGH"


def test_exemption_suppresses_no_psc_flag():
    provider = FakeProvider({"00000001": company("T")}, {}, exemptions={"00000001": {"psc_exempt_as_trading_on_regulated_market": {}}})
    result = build_ownership(provider, "00000001")
    codes = {f.code for f in result.flags}
    assert "NO_PSC_DATA" not in codes and "PSC_EXEMPT" in codes


def test_super_secure_psc_is_flagged_and_unresolved():
    pscs = {"00000001": [{"kind": "super-secure-person-with-significant-control", "natures_of_control": [S50]}]}
    result = build_ownership(FakeProvider({"00000001": company("T")}, pscs), "00000001")
    assert "SUPER_SECURE_PSC" in {f.code for f in result.flags}
    assert result.unresolved[0].kind == "super_secure"


def test_recent_incorporation_of_owner_is_low_flag():
    pscs = {"00000001": [corp("New Co", "00000002", [S75])], "00000002": [person("P", [S75])]}
    companies = {"00000001": company("T"), "00000002": company("New Co", created="2026-06-01")}
    result = build_ownership(FakeProvider(companies, pscs), "00000001", today=date(2026, 11, 15))
    flag = next(f for f in result.flags if f.code == "RECENT_INCORPORATION")
    assert flag.severity == "LOW"


def test_layering_flag_scales_with_depth():
    companies, pscs = {}, {}
    for i in range(1, 6):
        companies[f"0000000{i}"] = company(f"Co{i}")
    for i in range(1, 5):
        pscs[f"0000000{i}"] = [corp(f"Co{i+1}", f"0000000{i+1}", [S75])]
    pscs["00000005"] = [person("Ultimate", [S75])]
    result = build_ownership(FakeProvider(companies, pscs), "00000001", max_depth=6)
    flag = next(f for f in result.flags if f.code == "LAYERED_STRUCTURE")
    assert flag.severity == "MEDIUM"  # 4 intermediate companies


def test_depth_limit_stops_and_flags():
    pscs = {"00000001": [corp("Co2", "00000002", [S75])], "00000002": [person("Hidden", [S75])]}
    companies = {"00000001": company("T"), "00000002": company("Co2")}
    result = build_ownership(FakeProvider(companies, pscs), "00000001", max_depth=1)
    assert result.people == []
    assert "DEPTH_LIMIT" in {f.code for f in result.flags}
    assert result.unresolved[0].reason.startswith("Not expanded")


def test_unknown_company_raises():
    with pytest.raises(CompanyNotFound):
        build_ownership(FakeProvider({}, {}), "99999999")


def test_uk_owner_that_does_not_resolve_is_flagged():
    pscs = {"00000001": [corp("Ghost Ltd", "00000009", [S50])]}
    result = build_ownership(FakeProvider({"00000001": company("T")}, pscs), "00000001")
    assert "COMPANY_NOT_FOUND" in {f.code for f in result.flags}


def test_individual_resident_in_call_for_action_jurisdiction_is_high():
    pscs = {"00000001": [person("Resident Abroad", [S50], country_of_residence="Iran")]}
    result = build_ownership(FakeProvider({"00000001": company("T")}, pscs), "00000001")
    flag = next(f for f in result.flags if f.code == "PERSON_RESIDENCE_RISK")
    assert flag.severity == "HIGH"


def test_corporate_owner_without_registration_number_is_unresolved():
    pscs = {"00000001": [{"kind": "corporate-entity-person-with-significant-control", "name": "Mystery Holdings",
                          "natures_of_control": [S50], "identification": {"country_registered": "Panama"}}]}
    result = build_ownership(FakeProvider({"00000001": company("T")}, pscs), "00000001")
    assert "UNIDENTIFIED_CORPORATE" in {f.code for f in result.flags}
    assert result.unresolved[0].name == "Mystery Holdings"
