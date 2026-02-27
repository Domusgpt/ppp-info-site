"""
Cleanup Memory for Geometric Error Correction

Projects noisy/corrupted reasoning states back onto the manifold
of valid states. Implements the HDC cleanup pattern where noisy
representations are snapped to the nearest valid prototype.

Correction Events:
- Each correction generates an auditable TRACE event
- Before/after fingerprints enable forensic analysis
- Correction magnitude quantifies drift severity
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from .hypervector import Hypervector, HypervectorStore


@dataclass
class CorrectionResult:
    """Result of a cleanup/correction operation."""

    corrected: bool
    original_fingerprint: str
    corrected_fingerprint: str
    nearest_valid_state: str
    similarity_before: float
    similarity_after: float
    correction_magnitude: float
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())

    @property
    def was_significant(self) -> bool:
        """Check if correction was significant (not just noise)."""
        return self.correction_magnitude > 0.05

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "corrected": self.corrected,
            "original_fingerprint": self.original_fingerprint,
            "corrected_fingerprint": self.corrected_fingerprint,
            "nearest_valid_state": self.nearest_valid_state,
            "similarity_before": self.similarity_before,
            "similarity_after": self.similarity_after,
            "correction_magnitude": self.correction_magnitude,
            "timestamp": self.timestamp,
        }


class CleanupMemory:
    """
    Grounded concept store for cleanup/correction.

    Maintains a set of valid reasoning states as hypervectors.
    Noisy states are projected to the nearest valid state via
    nearest-neighbor lookup.

    Usage:
    1. Register valid states during training/calibration
    2. Query with potentially noisy states
    3. Receive corrected state and correction magnitude
    """

    def __init__(
        self,
        dimension: int = 10000,
        similarity_threshold: float = 0.7,
        auto_register: bool = False
    ):
        """
        Initialize cleanup memory.

        Args:
            dimension: Hypervector dimension
            similarity_threshold: Minimum similarity to consider valid
            auto_register: If True, register novel states automatically
        """
        self.dimension = dimension
        self.similarity_threshold = similarity_threshold
        self.auto_register = auto_register

        self.store = HypervectorStore(dimension)
        self.state_metadata: Dict[str, Dict[str, Any]] = {}
        self._correction_count = 0

    def register_valid_state(
        self,
        state_id: str,
        hypervector: Hypervector,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a valid reasoning state.

        Args:
            state_id: Unique identifier for state
            hypervector: Hypervector encoding of state
            metadata: Optional metadata about the state
        """
        self.store.add(state_id, hypervector)
        self.state_metadata[state_id] = metadata or {}

    def register_from_quaternion(
        self,
        state_id: str,
        quaternion: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register valid state from quaternion."""
        hv = Hypervector.from_quaternion(quaternion, self.dimension)
        self.register_valid_state(state_id, hv, metadata)

    def register_from_fingerprint(
        self,
        state_id: str,
        fingerprint: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register valid state from geometric fingerprint."""
        hv = Hypervector.from_geometric_state(fingerprint, self.dimension)
        self.register_valid_state(state_id, hv, metadata)

    def cleanup(
        self,
        noisy_state: Hypervector,
        state_fingerprint: str = ""
    ) -> CorrectionResult:
        """
        Clean up a potentially noisy state.

        Projects to nearest valid state if similarity is above threshold.

        Args:
            noisy_state: Potentially corrupted hypervector
            state_fingerprint: Original state fingerprint for audit

        Returns:
            CorrectionResult with correction details
        """
        # Find nearest valid state
        neighbors = self.store.nearest_neighbor(noisy_state, top_k=1)

        if not neighbors:
            # No valid states registered
            return CorrectionResult(
                corrected=False,
                original_fingerprint=state_fingerprint,
                corrected_fingerprint=state_fingerprint,
                nearest_valid_state="",
                similarity_before=0.0,
                similarity_after=0.0,
                correction_magnitude=0.0,
            )

        nearest_name, similarity = neighbors[0]
        nearest_vector = self.store.get(nearest_name)

        # Compute correction magnitude
        # (how far we had to move to reach valid state)
        correction_magnitude = 1.0 - similarity

        # Determine if correction should be applied
        if similarity >= self.similarity_threshold:
            # State is close enough to valid - apply correction
            corrected_fingerprint = nearest_vector.fingerprint().hex()
            self._correction_count += 1

            return CorrectionResult(
                corrected=True,
                original_fingerprint=state_fingerprint,
                corrected_fingerprint=corrected_fingerprint,
                nearest_valid_state=nearest_name,
                similarity_before=similarity,
                similarity_after=1.0,  # Now exactly on valid state
                correction_magnitude=correction_magnitude,
            )
        else:
            # Too far from any valid state
            if self.auto_register:
                # Register as new valid state
                new_id = f"auto_{len(self.store)}"
                self.register_valid_state(new_id, noisy_state)

            return CorrectionResult(
                corrected=False,
                original_fingerprint=state_fingerprint,
                corrected_fingerprint=state_fingerprint,
                nearest_valid_state=nearest_name,
                similarity_before=similarity,
                similarity_after=similarity,
                correction_magnitude=correction_magnitude,
            )

    def cleanup_quaternion(
        self,
        quaternion: np.ndarray,
        state_fingerprint: str = ""
    ) -> CorrectionResult:
        """Clean up from quaternion representation."""
        hv = Hypervector.from_quaternion(quaternion, self.dimension)
        return self.cleanup(hv, state_fingerprint)

    def get_correction_rate(self) -> float:
        """Fraction of queries that required correction."""
        total_states = len(self.store)
        if total_states == 0:
            return 0.0
        return self._correction_count / total_states

    def get_valid_state_metadata(self, state_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a valid state."""
        return self.state_metadata.get(state_id)

    @property
    def valid_state_count(self) -> int:
        """Number of registered valid states."""
        return len(self.store)


class HierarchicalCleanupMemory:
    """
    Multi-level cleanup memory for hierarchical reasoning.

    Supports coarse-to-fine correction:
    1. First match at abstract/category level
    2. Then refine within category
    """

    def __init__(
        self,
        dimension: int = 10000,
        levels: int = 2
    ):
        self.dimension = dimension
        self.levels = levels

        # Create memory for each level
        self.memories = [
            CleanupMemory(dimension, similarity_threshold=0.5 + 0.2 * i)
            for i in range(levels)
        ]

    def register_hierarchical(
        self,
        state_id: str,
        hypervector: Hypervector,
        level: int,
        parent_id: Optional[str] = None
    ) -> None:
        """Register state at specific hierarchy level."""
        if level >= self.levels:
            raise ValueError(f"Level {level} exceeds max {self.levels}")

        self.memories[level].register_valid_state(
            state_id,
            hypervector,
            metadata={"parent": parent_id}
        )

    def hierarchical_cleanup(
        self,
        noisy_state: Hypervector
    ) -> List[CorrectionResult]:
        """
        Perform hierarchical cleanup from coarse to fine.

        Returns correction results at each level.
        """
        results = []
        current_state = noisy_state

        for level, memory in enumerate(self.memories):
            result = memory.cleanup(current_state)
            results.append(result)

            if result.corrected:
                # Use corrected state for next level
                corrected = memory.store.get(result.nearest_valid_state)
                if corrected:
                    current_state = corrected

        return results
