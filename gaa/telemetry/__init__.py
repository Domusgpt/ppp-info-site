"""
Telemetry Layer - Hash-Chained Audit Trail

Provides tamper-evident logging of geometric state via TRACE events
and Merkle tree verification.

Key Components:
- TRACEEvent: Individual audit events with hash chaining
- GeometricFingerprint: Compact geometric state digests
- MerkleAuditTree: Efficient proof generation for event batches
- PPPStateSerializer: Canonical serialization for PPP telemetry

Design based on:
- arXiv:2511.17118 "Constant-size cryptographic evidence structure"
- Clinical AI audit trails achieving 3KB proofs for 80M events
"""

from .events import TRACEEvent, EventType, EventChain
from .fingerprint import GeometricFingerprint, FingerprintType
from .merkle import MerkleAuditTree, MerkleProof
from .serializer import PPPStateSerializer, TelemetryFrame

__all__ = [
    "TRACEEvent",
    "EventType",
    "EventChain",
    "GeometricFingerprint",
    "FingerprintType",
    "MerkleAuditTree",
    "MerkleProof",
    "PPPStateSerializer",
    "TelemetryFrame",
]
