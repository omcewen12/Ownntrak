"""Entirely fictional demonstration data.

Every company, person and registration number below is invented. Company numbers start
with DEMO so they can never be mistaken for real records. The shapes mirror what the
Companies House API returns, so the same analysis code runs on this data and on live data.

Dates are generated relative to today, so the overdue and due soon examples always
demonstrate what they say they do.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

SHARES_25_50 = "ownership-of-shares-25-to-50-percent"
SHARES_50_75 = "ownership-of-shares-50-to-75-percent"
SHARES_75_100 = "ownership-of-shares-75-to-100-percent"
APPOINT = "right-to-appoint-and-remove-directors"

DEMO_LABELS = {
    "DEMO0001": "Harbourline Logistics: layered chain, BVI owner, overdue accounts (RED)",
    "DEMO0010": "Fenwick Retail Group: circular ownership, trust, liquidation (RED)",
    "DEMO0030": "Brightwater Studios: two layers, ID and filings due soon (AMBER)",
    "DEMO0020": "Plain Cup Coffee: one verified owner, filings up to date (GREEN)",
}


def _corporate(name, reg, natures, country="England and Wales", authority="Companies Act 2006"):
    return {
        "kind": "corporate-entity-person-with-significant-control",
        "name": name,
        "natures_of_control": natures,
        "notified_on": "2019-04-01",
        "identification": {
            "legal_authority": authority,
            "legal_form": "Limited company",
            "country_registered": country,
            "registration_number": reg,
        },
    }


def _individual(name, natures, idv, birth=(1980, 5), residence="England"):
    return {
        "kind": "individual-person-with-significant-control",
        "name": name,
        "natures_of_control": natures,
        "notified_on": "2019-04-01",
        "date_of_birth": {"year": birth[0], "month": birth[1]},
        "nationality": "British",
        "country_of_residence": residence,
        "identity_verification_details": idv,
    }


class DemoProvider:
    """Mimics CompaniesHouseClient using the fictional data above."""

    calls = 0

    def __init__(self, today: Optional[date] = None):
        self.today = today or date.today()
        self._companies, self._pscs, self._statements = self._build()

    # ----------------------------------------------------------- date helpers
    def _on(self, offset_days: int) -> str:
        return (self.today + timedelta(days=offset_days)).isoformat()

    def _verified(self):
        return {"appointment_verification_start_on": self._on(-120)}

    def _due(self, in_days: int):
        return {"appointment_verification_statement_due_on": self._on(in_days)}

    def _profile(self, name, created, accounts_due, cs_due, accounts_overdue=False, status="active"):
        return {
            "company_name": name, "company_status": status, "date_of_creation": created,
            "jurisdiction": "england-wales",
            "accounts": {"next_due": self._on(accounts_due), "overdue": accounts_overdue},
            "confirmation_statement": {"next_due": self._on(cs_due), "overdue": False},
        }

    # ------------------------------------------------------------------ data
    def _build(self):
        companies = {
            # 1. Layered structure with an offshore link, overdue accounts and an overdue ID check
            "DEMO0001": self._profile("Harbourline Logistics Ltd (fictional)", "2015-03-12", -45, 60, accounts_overdue=True),
            "DEMO0002": self._profile("Northgate Holdings Ltd (fictional)", "2012-09-30", 200, 20),
            "DEMO0003": self._profile("Alder Bridge Investments Ltd (fictional)", "2018-01-22", 150, 120),
            # 2. Circular ownership, a trust, and a company in liquidation
            "DEMO0010": self._profile("Fenwick Retail Group Ltd (fictional)", "2010-06-14", 120, 90),
            "DEMO0011": self._profile("Quill Street Nominees Ltd (fictional)", "2021-11-02", 100, 80),
            "DEMO0012": self._profile("Wren Hill Estates Ltd (fictional)", "2009-02-18", 0, 0, status="liquidation"),
            # 3. Simple and fully in order
            "DEMO0020": self._profile("Plain Cup Coffee Ltd (fictional)", "2016-05-09", 150, 90),
            # 4. Two layers with things coming due
            "DEMO0030": self._profile("Brightwater Studios Ltd (fictional)", "2017-08-21", 140, 12),
            "DEMO0031": self._profile("Brightwater Holdings Ltd (fictional)", "2017-08-01", 160, 110),
        }
        pscs = {
            "DEMO0001": [_corporate("Northgate Holdings Ltd (fictional)", "DEMO0002", [SHARES_75_100])],
            "DEMO0002": [
                _corporate("Alder Bridge Investments Ltd (fictional)", "DEMO0003", [SHARES_50_75]),
                _individual("Jordan Ellis", [SHARES_25_50], self._verified(), birth=(1974, 8)),
            ],
            "DEMO0003": [
                _individual("Casey Morgan", [SHARES_50_75], self._due(-10), birth=(1969, 2)),
                _corporate("Meridian Ventures Ltd (fictional)", "VG-000123", [SHARES_25_50],
                           country="British Virgin Islands", authority="BVI Business Companies Act"),
            ],
            "DEMO0010": [
                _corporate("Quill Street Nominees Ltd (fictional)", "DEMO0011", [SHARES_50_75]),
                _individual("Riley Hart", [APPOINT], self._due(12), birth=(1985, 11)),
            ],
            "DEMO0011": [
                _corporate("Fenwick Retail Group Ltd (fictional)", "DEMO0010", [SHARES_25_50]),
                _corporate("Wren Hill Estates Ltd (fictional)", "DEMO0012", [SHARES_25_50, SHARES_25_50 + "-as-trust"]),
            ],
            "DEMO0012": [],
            "DEMO0020": [_individual("Morgan Lake", [SHARES_75_100], self._verified(), birth=(1978, 3))],
            "DEMO0030": [
                _corporate("Brightwater Holdings Ltd (fictional)", "DEMO0031", [SHARES_50_75]),
                _individual("Sam Rowe", [SHARES_25_50], self._due(20), birth=(1982, 9)),
            ],
            "DEMO0031": [_individual("Alex Quinn", [SHARES_75_100], self._verified(), birth=(1971, 12))],
        }
        statements = {
            "DEMO0012": [{"statement": "psc-details-not-confirmed", "notified_on": self._on(-200)}],
        }
        return companies, pscs, statements

    # ------------------------------------------------------------ provider API
    def get_company(self, number: str):
        return self._companies.get(number)

    def get_pscs(self, number: str) -> list:
        return self._pscs.get(number, [])

    def get_psc_statements(self, number: str) -> list:
        return self._statements.get(number, [])

    def get_exemptions(self, number: str) -> dict:
        return {}
