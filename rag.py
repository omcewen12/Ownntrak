"""Red, amber and green ratings.

Every red flag belongs to one of four dimensions. A dimension is RED if it holds any HIGH
flag, AMBER if it holds any MEDIUM flag, and GREEN otherwise. LOW and INFO flags are shown
but do not change the colour. The overall rating is the worst of the four. Keeping the rule
this plain means every colour can be traced back to named flags.
"""
from __future__ import annotations

from collections import Counter

from .models import OwnershipResult

DIMENSIONS = [
    ("structure", "Structure complexity"),
    ("transparency", "Transparency"),
    ("identity", "Identity verification"),
    ("filings", "Filings and status"),
]

CODE_DIMENSION = {
    # structure
    "OVERSEAS_OWNER": "structure", "CIRCULAR_OWNERSHIP": "structure", "LAYERED_STRUCTURE": "structure",
    "TRUST_OR_FIRM": "structure", "PERSON_RESIDENCE_RISK": "structure", "COMPLEX_STRUCTURE": "structure",
    # transparency
    "NO_PSC_DATA": "transparency", "PSC_STATEMENT": "transparency", "PSC_EXEMPT": "transparency",
    "SUPER_SECURE_PSC": "transparency", "LEGAL_PERSON": "transparency", "UNIDENTIFIED_CORPORATE": "transparency",
    "COMPANY_NOT_FOUND": "transparency", "UNKNOWN_PSC_TYPE": "transparency", "UNRESOLVED_SHARE": "transparency",
    "DEPTH_LIMIT": "transparency",
    # identity verification
    "IDV_OVERDUE": "identity", "IDV_NOT_VERIFIED": "identity",
    # filings and status
    "COMPANY_NOT_ACTIVE": "filings", "ACCOUNTS_OVERDUE": "filings", "CONFIRMATION_OVERDUE": "filings",
    "FILING_DUE_SOON": "filings", "STRIKE_OFF_PROPOSED": "filings", "OFFICE_UNDELIVERABLE": "filings",
    "OFFICE_IN_DISPUTE": "filings", "INSOLVENCY_HISTORY": "filings", "RECENT_INCORPORATION": "filings",
}

RAG_ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}
SEVERITY_TO_RAG = {"HIGH": "RED", "MEDIUM": "AMBER"}


def _reasons(flags: list, severity: str) -> list:
    counts = Counter(f.title for f in flags if f.severity == severity)
    return [title if n == 1 else f"{title} (x{n})" for title, n in counts.items()]


def apply_rag(result: OwnershipResult) -> None:
    for flag in result.flags:
        flag.dimension = CODE_DIMENSION.get(flag.code, "structure")

    has_individuals = any(n.kind in ("individual", "super_secure") for n in result.nodes.values())
    result.rag = {}
    for key, label in DIMENSIONS:
        flags = [f for f in result.flags if f.dimension == key]
        if key == "identity" and not has_individuals:
            result.rag[key] = {"label": label, "rag": "NA", "reasons": ["No individual PSCs to check"]}
            continue
        if any(f.severity == "HIGH" for f in flags):
            rag, reasons = "RED", _reasons(flags, "HIGH")
        elif any(f.severity == "MEDIUM" for f in flags):
            rag, reasons = "AMBER", _reasons(flags, "MEDIUM")
        else:
            rag = "GREEN"
            reasons = ["All individual PSCs show verified identity"] if key == "identity" else ["No issues found"]
        result.rag[key] = {"label": label, "rag": rag, "reasons": reasons}

    scored = [d for d in result.rag.values() if d["rag"] != "NA"]
    worst = max((d["rag"] for d in scored), key=lambda r: RAG_ORDER[r], default="GREEN")
    result.overall_rag = worst
    result.overall_reasons = [d["label"] for d in scored if d["rag"] == worst] if worst != "GREEN" else []
