"""Plain text and markdown reporting, designed to be saved as a working paper."""
from __future__ import annotations

import json
from dataclasses import asdict

from .filings import describe
from .models import OwnershipResult

CLASS_LABELS = {
    "LIKELY_UBO": "Likely UBO (25% or more even at the low end)",
    "POSSIBLE_UBO": "Possible UBO (range spans 25%)",
    "CONTROL": "Control without a share band",
    "BELOW_THRESHOLD": "Below 25%",
}

LIMITATIONS = [
    "Companies House publishes ownership in bands, so results are ranges, not exact percentages.",
    "PSC data is self reported by companies and is not verified by Companies House.",
    "The chain stops at overseas, protected or unidentified owners. These are listed as unresolved.",
    "Individuals are merged across companies only when name and month and year of birth match.",
    "Identity verification shown is Companies House's own, taken from the public register. It is not a substitute for your own customer identity checks.",
    "A missing identity verification record can mean the person has not verified or that the register has not yet been updated.",
    "This is a research aid and does not replace customer due diligence or professional judgement.",
]


def company_rows(result: OwnershipResult) -> list:
    """One row per UK company in the structure, nearest the target first."""
    rows = []
    for node in sorted(result.nodes.values(), key=lambda n: n.depth):
        if node.kind != "company" or not node.filings:
            continue
        notes = []
        if node.filings.get("strike_off"):
            notes.append("Proposal to strike off")
        if node.filings.get("undeliverable_office"):
            notes.append("Registered office undeliverable")
        if node.filings.get("office_in_dispute"):
            notes.append("Registered office in dispute")
        if node.filings.get("insolvency_history"):
            notes.append("Insolvency history")
        if node.note:
            notes.append(node.note)
        rows.append({
            "Company": node.name,
            "Number": node.company_number,
            "Status": node.status or "unknown",
            "Accounts": describe(node.filings.get("accounts")),
            "Confirmation statement": describe(node.filings.get("confirmation_statement")),
            "Notes": "; ".join(notes),
        })
    return rows


def to_markdown(result: OwnershipResult) -> str:
    root = result.root
    out = [
        f"# Ownership review: {root.name}",
        "",
        "Prepared with OwnnTrak by OSH Ventures.",
        "",
        f"- Company number: {root.company_number}",
        f"- Status: {root.status or 'unknown'}",
        f"- Source: {result.source}",
        f"- Generated: {result.generated_at}",
        f"- Depth followed: {result.params.get('max_depth')} levels",
        "",
        "## RAG summary",
        "",
        f"Overall: **{result.overall_rag}**",
        "",
        "| Area | Rating | Why |",
        "|---|---|---|",
    ]
    for item in result.rag.values():
        out.append(f"| {item['label']} | {item['rag']} | {'; '.join(item['reasons'])} |")
    out += ["", "A dimension is RED if it holds any high flag, AMBER if it holds any medium flag, and GREEN otherwise.", "",
            "## Natural persons", ""]
    if result.people:
        out += ["| Person | Estimated ownership | Assessment | Companies House identity verification |", "|---|---|---|---|"]
        for p in result.people:
            share = "No share band" if p.high == 0 else f"{p.low:.1f}% to {p.high:.1f}%"
            out.append(f"| {p.name} | {share} | {CLASS_LABELS[p.classification]} | {p.idv_label or 'Not assessed'} |")
        out.append("")
        for p in result.people:
            for route in p.routes + p.control_routes:
                out.append(f"- {route}")
        out.append("")
    else:
        out += ["No natural persons could be identified from public data.", ""]

    rows = company_rows(result)
    if rows:
        out += ["## Companies, filings and status", "",
                "| Company | Status | Accounts | Confirmation statement |", "|---|---|---|---|"]
        for row in rows:
            out.append(f"| {row['Company']} ({row['Number']}) | {row['Status']} | {row['Accounts']} | {row['Confirmation statement']} |")
        out.append("")

    out += ["## Unresolved owners", ""]
    if result.unresolved:
        out += ["| Entity | Up to | Why unresolved |", "|---|---|---|"]
        for u in result.unresolved:
            where = f" ({u.country})" if u.country else ""
            out.append(f"| {u.name}{where} | {u.high:.1f}% | {u.reason} |")
        out.append("")
    else:
        out += ["None. Every owner was traced to a natural person.", ""]

    out += ["## Red flags", ""]
    if result.flags:
        for f in result.flags:
            out.append(f"- **{f.severity}** {f.title}. {f.detail}")
        out.append("")
    else:
        out += ["No flags raised.", ""]

    out += ["## Limitations", ""] + [f"- {item}" for item in LIMITATIONS]
    return "\n".join(out) + "\n"


def to_json(result: OwnershipResult) -> str:
    payload = {
        "company": asdict(result.root),
        "generated_at": result.generated_at,
        "source": result.source,
        "params": result.params,
        "people": [asdict(p) for p in result.people],
        "unresolved": [asdict(u) for u in result.unresolved],
        "flags": [asdict(f) for f in result.flags],
        "edges": [asdict(e) for e in result.edges],
        "nodes": {k: asdict(v) for k, v in result.nodes.items()},
    }
    return json.dumps(payload, indent=2)
