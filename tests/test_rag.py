from datetime import date

from ubo_mapper import theme
from ubo_mapper.analysis import build_ownership
from ubo_mapper.demo import DEMO_LABELS, DemoProvider
from ubo_mapper.filings import describe, filing_flags, summarise
from ubo_mapper.graph import to_dot
from ubo_mapper.models import Node
from ubo_mapper.report import company_rows, to_markdown
from ubo_mapper.verification import assess_identity, worse

TODAY = date(2026, 11, 15)


# ------------------------------------------------------- identity verification
def test_statement_supplied_is_verified_green():
    status = assess_identity({"appointment_verification_start_on": "2026-01-10"}, TODAY)
    assert (status.status, status.rag) == ("VERIFIED", "GREEN")


def test_verified_by_authorised_corporate_service_provider():
    status = assess_identity({"identity_verified_on": "2026-02-01"}, TODAY)
    assert status.rag == "GREEN" and "service provider" in status.label


def test_overdue_due_date_is_red_and_counts_days():
    status = assess_identity({"appointment_verification_statement_due_on": "2026-11-05"}, TODAY)
    assert (status.status, status.rag) == ("OVERDUE", "RED")
    assert "10 days" in status.label


def test_future_due_date_is_amber():
    status = assess_identity({"appointment_verification_statement_due_on": "2026-12-01"}, TODAY)
    assert (status.status, status.rag) == ("NOT_VERIFIED", "AMBER")
    assert "16 days" in status.label


def test_no_record_before_transition_end_is_amber_and_after_is_red():
    before = assess_identity(None, TODAY)
    assert before.rag == "AMBER" and "2 days" in before.label
    after = assess_identity({}, date(2026, 11, 18))
    assert after.rag == "RED"


def test_removed_statement_is_not_treated_as_verified():
    details = {"appointment_verification_start_on": "2026-01-10", "appointment_verification_end_on": "2026-06-01",
               "appointment_verification_statement_due_on": "2026-12-20"}
    status = assess_identity(details, TODAY)
    assert status.rag == "AMBER" and "Statement removed" in status.label


def test_worse_picks_the_more_serious_status():
    assert worse("VERIFIED", "OVERDUE") == "OVERDUE"
    assert worse(None, "NOT_VERIFIED") == "NOT_VERIFIED"


# --------------------------------------------------------------------- filings
def profile(**extra):
    return {"company_name": "T", "company_status": "active", **extra}


def node_for(prof, status="active"):
    node = Node(id="co:1", kind="company", name="Target Ltd", status=status)
    node.filings = summarise(prof, TODAY)
    return node


def test_overdue_flag_from_register_boolean():
    node = node_for(profile(accounts={"next_due": "2026-10-01", "overdue": True}))
    flag = filing_flags(node, TODAY)[0]
    assert (flag.code, flag.severity) == ("ACCOUNTS_OVERDUE", "HIGH")
    assert "45 days" in flag.detail


def test_overdue_worked_out_from_date_when_boolean_missing():
    node = node_for(profile(confirmation_statement={"next_due": "2026-11-01"}))
    assert filing_flags(node, TODAY)[0].code == "CONFIRMATION_OVERDUE"


def test_due_within_30_days_is_medium_and_later_is_not_flagged():
    soon = node_for(profile(accounts={"next_due": "2026-12-10", "overdue": False}))
    assert [(f.code, f.severity) for f in filing_flags(soon, TODAY)] == [("FILING_DUE_SOON", "MEDIUM")]
    later = node_for(profile(accounts={"next_due": "2027-06-01", "overdue": False}))
    assert filing_flags(later, TODAY) == []


def test_closed_company_raises_no_filing_flags():
    node = node_for(profile(accounts={"next_due": "2026-01-01", "overdue": True}), status="dissolved")
    assert filing_flags(node, TODAY) == []


def test_strike_off_and_office_problems_are_flagged():
    node = node_for(profile(company_status_detail="active-proposal-to-strike-off",
                            undeliverable_registered_office_address=True))
    codes = {f.code for f in filing_flags(node, TODAY)}
    assert {"STRIKE_OFF_PROPOSED", "OFFICE_UNDELIVERABLE"} <= codes


def test_describe_wording():
    assert describe(None) == "Not reported"
    assert describe({"overdue": True, "due_on": "2026-10-01", "days": -45}).startswith("OVERDUE since 2026-10-01 (45 days)")
    assert describe({"overdue": False, "due_on": "2026-12-01", "days": 16}) == "Due 2026-12-01 (in 16 days)"


# ------------------------------------------------------------------------ RAG
def run(name):
    return build_ownership(DemoProvider(today=TODAY), name, today=TODAY)


def test_demo_scenarios_rate_as_labelled():
    expected = {"DEMO0001": "RED", "DEMO0010": "RED", "DEMO0030": "AMBER", "DEMO0020": "GREEN"}
    assert set(expected) == set(DEMO_LABELS)
    for number, rag in expected.items():
        assert run(number).overall_rag == rag, number


def test_each_dimension_is_driven_by_its_own_flags():
    rag = run("DEMO0001").rag
    assert rag["structure"]["rag"] == "RED"          # BVI owner
    assert rag["transparency"]["rag"] == "AMBER"     # 37.5% unresolved
    assert rag["identity"]["rag"] == "RED"           # Casey Morgan overdue
    assert rag["filings"]["rag"] == "RED"            # accounts overdue


def test_green_scenario_has_no_flags_above_info():
    result = run("DEMO0020")
    assert all(f.severity in ("LOW", "INFO") for f in result.flags)
    assert result.rag["identity"]["reasons"] == ["All individual PSCs show verified identity"]


def test_identity_is_not_applicable_when_there_are_no_individuals():
    from tests.test_analysis import FakeProvider, company

    result = build_ownership(FakeProvider({"00000001": company("T")}, {}), "00000001", today=TODAY)
    assert result.rag["identity"]["rag"] == "NA"
    assert result.overall_rag == "RED"  # no PSC data on the target is a high flag


def test_unresolved_share_flag_scales_with_exposure():
    result = run("DEMO0001")
    flag = next(f for f in result.flags if f.code == "UNRESOLVED_SHARE")
    assert flag.severity == "MEDIUM"  # 37.5% is under the 50% line


def test_person_in_two_places_keeps_the_worse_identity_status():
    from tests.test_analysis import S50, S75, FakeProvider, company, corp

    def psc(idv):
        return {"kind": "individual-person-with-significant-control", "name": "Shared", "natures_of_control": [S75],
                "date_of_birth": {"year": 1970, "month": 3}, "identity_verification_details": idv}

    pscs = {
        "00000001": [corp("A", "00000002", [S50]), corp("B", "00000003", [S50])],
        "00000002": [psc({"appointment_verification_start_on": "2026-01-01"})],
        "00000003": [psc({"appointment_verification_statement_due_on": "2026-10-01"})],
    }
    companies = {n: company(n) for n in ("00000001", "00000002", "00000003")}
    result = build_ownership(FakeProvider(companies, pscs), "00000001", today=TODAY)
    assert result.people[0].idv_status == "OVERDUE"


def test_ceased_psc_is_not_assessed_for_identity():
    from tests.test_analysis import S75, FakeProvider, company, person

    ceased = person("Gone", [S75], ceased_on="2024-01-01")
    result = build_ownership(FakeProvider({"00000001": company("T")}, {"00000001": [ceased]}), "00000001",
                             include_ceased=True, today=TODAY)
    assert next(n for n in result.nodes.values() if n.name == "Gone").idv_status is None


def test_many_entities_raise_a_complexity_flag():
    from tests.test_analysis import S75, FakeProvider, company, corp, person

    companies = {f"0000000{i}": company(f"Co{i}") for i in range(1, 8)}
    pscs = {"00000001": [corp(f"Co{i}", f"0000000{i}", [S75]) for i in range(2, 8)]}
    for i in range(2, 8):
        pscs[f"0000000{i}"] = [person(f"P{i}", [S75], birth=(1980, i))]
    result = build_ownership(FakeProvider(companies, pscs), "00000001", today=TODAY)
    assert "COMPLEX_STRUCTURE" in {f.code for f in result.flags}


# -------------------------------------------------------------------- outputs
def test_graph_shows_identity_status_and_overdue_filings():
    dot = to_dot(run("DEMO0001"))
    assert "ID overdue" in dot and "ID verified" in dot and "filing overdue" in dot


def test_markdown_has_rag_summary_and_filing_table():
    text = to_markdown(run("DEMO0001"))
    assert "## RAG summary" in text and "Overall: **RED**" in text
    assert "## Companies, filings and status" in text
    assert "Companies House identity verification" in text


def test_company_rows_list_each_company_nearest_first():
    rows = company_rows(run("DEMO0001"))
    assert [r["Number"] for r in rows] == ["DEMO0001", "DEMO0002", "DEMO0003"]
    assert rows[0]["Accounts"].startswith("OVERDUE")


def test_rag_card_uses_shape_and_colour_and_escapes():
    html = theme.rag_card("Label <b>", "RED", ["<script>x</script>"])
    assert theme.RAG_COLOURS["RED"] in html and theme.RAG_SYMBOLS["RED"] in html
    assert "<script>" not in html and "&lt;b&gt;" in html
    overall = theme.rag_card("Overall", "GREEN", [], overall=True)
    assert "ot-rag-overall" in overall
