"""Filing timeliness and company status checks from the Companies House company profile.

Uses the ``accounts`` and ``confirmation_statement`` blocks of the company profile, which
carry a ``next_due`` date and an ``overdue`` flag, plus a handful of status fields.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from .models import Flag, Node
from .verification import parse_date

DUE_SOON_DAYS = 30
CLOSED_STATUSES = {"dissolved", "closed", "converted-closed", "removed"}

_LABELS = {"accounts": "Accounts", "confirmation_statement": "Confirmation statement"}
_CODES = {"accounts": "ACCOUNTS_OVERDUE", "confirmation_statement": "CONFIRMATION_OVERDUE"}


def _block(profile: dict, key: str, today: date) -> Optional[dict]:
    block = profile.get(key)
    if not isinstance(block, dict):
        return None
    due = parse_date(block.get("next_due"))
    flag = block.get("overdue")
    overdue = flag if isinstance(flag, bool) else (due is not None and due < today)
    if due is None and not overdue:
        return None
    return {
        "due_on": due.isoformat() if due else None,
        "overdue": bool(overdue),
        "days": (due - today).days if due else None,  # negative when the date has passed
    }


def summarise(profile: dict, today: date) -> dict:
    """A small, serialisable summary stored on the company node."""
    return {
        "accounts": _block(profile, "accounts", today),
        "confirmation_statement": _block(profile, "confirmation_statement", today),
        "strike_off": "strike" in (profile.get("company_status_detail") or "").casefold(),
        "undeliverable_office": bool(profile.get("undeliverable_registered_office_address")),
        "office_in_dispute": bool(profile.get("registered_office_is_in_dispute")),
        "insolvency_history": bool(profile.get("has_insolvency_history")),
    }


def describe(info: Optional[dict]) -> str:
    """Plain wording for a table cell."""
    if not info:
        return "Not reported"
    days, due = info.get("days"), info.get("due_on")
    if info.get("overdue"):
        if days is not None:
            late = -days
            return f"OVERDUE since {due} ({late} day{'s' if late != 1 else ''})"
        return "OVERDUE"
    if due:
        return f"Due {due} (in {days} day{'s' if days != 1 else ''})" if days is not None else f"Due {due}"
    return "Not reported"


def filing_flags(node: Node, today: date) -> list:
    """Red flags for one company. Closed companies are skipped because nothing is due."""
    info = node.filings
    if not info or (node.status or "").casefold() in CLOSED_STATUSES:
        return []

    flags: list = []
    for key in ("accounts", "confirmation_statement"):
        item = info.get(key)
        if not item:
            continue
        label = _LABELS[key]
        if item["overdue"]:
            how_late = ""
            if item["days"] is not None and item["days"] < 0:
                how_late = f", {-item['days']} days ago"
            flags.append(Flag(
                _CODES[key], "HIGH", f"{label} overdue",
                f"{node.name}: {label.lower()} {'were' if key == 'accounts' else 'was'} due on "
                f"{item['due_on'] or 'an unstated date'}{how_late}.",
                node.id,
            ))
        elif item["days"] is not None and 0 <= item["days"] <= DUE_SOON_DAYS:
            flags.append(Flag(
                "FILING_DUE_SOON", "MEDIUM", f"{label} due soon",
                f"{node.name}: {label.lower()} due on {item['due_on']} (in {item['days']} days).",
                node.id,
            ))

    if info.get("strike_off"):
        flags.append(Flag(
            "STRIKE_OFF_PROPOSED", "HIGH", "Proposal to strike off",
            f"{node.name} is shown with a proposal to strike off the register.", node.id,
        ))
    if info.get("undeliverable_office"):
        flags.append(Flag(
            "OFFICE_UNDELIVERABLE", "MEDIUM", "Registered office address undeliverable",
            f"{node.name} has a registered office address marked as undeliverable.", node.id,
        ))
    if info.get("office_in_dispute"):
        flags.append(Flag(
            "OFFICE_IN_DISPUTE", "MEDIUM", "Registered office in dispute",
            f"The registered office of {node.name} is marked as in dispute.", node.id,
        ))
    if info.get("insolvency_history"):
        flags.append(Flag(
            "INSOLVENCY_HISTORY", "LOW", "Insolvency history",
            f"{node.name} has an insolvency history on the register.", node.id,
        ))
    return flags
