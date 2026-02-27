"""
Safety Case Implementation

Implements UL 4600 Claim-Argument-Evidence structure
for documenting geometric navigation safety.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class ClaimStatus(Enum):
    """Status of safety claim verification."""

    UNVERIFIED = "unverified"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"
    PARTIAL = "partial"


class EvidenceType(Enum):
    """Types of supporting evidence."""

    SIMULATION = "simulation"
    TESTING = "testing"
    ANALYSIS = "analysis"
    INSPECTION = "inspection"
    FIELD_DATA = "field_data"
    FORMAL_PROOF = "formal_proof"


@dataclass
class Evidence:
    """
    Evidence supporting a safety argument.

    Based on UL 4600 evidence requirements.
    """

    evidence_id: str
    evidence_type: EvidenceType
    title: str
    description: str = ""

    # Source information
    source_document: str = ""
    source_section: str = ""
    date_collected: float = field(default_factory=lambda: datetime.utcnow().timestamp())

    # Geometric specifics
    geometric_fingerprint: str = ""
    telemetry_range: tuple = (0.0, 0.0)

    # Verification
    verified: bool = False
    verifier: str = ""
    verification_date: float = 0.0

    # Metrics
    sample_size: int = 0
    pass_rate: float = 0.0
    confidence_level: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "type": self.evidence_type.value,
            "title": self.title,
            "description": self.description,
            "source": {
                "document": self.source_document,
                "section": self.source_section,
            },
            "date_collected": self.date_collected,
            "geometric_fingerprint": self.geometric_fingerprint,
            "verified": self.verified,
            "metrics": {
                "sample_size": self.sample_size,
                "pass_rate": self.pass_rate,
                "confidence": self.confidence_level,
            },
        }


@dataclass
class Argument:
    """
    Argument linking claims to evidence.

    Describes how evidence supports a claim.
    """

    argument_id: str
    description: str

    # Links
    supported_claims: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    sub_arguments: List[str] = field(default_factory=list)

    # Argument structure
    argument_type: str = "direct"  # direct, decomposition, assumption
    assumption: str = ""

    # Status
    complete: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "argument_id": self.argument_id,
            "description": self.description,
            "supported_claims": self.supported_claims,
            "evidence_refs": self.evidence_refs,
            "sub_arguments": self.sub_arguments,
            "type": self.argument_type,
            "assumption": self.assumption,
            "complete": self.complete,
        }


@dataclass
class Claim:
    """
    Safety claim in the safety case.

    Top-level claims are the safety goals.
    Sub-claims decompose the argument.
    """

    claim_id: str
    statement: str
    description: str = ""

    # Claim level
    level: int = 0  # 0 = top-level, 1+ = sub-claim

    # Links
    parent_claim: str = ""
    sub_claims: List[str] = field(default_factory=list)
    arguments: List[str] = field(default_factory=list)

    # Status
    status: ClaimStatus = ClaimStatus.UNVERIFIED

    # Geometric specifics
    geometric_constraint: str = ""  # Reference to ISpec constraint

    # Metrics
    target_metric: str = ""
    target_value: float = 0.0
    actual_value: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "description": self.description,
            "level": self.level,
            "parent_claim": self.parent_claim,
            "sub_claims": self.sub_claims,
            "arguments": self.arguments,
            "status": self.status.value,
            "geometric_constraint": self.geometric_constraint,
            "metrics": {
                "target": self.target_metric,
                "target_value": self.target_value,
                "actual_value": self.actual_value,
            },
        }


class SafetyCase:
    """
    Complete safety case following UL 4600 structure.

    Organizes claims, arguments, and evidence into
    a coherent safety argument.
    """

    def __init__(
        self,
        case_id: str,
        title: str,
        description: str = ""
    ):
        self.case_id = case_id
        self.title = title
        self.description = description
        self.created = datetime.utcnow().timestamp()
        self.version = "1.0.0"

        self.claims: Dict[str, Claim] = {}
        self.arguments: Dict[str, Argument] = {}
        self.evidence: Dict[str, Evidence] = {}

        self.top_level_claims: List[str] = []

    def add_claim(self, claim: Claim) -> None:
        """Add a claim to the safety case."""
        self.claims[claim.claim_id] = claim
        if claim.level == 0:
            self.top_level_claims.append(claim.claim_id)

    def add_argument(self, argument: Argument) -> None:
        """Add an argument."""
        self.arguments[argument.argument_id] = argument

    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence."""
        self.evidence[evidence.evidence_id] = evidence

    def link_claim_to_argument(self, claim_id: str, argument_id: str) -> None:
        """Link a claim to an argument."""
        if claim_id in self.claims:
            if argument_id not in self.claims[claim_id].arguments:
                self.claims[claim_id].arguments.append(argument_id)
        if argument_id in self.arguments:
            if claim_id not in self.arguments[argument_id].supported_claims:
                self.arguments[argument_id].supported_claims.append(claim_id)

    def link_argument_to_evidence(self, argument_id: str, evidence_id: str) -> None:
        """Link an argument to evidence."""
        if argument_id in self.arguments:
            if evidence_id not in self.arguments[argument_id].evidence_refs:
                self.arguments[argument_id].evidence_refs.append(evidence_id)

    def get_claim_status(self) -> Dict[str, ClaimStatus]:
        """Get verification status of all claims."""
        return {cid: c.status for cid, c in self.claims.items()}

    def get_unverified_claims(self) -> List[str]:
        """Get IDs of unverified claims."""
        return [
            cid for cid, c in self.claims.items()
            if c.status in (ClaimStatus.UNVERIFIED, ClaimStatus.IN_PROGRESS)
        ]

    def compute_coverage(self) -> float:
        """Compute fraction of claims with evidence."""
        if not self.claims:
            return 0.0

        covered = 0
        for claim in self.claims.values():
            has_evidence = False
            for arg_id in claim.arguments:
                arg = self.arguments.get(arg_id)
                if arg and arg.evidence_refs:
                    has_evidence = True
                    break
            if has_evidence:
                covered += 1

        return covered / len(self.claims)

    def create_geometric_safety_claims(self) -> None:
        """Create standard geometric navigation safety claims."""

        # Top-level claim
        self.add_claim(Claim(
            claim_id="GEO-001",
            statement="Geometric navigation system operates safely",
            description="The PPP-based navigation maintains safe operational envelope",
            level=0,
            target_metric="overall_safety",
        ))

        # Sub-claims
        self.add_claim(Claim(
            claim_id="GEO-001-1",
            statement="Spinor coherence remains above safety threshold",
            description="The system maintains coherence >= 0.7 under all conditions",
            level=1,
            parent_claim="GEO-001",
            target_metric="spinor_coherence",
            target_value=0.7,
        ))
        self.claims["GEO-001"].sub_claims.append("GEO-001-1")

        self.add_claim(Claim(
            claim_id="GEO-001-2",
            statement="Isoclinic rotation constraints are preserved",
            description="Left and right isoclinic angles remain within bounds",
            level=1,
            parent_claim="GEO-001",
            target_metric="isoclinic_defect",
            target_value=0.3,
        ))
        self.claims["GEO-001"].sub_claims.append("GEO-001-2")

        self.add_claim(Claim(
            claim_id="GEO-001-3",
            statement="Error correction system detects and repairs drift",
            description="HDC cleanup memory corrects reasoning drift",
            level=1,
            parent_claim="GEO-001",
            target_metric="correction_rate",
            target_value=0.95,
        ))
        self.claims["GEO-001"].sub_claims.append("GEO-001-3")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "case_id": self.case_id,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "created": self.created,
            "claims": {cid: c.to_dict() for cid, c in self.claims.items()},
            "arguments": {aid: a.to_dict() for aid, a in self.arguments.items()},
            "evidence": {eid: e.to_dict() for eid, e in self.evidence.items()},
            "top_level_claims": self.top_level_claims,
            "coverage": self.compute_coverage(),
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)
