"""
Geometric Fingerprinting

Compact cryptographic digests of geometric state for audit trails.
Supports multiple fingerprint types for different verification needs.

Fingerprint Types:
- CONSTELLATION: Hash of sorted vertex coordinates (rotation-invariant)
- TOPOLOGICAL: Persistence diagram encoding
- QUATERNION: Pedersen-style commitment to spinor state
- HYBRID: Combined fingerprint for comprehensive verification
"""

import hashlib
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional
import struct


class FingerprintType(Enum):
    """Types of geometric fingerprints."""

    CONSTELLATION = "constellation"
    TOPOLOGICAL = "topological"
    QUATERNION = "quaternion"
    HYBRID = "hybrid"


@dataclass
class GeometricFingerprint:
    """
    Cryptographic fingerprint of geometric state.

    Provides tamper-evident digest of polytope configuration,
    topological structure, or spinor state.
    """

    fingerprint_type: FingerprintType
    digest: bytes
    metadata: dict

    @classmethod
    def from_constellation(
        cls,
        vertices: np.ndarray,
        rotation_invariant: bool = True
    ) -> 'GeometricFingerprint':
        """
        Create fingerprint from polytope vertex constellation.

        Args:
            vertices: Nx4 array of 4D vertex coordinates
            rotation_invariant: If True, sort by distance from centroid
        """
        vertices = np.asarray(vertices, dtype=np.float64)

        if rotation_invariant and len(vertices) > 0:
            # Compute centroid
            centroid = vertices.mean(axis=0)

            # Compute distances from centroid
            distances = np.linalg.norm(vertices - centroid, axis=1)

            # Sort vertices by distance (rotation-invariant ordering)
            sorted_indices = np.argsort(distances)
            sorted_vertices = vertices[sorted_indices]

            # Round for determinism
            canonical = np.round(sorted_vertices, decimals=10)
        else:
            canonical = np.round(vertices, decimals=10)

        # Hash the canonical representation
        data = canonical.tobytes()
        digest = hashlib.sha256(data).digest()

        return cls(
            fingerprint_type=FingerprintType.CONSTELLATION,
            digest=digest,
            metadata={
                "vertex_count": len(vertices),
                "rotation_invariant": rotation_invariant,
            }
        )

    @classmethod
    def from_persistence_diagram(
        cls,
        birth_death_pairs: List[Tuple[float, float]],
        dimension: int = 1
    ) -> 'GeometricFingerprint':
        """
        Create fingerprint from persistence diagram.

        The persistence diagram captures topological features
        (holes, voids) independent of coordinate system.

        Args:
            birth_death_pairs: List of (birth, death) times
            dimension: Homology dimension (0=components, 1=loops, 2=voids)
        """
        # Sort pairs for canonical ordering
        sorted_pairs = sorted(birth_death_pairs, key=lambda x: (x[0], x[1]))

        # Encode as bytes
        data = struct.pack('i', dimension)
        for birth, death in sorted_pairs:
            # Round for determinism
            b = round(birth, 10)
            d = round(death, 10)
            data += struct.pack('dd', b, d)

        digest = hashlib.sha256(data).digest()

        return cls(
            fingerprint_type=FingerprintType.TOPOLOGICAL,
            digest=digest,
            metadata={
                "dimension": dimension,
                "feature_count": len(sorted_pairs),
                "total_persistence": sum(d - b for b, d in sorted_pairs),
            }
        )

    @classmethod
    def from_quaternion(
        cls,
        quaternion: np.ndarray,
        blinding_factor: Optional[bytes] = None
    ) -> 'GeometricFingerprint':
        """
        Create fingerprint from quaternion state.

        Uses Pedersen-style commitment for optional zero-knowledge property.

        Args:
            quaternion: 4-element quaternion [w, x, y, z]
            blinding_factor: Optional random bytes for hiding commitment
        """
        quaternion = np.asarray(quaternion, dtype=np.float64)

        # Canonical form: ensure w >= 0 (hemisphere normalization)
        if quaternion[0] < 0:
            quaternion = -quaternion

        # Round for determinism
        canonical = np.round(quaternion, decimals=10)

        # Build commitment
        data = canonical.tobytes()
        if blinding_factor:
            data += blinding_factor

        digest = hashlib.sha256(data).digest()

        return cls(
            fingerprint_type=FingerprintType.QUATERNION,
            digest=digest,
            metadata={
                "blinded": blinding_factor is not None,
                "norm": float(np.linalg.norm(quaternion)),
            }
        )

    @classmethod
    def from_hybrid(
        cls,
        constellation_fp: 'GeometricFingerprint',
        topological_fp: 'GeometricFingerprint',
        quaternion_fp: 'GeometricFingerprint'
    ) -> 'GeometricFingerprint':
        """
        Create hybrid fingerprint combining multiple types.

        Provides comprehensive verification covering geometry,
        topology, and orientation.
        """
        # Combine digests
        combined = (
            constellation_fp.digest +
            topological_fp.digest +
            quaternion_fp.digest
        )
        digest = hashlib.sha256(combined).digest()

        return cls(
            fingerprint_type=FingerprintType.HYBRID,
            digest=digest,
            metadata={
                "components": {
                    "constellation": constellation_fp.hex(),
                    "topological": topological_fp.hex(),
                    "quaternion": quaternion_fp.hex(),
                }
            }
        )

    def hex(self) -> str:
        """Return fingerprint as hex string."""
        return self.digest.hex()

    def short_hex(self, length: int = 16) -> str:
        """Return truncated hex string for display."""
        return self.digest.hex()[:length]

    def verify(self, other: 'GeometricFingerprint') -> bool:
        """Verify fingerprint matches another."""
        return (
            self.fingerprint_type == other.fingerprint_type and
            self.digest == other.digest
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GeometricFingerprint):
            return False
        return self.verify(other)

    def __hash__(self) -> int:
        return hash(self.digest)

    def __repr__(self) -> str:
        return f"GeometricFingerprint({self.fingerprint_type.value}, {self.short_hex()})"


def compute_constellation_hash(
    vertices: np.ndarray,
    rotation_invariant: bool = True
) -> str:
    """
    Convenience function to compute constellation hash as hex string.

    Args:
        vertices: Nx4 array of vertex coordinates
        rotation_invariant: Sort by centroid distance for rotation invariance
    """
    fp = GeometricFingerprint.from_constellation(vertices, rotation_invariant)
    return fp.hex()


def compute_quaternion_hash(quaternion: np.ndarray) -> str:
    """
    Convenience function to compute quaternion hash as hex string.

    Args:
        quaternion: 4-element quaternion [w, x, y, z]
    """
    fp = GeometricFingerprint.from_quaternion(quaternion)
    return fp.hex()


def compute_betti_signature(
    betti_0: int,
    betti_1: int,
    betti_2: int
) -> str:
    """
    Compute compact signature from Betti numbers.

    Args:
        betti_0: Number of connected components
        betti_1: Number of 1-cycles (loops)
        betti_2: Number of 2-cycles (voids)
    """
    data = struct.pack('iii', betti_0, betti_1, betti_2)
    return hashlib.sha256(data).hexdigest()[:16]
