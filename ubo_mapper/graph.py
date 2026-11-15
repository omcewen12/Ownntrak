"""Render an OwnershipResult as Graphviz DOT, which Streamlit can draw natively.

Colours follow the OwnnTrak by OSH Ventures palette so the map matches the app.
"""
from __future__ import annotations

from .analysis import band_text
from .models import (
    KIND_COMPANY,
    KIND_INDIVIDUAL,
    KIND_LEGAL_PERSON,
    KIND_SUPER_SECURE,
    OwnershipResult,
)
from .theme import CLAY, CORAL, IVORY, PINK, RAG_COLOURS, SAGE_LIGHT, TERRACOTTA
from .verification import SHORT_LABELS


def _esc(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace('"', '\\"')


def to_dot(result: OwnershipResult, background: str = "transparent") -> str:
    risky = {f.node_id for f in result.flags if f.severity == "HIGH" and f.node_id}
    unresolved = {u.node_id for u in result.unresolved}

    lines = [
        "digraph ownership {",
        '  rankdir="BT";',
        f'  graph [pad="0.3", nodesep="0.5", ranksep="0.75", bgcolor="{background}"];',
        f'  node [fontname="Helvetica", fontsize=11, style="filled,rounded", shape=box, fillcolor="#2B1A15", '
        f'color="{CLAY}", fontcolor="{IVORY}", margin="0.18,0.1"];',
        f'  edge [fontname="Helvetica", fontsize=10, color="{CLAY}", fontcolor="{IVORY}", arrowsize=0.8];',
    ]

    for node_id, node in result.nodes.items():
        parts = [node.name]
        if node.company_number and node.kind == KIND_COMPANY:
            parts.append(node.company_number)
        if node.kind == KIND_INDIVIDUAL and node.birth:
            parts.append(f"born {node.birth}")
        if node.country and node.kind not in (KIND_INDIVIDUAL, KIND_COMPANY):
            parts.append(node.country)
        if node.kind == KIND_INDIVIDUAL and node.idv_status:
            parts.append(SHORT_LABELS[node.idv_status])
        if node.kind == KIND_COMPANY and any((node.filings.get(k) or {}).get("overdue")
                                             for k in ("accounts", "confirmation_statement")):
            parts.append("filing overdue")
        label = "\\n".join(_esc(part) for part in parts)  # DOT reads \n as a line break

        attrs = [f'label="{label}"']
        if node.kind == KIND_INDIVIDUAL:
            attrs += ["shape=ellipse", 'style="filled"', 'fillcolor="#33402F"',
                      f'color="{RAG_COLOURS.get(node.idv_rag, SAGE_LIGHT)}"']
        elif node.kind in (KIND_SUPER_SECURE, KIND_LEGAL_PERSON):
            attrs += ['fillcolor="#3A302B"', 'color="#BFB3A5"']
        if node_id == result.root_id:
            attrs += [f'fillcolor="{TERRACOTTA}"', f'color="{IVORY}"', "penwidth=2", f'fontcolor="#FFFFFF"']
        if node_id in unresolved:
            attrs += ['style="filled,rounded,dashed"', 'fillcolor="#3B2230"', f'color="{PINK}"', "penwidth=1.6"]
        if node_id in risky:
            attrs += [f'color="{CORAL}"', "penwidth=2.4"]
        lines.append(f'  "{_esc(node_id)}" [{", ".join(attrs)}];')

    for edge in result.edges:
        label = band_text(edge.band)
        if edge.band is None and edge.control_rights:
            label = "control"
        if edge.as_trust:
            label += " (trust)"
        if edge.as_firm:
            label += " (firm)"
        style = "solid" if edge.active else "dotted"
        lines.append(
            f'  "{_esc(edge.owner)}" -> "{_esc(edge.owned)}" [label="{_esc(label)}", style={style}];'
        )

    lines.append("}")
    return "\n".join(lines)
