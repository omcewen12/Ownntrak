"""Plain data containers shared across the package."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Band = tuple  # (low, high) expressed as percentages, e.g. (25.0, 50.0)

# Severity levels, most serious first.
SEVERITIES = ("HIGH", "MEDIUM", "LOW", "INFO")
SEVERITY_RANK = {name: rank for rank, name in enumerate(SEVERITIES)}

# Node kinds
KIND_COMPANY = "company"                # UK company looked up at Companies House
KIND_INDIVIDUAL = "individual"          # natural person PSC
KIND_OVERSEAS = "overseas_entity"       # corporate PSC registered outside the UK
KIND_UNVERIFIED = "unverified_entity"   # corporate PSC with no usable registration number
KIND_LEGAL_PERSON = "legal_person"      # e.g. a public body
KIND_SUPER_SECURE = "super_secure"      # identity protected by law
KIND_NOT_FOUND = "not_found"            # UK registration number that did not resolve


@dataclass
class Node:
    id: str
    kind: str
    name: str
    company_number: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None
    incorporated: Optional[str] = None
    depth: int = 0
    note: Optional[str] = None
    nationality: Optional[str] = None
    residence: Optional[str] = None
    birth: Optional[str] = None  # "YYYY-MM" exactly as published, never a full date
    idv_status: Optional[str] = None   # VERIFIED | NOT_VERIFIED | OVERDUE (individual and super secure PSCs)
    idv_rag: Optional[str] = None
    idv_label: Optional[str] = None
    filings: dict = field(default_factory=dict)  # accounts, confirmation statement and status checks


@dataclass
class Edge:
    """An ownership or control link running from owner to owned company."""

    owner: str
    owned: str
    natures: list = field(default_factory=list)
    shares: Optional[tuple] = None
    voting: Optional[tuple] = None
    control_rights: list = field(default_factory=list)
    as_trust: bool = False
    as_firm: bool = False
    notified_on: Optional[str] = None
    ceased_on: Optional[str] = None

    @property
    def active(self) -> bool:
        return not self.ceased_on

    @property
    def band(self) -> Optional[tuple]:
        """The percentage band used for ownership maths (shares first, then voting)."""
        return self.shares or self.voting

    @property
    def basis(self) -> str:
        if self.shares:
            return "shares"
        if self.voting:
            return "voting rights"
        return "control"


@dataclass
class Flag:
    code: str
    severity: str
    title: str
    detail: str
    node_id: Optional[str] = None
    dimension: str = ""  # structure | transparency | identity | filings, set when RAG is applied


@dataclass
class PersonResult:
    """A natural person and their estimated ownership of the target company."""

    node_id: str
    name: str
    low: float
    high: float
    classification: str  # LIKELY_UBO | POSSIBLE_UBO | CONTROL | BELOW_THRESHOLD
    routes: list = field(default_factory=list)
    control_routes: list = field(default_factory=list)
    layers: int = 0
    nationality: Optional[str] = None
    residence: Optional[str] = None
    birth: Optional[str] = None
    idv_status: Optional[str] = None
    idv_rag: Optional[str] = None
    idv_label: Optional[str] = None


@dataclass
class UnresolvedResult:
    """An owner that the public register cannot look through."""

    node_id: str
    name: str
    kind: str
    country: Optional[str]
    reason: str
    low: float
    high: float
    routes: list = field(default_factory=list)


@dataclass
class OwnershipResult:
    root_id: str
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    people: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    params: dict = field(default_factory=dict)
    generated_at: str = ""
    source: str = ""
    rag: dict = field(default_factory=dict)       # dimension key -> {label, rag, reasons}
    overall_rag: str = ""
    overall_reasons: list = field(default_factory=list)

    @property
    def root(self) -> Node:
        return self.nodes[self.root_id]

    def flags_by_severity(self, severity: str) -> list:
        return [f for f in self.flags if f.severity == severity]
