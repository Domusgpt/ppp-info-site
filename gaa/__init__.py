"""
Geometric Audit Architecture (GAA)

Integrates CRA/TRACE hash-chained telemetry with Polytopal Projection
Processing (PPP) for auditable geometric cognition.

The GAA enables:
1. Geometric evidence artifacts for AI audit trails
2. Hyperdimensional error correction for reasoning drift
3. Coordinate-free multi-agent coordination via topological invariants

Architecture Layers:
- foundational: Quaternion/Clifford algebra, E(3) equivariance
- telemetry: PPP state serialization, Merkle tree proofs
- correction: HDC cleanup memory, resonator networks
- governance: ISpec constraints, audit agents
- coordination: Manifold consensus, topology verification
- compliance: UL 4600, ISO 26262, EDR patterns

Copyright (c) 2025-2026 Paul Phillips - Clear Seas Solutions LLC
"""

__version__ = "0.1.0"
__author__ = "Paul Phillips"

from .foundational import (
    Quaternion,
    DualQuaternion,
    CliffordAlgebra,
    GeometricState,
)

from .telemetry import (
    TRACEEvent,
    GeometricFingerprint,
    MerkleAuditTree,
    PPPStateSerializer,
)

from .correction import (
    HypervectorStore,
    CleanupMemory,
    ResonatorNetwork,
    DriftDetector,
)

from .governance import (
    ISpec,
    GeometricConstraint,
    AuditAgent,
    PolicyResolver,
)

from .coordination import (
    ManifoldConsensus,
    TopologyVerifier,
    HopfCoordinator,
    SwarmAnalyzer,
)

from .compliance import (
    SafetyCase,
    EDRCapture,
    TraceabilityMatrix,
    ComplianceReport,
)

__all__ = [
    # Foundational
    "Quaternion",
    "DualQuaternion",
    "CliffordAlgebra",
    "GeometricState",
    # Telemetry
    "TRACEEvent",
    "GeometricFingerprint",
    "MerkleAuditTree",
    "PPPStateSerializer",
    # Correction
    "HypervectorStore",
    "CleanupMemory",
    "ResonatorNetwork",
    "DriftDetector",
    # Governance
    "ISpec",
    "GeometricConstraint",
    "AuditAgent",
    "PolicyResolver",
    # Coordination
    "ManifoldConsensus",
    "TopologyVerifier",
    "HopfCoordinator",
    "SwarmAnalyzer",
    # Compliance
    "SafetyCase",
    "EDRCapture",
    "TraceabilityMatrix",
    "ComplianceReport",
]
