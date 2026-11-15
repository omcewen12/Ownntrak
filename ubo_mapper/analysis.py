"""Ownership tracing, effective ownership ranges and red flag logic.

The public Companies House register publishes ownership as bands (25 to 50,
50 to 75 and 75 to 100 percent) rather than exact figures. Everything in this
module therefore works with ranges. A person is only called a "likely" UBO when
even the lowest end of the range clears the 25 percent threshold.
"""
from __future__ import annotations

import json
import re
from collections import deque
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import networkx as nx

from .client import CompanyNotFound, normalise_company_number
from .filings import filing_flags, summarise as summarise_filings
from .models import (
    KIND_COMPANY,
    KIND_INDIVIDUAL,
    KIND_LEGAL_PERSON,
    KIND_NOT_FOUND,
    KIND_OVERSEAS,
    KIND_SUPER_SECURE,
    KIND_UNVERIFIED,
    SEVERITY_RANK,
    Edge,
    Flag,
    Node,
    OwnershipResult,
    PersonResult,
    UnresolvedResult,
)
from .rag import apply_rag
from .verification import STATUS_RANK, assess_identity, parse_date as _parse_date

UBO_THRESHOLD = 25.0
MAX_PATHS_PER_NODE = 500

UK_NAMES = {
    "england",
    "wales",
    "england and wales",
    "scotland",
    "northern ireland",
    "united kingdom",
    "uk",
    "great britain",
    "gb",
}

JURISDICTION_NAMES = {
    "england-wales": "England and Wales",
    "england": "England",
    "wales": "Wales",
    "scotland": "Scotland",
    "northern-ireland": "Northern Ireland",
    "united-kingdom": "United Kingdom",
}

INACTIVE_STATUSES = {
    "dissolved",
    "liquidation",
    "receivership",
    "administration",
    "voluntary-arrangement",
    "converted-closed",
    "insolvency-proceedings",
    "removed",
    "closed",
}

# Statement codes published by Companies House. Note that the register itself
# spells "significant" wrongly in one of them, so matching is by substring.
STATEMENT_RULES = [
    ("restrictions-notice", "HIGH", "Restrictions notice issued to a PSC",
     "A restrictions notice has been issued, which usually means the company could not obtain the information it asked for."),
    ("psc-has-failed", "MEDIUM", "PSC failed to confirm changed details",
     "The company says a person with significant control has not confirmed updated details."),
    ("psc-contacted-but-no-response", "MEDIUM", "PSC contacted but did not respond",
     "The company has asked a possible PSC for information and received no reply."),
    ("psc-details-not-confirmed", "MEDIUM", "PSC details not confirmed",
     "The company has not been able to confirm its PSC details."),
    ("steps-to-find-psc-not-yet-completed", "MEDIUM", "Steps to identify PSC not yet completed",
     "The company has not finished identifying who has significant control."),
    ("no-individual-or-entity", "MEDIUM", "Company states it has no PSC",
     "The company says nobody meets the PSC conditions. That is possible, but worth testing against its shareholder list."),
]

_SHARES_RE = re.compile(r"(?:ownership-of-shares|right-to-share-surplus-assets)-(\d+)-to-(\d+)-percent")
_VOTING_RE = re.compile(r"voting-rights-(\d+)-to-(\d+)-percent")
_MORE_THAN_RE = re.compile(r"(ownership-of-shares|voting-rights)-more-than-25-percent")


# --------------------------------------------------------------------- helpers
def _norm(text: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (text or "").casefold().replace("-", " ")).strip()


def is_uk(country: Optional[str]) -> bool:
    return _norm(country) in UK_NAMES


def load_jurisdictions(path: Optional[str] = None) -> dict:
    file = Path(path) if path else Path(__file__).resolve().parent / "data" / "jurisdictions.json"
    with open(file, encoding="utf-8") as handle:
        raw = json.load(handle)
    return {
        "call_for_action": {_norm(x) for x in raw.get("call_for_action", [])},
        "offshore_centres": {_norm(x) for x in raw.get("offshore_centres", [])},
    }


def jurisdiction_risk(country: Optional[str], cfg: dict) -> Optional[str]:
    key = _norm(country)
    if not key:
        return None
    if key in cfg["call_for_action"]:
        return "call_for_action"
    if key in cfg["offshore_centres"]:
        return "offshore_centres"
    return None


def parse_natures(natures: list) -> dict:
    """Turn Companies House 'natures of control' strings into structured data."""
    shares = voting = None
    control_rights: list = []
    as_trust = as_firm = False

    def widen(current, low, high):
        if current is None:
            return (low, high)
        return (min(current[0], low), max(current[1], high))

    for nature in natures or []:
        text = nature or ""
        if text.endswith("-as-trust") or "-as-trust" in text:
            as_trust = True
        if text.endswith("-as-firm") or "-as-firm" in text:
            as_firm = True

        match = _SHARES_RE.search(text)
        if match:
            shares = widen(shares, float(match.group(1)), float(match.group(2)))
            continue
        match = _VOTING_RE.search(text)
        if match:
            voting = widen(voting, float(match.group(1)), float(match.group(2)))
            continue
        match = _MORE_THAN_RE.search(text)
        if match:
            if match.group(1) == "ownership-of-shares":
                shares = widen(shares, 25.0, 100.0)
            else:
                voting = widen(voting, 25.0, 100.0)
            continue
        if text.startswith("right-to-appoint") or "significant-influence" in text:
            base = re.sub(r"-as-(trust|firm)$", "", text)
            if base not in control_rights:
                control_rights.append(base)

    return {
        "shares": shares,
        "voting": voting,
        "control_rights": control_rights,
        "as_trust": as_trust,
        "as_firm": as_firm,
    }


def band_text(band: Optional[tuple]) -> str:
    if not band:
        return "control"
    low, high = band
    return f"{low:g}-{high:g}%"


def _co_id(number: str) -> str:
    return f"co:{number}"


def _corporate_country(identification: dict) -> Optional[str]:
    country = identification.get("country_registered")
    if country:
        return country
    place = (identification.get("place_registered") or "").casefold()
    if "companies house" in place:
        return "United Kingdom"
    return None


def _is_uk_lookup(identification: dict) -> bool:
    country = _corporate_country(identification)
    if country:
        return is_uk(country)
    authority = (identification.get("legal_authority") or "").casefold()
    return "companies act" in authority


def _person_name(item: dict) -> str:
    if item.get("name"):
        return item["name"]
    elements = item.get("name_elements") or {}
    parts = [elements.get("forename"), elements.get("surname")]
    return " ".join(p for p in parts if p) or "Unnamed person"


def _birth_text(item: dict) -> Optional[str]:
    dob = item.get("date_of_birth") or {}
    if dob.get("year") and dob.get("month"):
        return f"{int(dob['year']):04d}-{int(dob['month']):02d}"
    return None


def _merge_edge(existing: Edge, new: Edge) -> None:
    existing.natures.extend(n for n in new.natures if n not in existing.natures)
    for attr in ("shares", "voting"):
        a, b = getattr(existing, attr), getattr(new, attr)
        if a and b:
            setattr(existing, attr, (min(a[0], b[0]), max(a[1], b[1])))
        elif b:
            setattr(existing, attr, b)
    existing.control_rights.extend(c for c in new.control_rights if c not in existing.control_rights)
    existing.as_trust = existing.as_trust or new.as_trust
    existing.as_firm = existing.as_firm or new.as_firm


# ------------------------------------------------------------------ traversal
def build_ownership(
    provider,
    company_number: str,
    *,
    max_depth: int = 5,
    include_ceased: bool = False,
    jurisdictions: Optional[dict] = None,
    today: Optional[date] = None,
    source: str = "Companies House API",
) -> OwnershipResult:
    """Trace who owns and controls a company, following UK corporate owners upwards.

    ``max_depth`` is the number of ownership levels above the target company to
    follow. ``provider`` needs get_company, get_pscs, get_psc_statements and
    get_exemptions methods, which both the live client and the demo data have.
    """
    today = today or date.today()
    cfg = jurisdictions if jurisdictions is not None else load_jurisdictions()
    root_no = normalise_company_number(company_number)

    profile = provider.get_company(root_no)
    if profile is None:
        raise CompanyNotFound(f"No company found with number {root_no}.")

    result = OwnershipResult(
        root_id=_co_id(root_no),
        params={"company_number": root_no, "max_depth": max_depth, "include_ceased": include_ceased},
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        source=source,
    )
    result.nodes[result.root_id] = _company_node(profile, root_no, depth=0)
    result.nodes[result.root_id].filings = summarise_filings(profile, today)

    edges: dict = {}
    expanded: set = set()
    queue: deque = deque([(root_no, 0)])

    while queue:
        number, depth = queue.popleft()
        if number in expanded:
            continue
        expanded.add(number)
        owned_id = _co_id(number)
        owned = result.nodes[owned_id]

        if depth > 0:
            fetched = provider.get_company(number)
            if fetched is None:
                owned.kind = KIND_NOT_FOUND
                owned.note = "Registration number did not resolve at Companies House"
                result.flags.append(Flag(
                    "COMPANY_NOT_FOUND", "MEDIUM", "Owner company not found",
                    f"{owned.name} ({number}) is named as a corporate PSC but could not be looked up.",
                    owned_id,
                ))
                continue
            _refresh_company_node(owned, fetched)
            owned.filings = summarise_filings(fetched, today)

        _check_company_status(result, owned, depth)
        _check_recent_incorporation(result, owned, depth, today)

        pscs = provider.get_pscs(number)
        statements = provider.get_psc_statements(number)
        exemptions = provider.get_exemptions(number)
        active_pscs = [p for p in pscs if not p.get("ceased_on")]
        shown = pscs if include_ceased else active_pscs

        _check_statements(result, owned, statements)
        if exemptions:
            owned.note = "PSC exempt: " + ", ".join(sorted(exemptions))
            result.flags.append(Flag(
                "PSC_EXEMPT", "INFO", "Exempt from PSC rules",
                f"{owned.name} reports a PSC exemption ({', '.join(sorted(exemptions))}). "
                "Check major shareholder disclosures instead.",
                owned_id,
            ))
        elif not active_pscs and _active_statements(statements):
            owned.note = "No PSC identified; see the company's PSC statement"
        elif not active_pscs:
            owned.note = "No PSC data filed"
            result.flags.append(Flag(
                "NO_PSC_DATA", "HIGH" if depth == 0 else "MEDIUM", "No PSC information on the register",
                f"{owned.name} has no active PSC, no PSC statement and no exemption on the register.",
                owned_id,
            ))

        for index, item in enumerate(shown):
            _process_psc(result, edges, queue, owned, number, depth, index, item, max_depth, cfg, today)

    result.edges = list(edges.values())
    _flag_graph_shape(result, cfg, max_depth)
    _compute_effective(result, max_depth)
    _flag_unresolved_share(result)
    _flag_identity(result)
    for node in result.nodes.values():
        if node.kind == KIND_COMPANY:
            result.flags.extend(filing_flags(node, today))
    apply_rag(result)
    result.flags.sort(key=lambda f: (SEVERITY_RANK[f.severity], f.title))
    return result


def _company_node(profile: dict, number: str, depth: int) -> Node:
    node = Node(id=_co_id(number), kind=KIND_COMPANY, name=profile.get("company_name", number),
                company_number=number, depth=depth)
    _refresh_company_node(node, profile)
    return node


def _refresh_company_node(node: Node, profile: dict) -> None:
    node.name = profile.get("company_name") or node.name
    node.status = profile.get("company_status")
    node.incorporated = profile.get("date_of_creation")
    jurisdiction = profile.get("jurisdiction")
    node.country = JURISDICTION_NAMES.get(jurisdiction, jurisdiction) or node.country or "United Kingdom"


def _process_psc(result, edges, queue, owned: Node, owned_number: str, depth: int,
                 index: int, item: dict, max_depth: int, cfg: dict, today: date) -> None:
    kind_text = item.get("kind", "")
    name = _person_name(item) if "individual" in kind_text else (item.get("name") or "Unnamed entity")
    parsed = parse_natures(item.get("natures_of_control", []))
    edge_template = dict(
        natures=list(item.get("natures_of_control", [])),
        shares=parsed["shares"],
        voting=parsed["voting"],
        control_rights=parsed["control_rights"],
        as_trust=parsed["as_trust"],
        as_firm=parsed["as_firm"],
        notified_on=item.get("notified_on"),
        ceased_on=item.get("ceased_on"),
    )
    child_depth = depth + 1

    if "super-secure" in kind_text:
        node = Node(id=f"ss:{owned_number}:{index}", kind=KIND_SUPER_SECURE,
                    name="Identity protected (super secure PSC)", depth=child_depth,
                    note="Identity restricted by law")
        result.flags.append(Flag(
            "SUPER_SECURE_PSC", "MEDIUM", "Super secure PSC",
            f"{owned.name} has a PSC whose identity is hidden by law. It cannot be verified from public data.",
            node.id,
        ))
    elif "individual" in kind_text:
        birth = _birth_text(item)
        key = f"ind:{_norm(name)}:{birth}" if birth else f"ind:{owned_number}:{index}:{_norm(name)}"
        node = result.nodes.get(key) or Node(
            id=key, kind=KIND_INDIVIDUAL, name=name, depth=child_depth,
            nationality=item.get("nationality"), residence=item.get("country_of_residence"), birth=birth,
        )
        residence_risk = jurisdiction_risk(node.residence, cfg)
        if residence_risk and key not in result.nodes:
            severity = "HIGH" if residence_risk == "call_for_action" else "LOW"
            result.flags.append(Flag(
                "PERSON_RESIDENCE_RISK", severity, "Individual resident in an elevated risk jurisdiction",
                f"{name} is shown as resident in {node.residence}.", key,
            ))
    elif "legal-person" in kind_text:
        node = Node(id=f"lp:{_norm(name)}", kind=KIND_LEGAL_PERSON, name=name, depth=child_depth,
                    note="Legal person, not a natural person")
        result.flags.append(Flag(
            "LEGAL_PERSON", "INFO", "Legal person as PSC",
            f"{name} is a legal person (for example a public body). Work out who stands behind it.", node.id,
        ))
    elif "corporate-entity" in kind_text:
        node = _corporate_node(result, queue, owned, depth, name, item, max_depth, cfg)
    else:
        node = Node(id=f"unk:{owned_number}:{index}", kind=KIND_UNVERIFIED, name=name, depth=child_depth,
                    note=f"Unrecognised PSC type '{kind_text}'")
        result.flags.append(Flag(
            "UNKNOWN_PSC_TYPE", "MEDIUM", "Unrecognised PSC type",
            f"The register returned a PSC type this tool does not recognise: '{kind_text}'.", node.id,
        ))

    if node.kind in (KIND_INDIVIDUAL, KIND_SUPER_SECURE) and not item.get("ceased_on"):
        _apply_identity(node, item, today)

    result.nodes.setdefault(node.id, node)
    new_edge = Edge(owner=node.id, owned=owned.id, **edge_template)
    key = (node.id, owned.id)
    if key in edges:
        _merge_edge(edges[key], new_edge)
    else:
        edges[key] = new_edge

    if new_edge.as_trust or new_edge.as_firm:
        label = "trust" if new_edge.as_trust else "firm"
        result.flags.append(Flag(
            "TRUST_OR_FIRM", "MEDIUM", f"Interest held as a {label}",
            f"{node.name} holds its interest in {owned.name} as a {label}. "
            "Settlors, beneficiaries and protectors are not shown in PSC data.", node.id,
        ))


def _corporate_node(result, queue, owned: Node, depth: int, name: str, item: dict,
                    max_depth: int, cfg: dict) -> Node:
    ident = item.get("identification") or {}
    reg = normalise_company_number(ident.get("registration_number") or "")
    country = _corporate_country(ident)
    child_depth = depth + 1

    if _is_uk_lookup(ident) and reg:
        node_id = _co_id(reg)
        node = result.nodes.get(node_id)
        if node is None:
            node = Node(id=node_id, kind=KIND_COMPANY, name=name, company_number=reg,
                        country=country or "United Kingdom", depth=child_depth)
            result.nodes[node_id] = node
            if child_depth < max_depth:
                queue.append((reg, child_depth))
            else:
                node.note = "Not expanded: depth limit reached"
                result.flags.append(Flag(
                    "DEPTH_LIMIT", "INFO", "Depth limit reached",
                    f"{name} ({reg}) was not looked through. Increase the depth to keep tracing.", node_id,
                ))
        return node

    if not reg:
        node = Node(id=f"ent:{_norm(name)}:{_norm(country)}", kind=KIND_UNVERIFIED, name=name,
                    country=country, depth=child_depth, note="No usable registration number")
        result.flags.append(Flag(
            "UNIDENTIFIED_CORPORATE", "MEDIUM", "Corporate owner without a registration number",
            f"{name} has no registration number on the register, so it cannot be looked up.", node.id,
        ))
        return node

    node = Node(id=f"ent:{_norm(name)}:{_norm(country)}:{reg}", kind=KIND_OVERSEAS, name=name,
                company_number=reg, country=country, depth=child_depth,
                note="Registered outside the UK; chain stops here")
    risk = jurisdiction_risk(country, cfg)
    severity = "HIGH" if risk in ("call_for_action", "offshore_centres") else "MEDIUM"
    detail = f"{name} is registered in {country or 'an unstated country'}, so ownership behind it is not visible here."
    if risk == "call_for_action":
        detail += " The jurisdiction is on this tool's call for action list."
    elif risk == "offshore_centres":
        detail += " The jurisdiction is on this tool's offshore financial centre list."
    result.flags.append(Flag("OVERSEAS_OWNER", severity, "Overseas corporate owner", detail, node.id))
    return node


# ---------------------------------------------------------------------- flags
def _active_statements(statements: list) -> list:
    return [s for s in statements if not s.get("ceased_on")]


def _check_statements(result: OwnershipResult, node: Node, statements: list) -> None:
    for statement in _active_statements(statements):
        code = statement.get("statement", "")
        for fragment, severity, title, detail in STATEMENT_RULES:
            if fragment in code:
                result.flags.append(Flag(
                    "PSC_STATEMENT", severity, title, f"{node.name}: {detail}", node.id,
                ))
                break


def _check_company_status(result: OwnershipResult, node: Node, depth: int) -> None:
    if node.status and node.status.casefold() in INACTIVE_STATUSES:
        severity = "MEDIUM" if depth == 0 else "HIGH"
        result.flags.append(Flag(
            "COMPANY_NOT_ACTIVE", severity, "Company is not active",
            f"{node.name} has status '{node.status}'.", node.id,
        ))


def _check_recent_incorporation(result: OwnershipResult, node: Node, depth: int, today: date) -> None:
    if depth == 0:
        return
    created = _parse_date(node.incorporated)
    if created and (today - created).days < 365:
        result.flags.append(Flag(
            "RECENT_INCORPORATION", "LOW", "Recently incorporated owner",
            f"{node.name} was incorporated on {node.incorporated}, less than a year ago.", node.id,
        ))


def _flag_graph_shape(result: OwnershipResult, cfg: dict, max_depth: int) -> None:
    graph = nx.DiGraph()
    for edge in result.edges:
        if edge.active:
            graph.add_edge(edge.owner, edge.owned)

    cycles = []
    for cycle in nx.simple_cycles(graph):
        cycles.append(cycle)
        if len(cycles) >= 5:
            break
    for cycle in cycles:
        names = " -> ".join(result.nodes[n].name for n in cycle + [cycle[0]])
        result.flags.append(Flag(
            "CIRCULAR_OWNERSHIP", "HIGH", "Circular ownership",
            f"Ownership loops back on itself: {names}.", cycle[0],
        ))

    entities = [n for n in result.nodes.values()
                if n.id != result.root_id and n.kind not in (KIND_INDIVIDUAL, KIND_SUPER_SECURE)]
    if len(entities) >= 6:
        result.flags.append(Flag(
            "COMPLEX_STRUCTURE", "HIGH" if len(entities) >= 10 else "MEDIUM", "Many entities in the structure",
            f"{len(entities)} corporate or legal entities sit between the target and its owners.",
        ))

    deepest = max((n.depth for n in result.nodes.values() if n.kind == KIND_INDIVIDUAL), default=0)
    layers = max(deepest - 1, 0)
    if layers >= 3:
        result.flags.append(Flag(
            "LAYERED_STRUCTURE", "HIGH" if layers >= 5 else "MEDIUM", "Layered ownership structure",
            f"A natural person sits behind {layers} intermediate companies. "
            "Long chains make ownership harder to verify.",
        ))


def _apply_identity(node: Node, item: dict, today: date) -> None:
    """Record Companies House identity verification status, keeping the more serious one if a person appears twice."""
    assessed = assess_identity(item.get("identity_verification_details"), today)
    if node.idv_status is None or STATUS_RANK[assessed.status] > STATUS_RANK[node.idv_status]:
        node.idv_status, node.idv_rag, node.idv_label = assessed.status, assessed.rag, assessed.label


def _flag_identity(result: OwnershipResult) -> None:
    for node in result.nodes.values():
        if node.kind not in (KIND_INDIVIDUAL, KIND_SUPER_SECURE):
            continue
        who = node.name if node.kind == KIND_INDIVIDUAL else "A super secure PSC"
        if node.idv_status == "OVERDUE":
            result.flags.append(Flag(
                "IDV_OVERDUE", "HIGH", "Identity verification overdue", f"{who}: {node.idv_label}.", node.id,
            ))
        elif node.idv_status == "NOT_VERIFIED":
            result.flags.append(Flag(
                "IDV_NOT_VERIFIED", "MEDIUM", "Identity not yet verified", f"{who}: {node.idv_label}.", node.id,
            ))


def _flag_unresolved_share(result: OwnershipResult) -> None:
    total = min(sum(u.high for u in result.unresolved), 100.0)
    if total <= 0:
        return
    severity = "HIGH" if total >= 50 else "MEDIUM"
    result.flags.append(Flag(
        "UNRESOLVED_SHARE", severity, "Ownership hidden behind unresolved owners",
        f"Up to {total:.1f}% of the target sits behind owners that cannot be looked through on the public register.",
    ))


# ------------------------------------------------------------------- maths
def _compute_effective(result: OwnershipResult, max_depth: int) -> None:
    graph = nx.DiGraph()
    edge_map: dict = {}
    for edge in result.edges:
        if edge.active:
            graph.add_edge(edge.owner, edge.owned)
            edge_map[(edge.owner, edge.owned)] = edge

    root = result.root_id
    for node_id, node in result.nodes.items():
        if node_id == root or node_id not in graph:
            continue
        is_leaf = graph.in_degree(node_id) == 0
        if node.kind != KIND_INDIVIDUAL and not is_leaf:
            continue  # intermediate companies are not reported; only people and dead ends

        low_total = high_total = 0.0
        routes: list = []
        control_routes: list = []
        paths = 0
        for path in nx.all_simple_paths(graph, node_id, root, cutoff=max_depth + 1):
            paths += 1
            if paths > MAX_PATHS_PER_NODE:
                break
            low, high = 100.0, 100.0
            control_only = False
            text = result.nodes[path[0]].name
            for a, b in zip(path, path[1:]):
                edge = edge_map[(a, b)]
                band = edge.band
                text += f" -[{band_text(band)}]-> {result.nodes[b].name}"
                if band is None:
                    control_only = True
                else:
                    low *= band[0] / 100.0
                    high *= band[1] / 100.0
            if control_only:
                control_routes.append(text)
            else:
                low_total += low
                high_total += high
                routes.append(f"{text}  (about {low:.1f}-{high:.1f}%)")

        low_total, high_total = min(low_total, 100.0), min(high_total, 100.0)

        if node.kind == KIND_INDIVIDUAL:
            result.people.append(PersonResult(
                node_id=node_id, name=node.name, low=round(low_total, 2), high=round(high_total, 2),
                classification=_classify(low_total, high_total, bool(control_routes)),
                routes=routes, control_routes=control_routes, layers=max(node.depth - 1, 0),
                nationality=node.nationality, residence=node.residence, birth=node.birth,
                idv_status=node.idv_status, idv_rag=node.idv_rag, idv_label=node.idv_label,
            ))
        else:
            result.unresolved.append(UnresolvedResult(
                node_id=node_id, name=node.name, kind=node.kind, country=node.country,
                reason=node.note or "Ownership behind this entity is not visible on the register",
                low=round(low_total, 2), high=round(high_total, 2), routes=routes + control_routes,
            ))

    result.people.sort(key=lambda p: (-p.low, -p.high, p.name))
    result.unresolved.sort(key=lambda u: (-u.high, u.name))


def _classify(low: float, high: float, has_control: bool) -> str:
    if low >= UBO_THRESHOLD:
        return "LIKELY_UBO"
    if high > UBO_THRESHOLD:
        return "POSSIBLE_UBO"
    if has_control:
        return "CONTROL"
    return "BELOW_THRESHOLD"
