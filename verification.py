"""Companies House identity verification status for individual PSCs.

Since 18 November 2025 identity verification has been mandatory for new PSCs, with a
12 month transition period for existing ones that ends on 17 November 2026. The public
API publishes an optional ``identity_verification_details`` object on individual PSCs.
The fields used here are the ones documented in the Companies House API specification:

- appointment_verification_start_on: date the verification statement was supplied
- appointment_verification_end_on: date the statement was removed
- appointment_verification_statement_due_on: date by which a statement must be supplied
- identity_verified_on: date an authorised corporate service provider verified the identity

This is Companies House's own verification, which is separate from the identity checks
a firm carries out on its own customers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

TRANSITION_END = date(2026, 11, 17)

VERIFIED = "VERIFIED"
NOT_VERIFIED = "NOT_VERIFIED"
OVERDUE = "OVERDUE"

STATUS_RANK = {VERIFIED: 0, NOT_VERIFIED: 1, OVERDUE: 2}
STATUS_RAG = {VERIFIED: "GREEN", NOT_VERIFIED: "AMBER", OVERDUE: "RED"}
SHORT_LABELS = {VERIFIED: "ID verified", NOT_VERIFIED: "ID not verified", OVERDUE: "ID overdue"}


@dataclass
class IdvStatus:
    status: str
    rag: str
    label: str


def parse_date(text) -> Optional[date]:
    if not text:
        return None
    try:
        return datetime.strptime(str(text)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _fmt(value: date) -> str:
    return value.strftime("%d %b %Y")


def _days(count: int) -> str:
    return f"{count} day" + ("" if count == 1 else "s")


def assess_identity(details: Optional[dict], today: date, transition_end: date = TRANSITION_END) -> IdvStatus:
    """Turn the register's verification fields into a status, a RAG colour and a plain label."""
    data = details or {}
    start = parse_date(data.get("appointment_verification_start_on"))
    end = parse_date(data.get("appointment_verification_end_on"))
    verified_on = parse_date(data.get("identity_verified_on"))
    due = parse_date(data.get("appointment_verification_statement_due_on"))

    removed = bool(end and (not start or end >= start))
    if start and not removed:
        return IdvStatus(VERIFIED, "GREEN", f"Verified (statement supplied {_fmt(start)})")
    if verified_on:
        return IdvStatus(VERIFIED, "GREEN", f"Verified by an authorised corporate service provider on {_fmt(verified_on)}")

    prefix = f"Statement removed {_fmt(end)}. " if removed else ""
    if due:
        delta = (due - today).days
        if delta < 0:
            return IdvStatus(OVERDUE, "RED", f"{prefix}Overdue by {_days(-delta)} (was due {_fmt(due)})")
        return IdvStatus(NOT_VERIFIED, "AMBER", f"{prefix}Not verified, due {_fmt(due)} (in {_days(delta)})")

    if today > transition_end:
        return IdvStatus(OVERDUE, "RED", f"{prefix}Not verified and the transition period ended on {_fmt(transition_end)}")
    left = (transition_end - today).days
    return IdvStatus(
        NOT_VERIFIED, "AMBER",
        f"{prefix}No verification recorded; transition period ends {_fmt(transition_end)} (in {_days(left)})",
    )


def worse(first: Optional[str], second: Optional[str]) -> Optional[str]:
    """Return whichever status is more serious. None means 'not assessed'."""
    if first is None:
        return second
    if second is None:
        return first
    return first if STATUS_RANK[first] >= STATUS_RANK[second] else second
