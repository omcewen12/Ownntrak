import json

import pytest

from ubo_mapper.analysis import build_ownership
from ubo_mapper.client import BASE_URL, CompaniesHouseClient, CompaniesHouseError
from ubo_mapper.demo import DemoProvider
from ubo_mapper.graph import to_dot
from ubo_mapper.report import to_json, to_markdown


class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status_code, self._payload, self.headers = status, payload, headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


def client(responses, **kwargs):
    session = FakeSession(responses)
    sleeps = []
    return CompaniesHouseClient("secret-key", session=session, sleep=sleeps.append, **kwargs), session, sleeps


def test_key_is_sent_as_basic_auth_username_with_blank_password():
    c, session, _ = client([FakeResponse(200, {"company_name": "X"})])
    c.get_company("00000001")
    url, kwargs = session.requests[0]
    assert url == f"{BASE_URL}/company/00000001"
    assert kwargs["auth"] == ("secret-key", "")


def test_404_returns_none_and_is_cached():
    c, session, _ = client([FakeResponse(404)])
    assert c.get_company("00000001") is None
    assert c.get_company("00000001") is None
    assert len(session.requests) == 1


def test_rate_limit_retries_with_retry_after_then_succeeds():
    c, session, sleeps = client([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, {"ok": 1})])
    assert c.get_company("00000001") == {"ok": 1}
    assert sleeps == [7.0]


def test_persistent_rate_limit_raises_helpful_error():
    c, _, _ = client([FakeResponse(429)] * 3, max_retries=2)
    with pytest.raises(CompaniesHouseError, match="600 requests"):
        c.get_company("00000001")


def test_bad_key_raises_without_leaking_the_key():
    c, _, _ = client([FakeResponse(401)])
    with pytest.raises(CompaniesHouseError) as error:
        c.get_company("00000001")
    assert "secret-key" not in str(error.value)


def test_missing_key_is_rejected():
    with pytest.raises(ValueError):
        CompaniesHouseClient("   ")


def test_psc_pagination_collects_every_page():
    page1 = {"items": [{"name": "a"}, {"name": "b"}], "total_results": 3}
    page2 = {"items": [{"name": "c"}], "total_results": 3}
    c, session, _ = client([FakeResponse(200, page1), FakeResponse(200, page2)])
    assert [i["name"] for i in c.get_pscs("00000001")] == ["a", "b", "c"]
    assert session.requests[1][1]["params"]["start_index"] == 2


def test_no_psc_endpoint_404_means_empty_list():
    c, _, _ = client([FakeResponse(404)])
    assert c.get_pscs("00000001") == []


# ----------------------------------------------------------------- outputs
def test_markdown_report_contains_key_sections():
    text = to_markdown(build_ownership(DemoProvider(), "DEMO0001", source="Fictional demo data"))
    for expected in ("# Ownership review", "## Natural persons", "## Unresolved owners",
                     "## Red flags", "## Limitations", "Jordan Ellis"):
        assert expected in text


def test_json_report_is_valid_and_complete():
    payload = json.loads(to_json(build_ownership(DemoProvider(), "DEMO0010")))
    assert {"company", "people", "unresolved", "flags", "edges", "nodes"} <= payload.keys()


def test_dot_output_is_well_formed_and_marks_unresolved_nodes():
    dot = to_dot(build_ownership(DemoProvider(), "DEMO0001"))
    assert dot.startswith("digraph") and dot.rstrip().endswith("}")
    assert "dashed" in dot
    assert "25-50%" in dot


# ------------------------------------------------------------------- theme
def test_theme_escapes_untrusted_text():
    from ubo_mapper import theme

    nasty = '<script>alert("x")</script> & Co'
    for html in (
        theme.company_header(nasty, nasty, nasty, nasty, nasty),
        theme.flag_card("HIGH", nasty, nasty),
        theme.stat_card(nasty, nasty, "#fff"),
    ):
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


def test_brand_requirements_are_in_the_markup():
    from ubo_mapper import theme

    assert "OwnnTrak" in theme.hero() and "by OSH Ventures" in theme.hero()
    assert "Comic Sans" in theme.CSS and theme.PINK in "#FF6FB5"
    assert "Plus Jakarta Sans" in theme.CSS
    assert "#B96545" in theme.CSS  # OSH Ventures terracotta


def test_unknown_severity_falls_back_to_info_colour():
    from ubo_mapper import theme

    assert theme.SEVERITY_COLOURS["INFO"] in theme.flag_card("WHATEVER", "t", "d")
