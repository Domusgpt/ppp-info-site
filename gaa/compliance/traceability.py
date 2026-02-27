"""
Traceability Matrix

Implements ISO 26262 bidirectional traceability from
requirements through implementation.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum
from datetime import datetime


class RequirementType(Enum):
    """Types of requirements."""

    SAFETY = "safety"
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    GEOMETRIC = "geometric"
    INTERFACE = "interface"


class RequirementStatus(Enum):
    """Status of requirement implementation."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    VALIDATED = "validated"


@dataclass
class Requirement:
    """
    System requirement with traceability info.
    """

    requirement_id: str
    title: str
    description: str = ""
    requirement_type: RequirementType = RequirementType.FUNCTIONAL
    status: RequirementStatus = RequirementStatus.PROPOSED

    # Hierarchy
    parent_id: str = ""
    child_ids: List[str] = field(default_factory=list)

    # Links
    implementation_ids: List[str] = field(default_factory=list)
    test_ids: List[str] = field(default_factory=list)
    safety_claim_ids: List[str] = field(default_factory=list)

    # Geometric specifics
    geometric_constraint_id: str = ""
    ispec_id: str = ""

    # Metadata
    author: str = ""
    created: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "title": self.title,
            "description": self.description,
            "type": self.requirement_type.value,
            "status": self.status.value,
            "hierarchy": {
                "parent": self.parent_id,
                "children": self.child_ids,
            },
            "links": {
                "implementations": self.implementation_ids,
                "tests": self.test_ids,
                "safety_claims": self.safety_claim_ids,
            },
            "geometric": {
                "constraint_id": self.geometric_constraint_id,
                "ispec_id": self.ispec_id,
            },
            "metadata": {
                "author": self.author,
                "created": self.created,
                "version": self.version,
            },
        }


@dataclass
class Implementation:
    """
    Implementation artifact linked to requirements.
    """

    implementation_id: str
    title: str
    description: str = ""

    # Source location
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    function_name: str = ""

    # Links
    requirement_ids: List[str] = field(default_factory=list)
    test_ids: List[str] = field(default_factory=list)

    # Verification
    verified: bool = False
    verification_method: str = ""
    verification_date: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "implementation_id": self.implementation_id,
            "title": self.title,
            "description": self.description,
            "source": {
                "file": self.file_path,
                "lines": [self.line_start, self.line_end],
                "function": self.function_name,
            },
            "links": {
                "requirements": self.requirement_ids,
                "tests": self.test_ids,
            },
            "verification": {
                "verified": self.verified,
                "method": self.verification_method,
                "date": self.verification_date,
            },
        }


class TraceabilityMatrix:
    """
    Bidirectional traceability matrix.

    Links requirements to implementations and tests.
    Supports coverage analysis and gap detection.
    """

    def __init__(self, project_id: str = ""):
        self.project_id = project_id
        self.requirements: Dict[str, Requirement] = {}
        self.implementations: Dict[str, Implementation] = {}
        self.tests: Dict[str, Dict[str, Any]] = {}

    def add_requirement(self, req: Requirement) -> None:
        """Add a requirement."""
        self.requirements[req.requirement_id] = req

    def add_implementation(self, impl: Implementation) -> None:
        """Add an implementation."""
        self.implementations[impl.implementation_id] = impl

        # Update bidirectional links
        for req_id in impl.requirement_ids:
            if req_id in self.requirements:
                if impl.implementation_id not in self.requirements[req_id].implementation_ids:
                    self.requirements[req_id].implementation_ids.append(impl.implementation_id)

    def add_test(
        self,
        test_id: str,
        title: str,
        requirement_ids: List[str],
        passed: bool = False
    ) -> None:
        """Add a test."""
        self.tests[test_id] = {
            "test_id": test_id,
            "title": title,
            "requirement_ids": requirement_ids,
            "passed": passed,
        }

        # Update requirement links
        for req_id in requirement_ids:
            if req_id in self.requirements:
                if test_id not in self.requirements[req_id].test_ids:
                    self.requirements[req_id].test_ids.append(test_id)

    def link_requirement_to_implementation(
        self,
        req_id: str,
        impl_id: str
    ) -> bool:
        """Create link between requirement and implementation."""
        if req_id not in self.requirements or impl_id not in self.implementations:
            return False

        if impl_id not in self.requirements[req_id].implementation_ids:
            self.requirements[req_id].implementation_ids.append(impl_id)

        if req_id not in self.implementations[impl_id].requirement_ids:
            self.implementations[impl_id].requirement_ids.append(req_id)

        return True

    def get_unimplemented_requirements(self) -> List[str]:
        """Get requirements without implementations."""
        return [
            req_id for req_id, req in self.requirements.items()
            if not req.implementation_ids
        ]

    def get_untested_requirements(self) -> List[str]:
        """Get requirements without tests."""
        return [
            req_id for req_id, req in self.requirements.items()
            if not req.test_ids
        ]

    def get_orphan_implementations(self) -> List[str]:
        """Get implementations not linked to requirements."""
        return [
            impl_id for impl_id, impl in self.implementations.items()
            if not impl.requirement_ids
        ]

    def compute_coverage(self) -> Dict[str, float]:
        """Compute various coverage metrics."""
        total_reqs = len(self.requirements)
        if total_reqs == 0:
            return {
                "implementation_coverage": 0.0,
                "test_coverage": 0.0,
                "verification_coverage": 0.0,
            }

        implemented = sum(1 for r in self.requirements.values() if r.implementation_ids)
        tested = sum(1 for r in self.requirements.values() if r.test_ids)
        verified = sum(
            1 for r in self.requirements.values()
            if r.status in (RequirementStatus.VERIFIED, RequirementStatus.VALIDATED)
        )

        return {
            "implementation_coverage": implemented / total_reqs,
            "test_coverage": tested / total_reqs,
            "verification_coverage": verified / total_reqs,
        }

    def trace_forward(self, req_id: str) -> Dict[str, List[str]]:
        """Trace forward from requirement to implementations and tests."""
        if req_id not in self.requirements:
            return {"implementations": [], "tests": []}

        req = self.requirements[req_id]
        return {
            "implementations": req.implementation_ids,
            "tests": req.test_ids,
        }

    def trace_backward(self, impl_id: str) -> List[str]:
        """Trace backward from implementation to requirements."""
        if impl_id not in self.implementations:
            return []
        return self.implementations[impl_id].requirement_ids

    def create_geometric_requirements(self) -> None:
        """Create standard geometric navigation requirements."""

        self.add_requirement(Requirement(
            requirement_id="REQ-GEO-001",
            title="Spinor Coherence Maintenance",
            description="System shall maintain spinor coherence >= 0.7 under all operational conditions",
            requirement_type=RequirementType.GEOMETRIC,
            status=RequirementStatus.APPROVED,
        ))

        self.add_requirement(Requirement(
            requirement_id="REQ-GEO-002",
            title="Isoclinic Constraint Enforcement",
            description="System shall enforce isoclinic defect < 0.3 radians",
            requirement_type=RequirementType.GEOMETRIC,
            status=RequirementStatus.APPROVED,
        ))

        self.add_requirement(Requirement(
            requirement_id="REQ-GEO-003",
            title="Drift Detection and Correction",
            description="System shall detect reasoning drift within 100ms and apply correction",
            requirement_type=RequirementType.SAFETY,
            status=RequirementStatus.APPROVED,
        ))

        self.add_requirement(Requirement(
            requirement_id="REQ-GEO-004",
            title="Audit Trail Completeness",
            description="System shall maintain complete hash-chained audit trail of all geometric state changes",
            requirement_type=RequirementType.SAFETY,
            status=RequirementStatus.APPROVED,
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "requirements": {rid: r.to_dict() for rid, r in self.requirements.items()},
            "implementations": {iid: i.to_dict() for iid, i in self.implementations.items()},
            "tests": self.tests,
            "coverage": self.compute_coverage(),
            "gaps": {
                "unimplemented": self.get_unimplemented_requirements(),
                "untested": self.get_untested_requirements(),
                "orphan_implementations": self.get_orphan_implementations(),
            },
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)
