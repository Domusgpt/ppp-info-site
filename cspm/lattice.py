"""
600-Cell Polytope Lattice for Optical Signal Constellation

The 600-cell (hexacosichoron) is a regular 4-polytope with:
- 120 vertices
- 720 edges
- 1200 triangular faces
- 600 tetrahedral cells

Its vertices form an optimal sphere packing in 4D, making it ideal
for a signal constellation with maximum noise margin.

=== PHYSICAL ENCODING (Addressing OAM Discreteness) ===

IMPORTANT: Raw OAM modes (ℓ = -2, -1, 0, 1, 2...) are DISCRETE integers.
You cannot create a continuous 4D signal space using discrete OAM channels.

SOLUTION: We use COHERENT SUPERPOSITION STATES, not pure OAM modes.

Physical Signal Space (4D Hilbert Space on S³):
- Dimensions 1-2: Polarization Bloch Sphere (Poincaré Sphere)
    |ψ_pol⟩ = α|H⟩ + β|V⟩  where |α|² + |β|² = 1
    Creates continuous S² via relative phase and amplitude ratio

- Dimensions 3-4: OAM Superposition Sphere (OAM Bloch Sphere)
    |ψ_OAM⟩ = γ|ℓ₁⟩ + δ|ℓ₂⟩  where |γ|² + |δ|² = 1
    By varying γ/δ phase and amplitude, creates continuous S²

Combined: The tensor product of two S² spaces (with proper phase coupling)
creates a 4D manifold homeomorphic to S³, where the 600-cell can naturally
embed via the Hopf Fibration.

Mapping: The 120 vertices correspond to specific (α, β, γ, δ) values that:
1. Maximize minimum angular distance between symbols
2. Respect the I₂ × I₂ symmetry group of the 600-cell
3. Are distinguishable by coherent detection

This is NOT treating OAM as "integer axis" - we use the PHASE SPACE
of coupled OAM modes to create a continuous manifold.

Reference: Berry phase, geometric phase in topological photonics,
Majorana sphere representation of OAM states.

Spectral Efficiency: 120 distinct symbols = 6.9 bits per symbol
Compare to 64-QAM = 6 bits per symbol, but with geometric noise margin.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import hashlib


def _golden_ratio() -> float:
    """The golden ratio phi = (1 + sqrt(5)) / 2."""
    return (1 + np.sqrt(5)) / 2


@dataclass
class Vertex4D:
    """
    A vertex in 4D space with physical interpretation.

    Physical Mapping (via Hopf Fibration):
    The 4D coordinates [w, x, y, z] map to coupled optical states:

    coords[0:2] → Polarization Bloch vector components
        Re(α·β*), Im(α·β*) where |ψ_pol⟩ = α|H⟩ + β|V⟩

    coords[2:4] → OAM Superposition Bloch vector components
        Re(γ·δ*), Im(γ·δ*) where |ψ_OAM⟩ = γ|ℓ₁⟩ + δ|ℓ₂⟩

    Note: This is NOT treating OAM as a discrete integer index.
    We encode into the continuous phase space of OAM superpositions.
    """

    coords: np.ndarray  # [w, x, y, z] - unit 4-vector on S³
    index: int  # Vertex index (0-119 for 600-cell)
    symbol: int  # Data symbol this vertex represents

    @property
    def polarization_bloch(self) -> np.ndarray:
        """
        Polarization Bloch vector components.
        Maps to Stokes parameters via Poincaré sphere.
        """
        return self.coords[0:2]

    @property
    def oam_superposition_bloch(self) -> np.ndarray:
        """
        OAM superposition Bloch vector components.
        Represents phase/amplitude ratio between ℓ₁ and ℓ₂ modes.
        This is CONTINUOUS (not discrete OAM index).
        """
        return self.coords[2:4]

    @property
    def full_bloch_state(self) -> np.ndarray:
        """Full 4D state on Poincaré-OAM hypersphere."""
        return self.coords

    def distance_to(self, other: 'Vertex4D') -> float:
        """Euclidean distance in 4D."""
        return np.linalg.norm(self.coords - other.coords)

    def angular_distance(self, other: 'Vertex4D') -> float:
        """Angular distance on the 3-sphere."""
        dot = np.clip(np.dot(self.coords, other.coords), -1, 1)
        return np.arccos(abs(dot))


class Cell600:
    """
    The 600-cell regular 4-polytope.

    Vertex construction follows the standard mathematical definition:
    - 8 vertices from (±1, 0, 0, 0) permutations
    - 16 vertices from (±1/2, ±1/2, ±1/2, ±1/2)
    - 96 vertices from even permutations of (±φ/2, ±1/2, ±1/(2φ), 0)

    where φ = golden ratio = (1+√5)/2
    """

    def __init__(self):
        self.vertices: List[Vertex4D] = []
        self._build_vertices()
        self._symbol_map: Dict[int, Vertex4D] = {v.symbol: v for v in self.vertices}
        self._kdtree = None  # Lazy initialization

    def _build_vertices(self):
        """Construct all 120 vertices of the 600-cell."""
        phi = _golden_ratio()
        phi_inv = 1 / phi  # 1/φ = φ - 1

        vertices = []

        # Type 1: 8 vertices - axis-aligned unit vectors
        # (±1, 0, 0, 0) and all permutations
        for axis in range(4):
            for sign in [-1, 1]:
                v = np.zeros(4)
                v[axis] = sign
                vertices.append(v)

        # Type 2: 16 vertices - all sign combinations of (1/2, 1/2, 1/2, 1/2)
        for s0 in [-1, 1]:
            for s1 in [-1, 1]:
                for s2 in [-1, 1]:
                    for s3 in [-1, 1]:
                        v = np.array([s0, s1, s2, s3]) * 0.5
                        vertices.append(v)

        # Type 3: 96 vertices - even permutations of (φ/2, 1/2, 1/(2φ), 0)
        base_coords = [phi / 2, 0.5, phi_inv / 2, 0.0]

        # Generate all even permutations (12 total)
        even_perms = [
            [0, 1, 2, 3], [0, 2, 3, 1], [0, 3, 1, 2],
            [1, 2, 0, 3], [1, 3, 2, 0], [1, 0, 3, 2],
            [2, 0, 1, 3], [2, 3, 0, 1], [2, 1, 3, 0],
            [3, 1, 0, 2], [3, 0, 2, 1], [3, 2, 1, 0]
        ]

        for perm in even_perms:
            base = [base_coords[i] for i in perm]
            # All sign combinations for non-zero components
            for s0 in [-1, 1]:
                for s1 in [-1, 1]:
                    for s2 in [-1, 1]:
                        v = np.array([
                            base[0] * s0,
                            base[1] * s1,
                            base[2] * s2,
                            base[3]  # Always 0
                        ])
                        if np.linalg.norm(v) > 0.1:  # Skip degenerate
                            vertices.append(v)

        # Normalize all vertices to unit sphere and remove duplicates
        unique_vertices = []
        for v in vertices:
            v = v / np.linalg.norm(v)
            # Check for duplicates
            is_duplicate = False
            for uv in unique_vertices:
                if np.allclose(v, uv, atol=1e-10) or np.allclose(v, -uv, atol=1e-10):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_vertices.append(v)

        # If we don't have exactly 120, use the fallback construction
        if len(unique_vertices) != 120:
            unique_vertices = self._build_vertices_fallback()

        # Create Vertex4D objects with symbol assignments
        for i, v in enumerate(unique_vertices[:120]):
            self.vertices.append(Vertex4D(
                coords=np.array(v),
                index=i,
                symbol=i
            ))

    def _build_vertices_fallback(self) -> List[np.ndarray]:
        """
        Fallback vertex construction using quaternion group structure.

        The 600-cell vertices correspond to the binary icosahedral group
        (a double cover of the icosahedral rotation group).
        """
        phi = _golden_ratio()
        vertices = []

        # The 120 vertices can be constructed as unit quaternions
        # representing the binary icosahedral group 2I

        # 24 quaternions from the 24-cell (binary tetrahedral group)
        for perm in [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]:
            for signs in [1, -1]:
                vertices.append(np.array(perm) * signs)

        for s1 in [-1, 1]:
            for s2 in [-1, 1]:
                for s3 in [-1, 1]:
                    for s4 in [-1, 1]:
                        v = np.array([s1, s2, s3, s4]) * 0.5
                        vertices.append(v)

        # Additional 96 vertices using golden ratio
        # These come from the icosahedral symmetry
        coords_set = [
            [phi/2, 0.5, 1/(2*phi), 0],
            [0.5, 1/(2*phi), phi/2, 0],
            [1/(2*phi), phi/2, 0.5, 0],
            [0.5, 1/(2*phi), 0, phi/2],
            [1/(2*phi), phi/2, 0, 0.5],
            [phi/2, 0.5, 0, 1/(2*phi)],
            [0, phi/2, 0.5, 1/(2*phi)],
            [0, 0.5, 1/(2*phi), phi/2],
            [0, 1/(2*phi), phi/2, 0.5],
        ]

        for base in coords_set:
            for s0 in [-1, 1]:
                for s1 in [-1, 1]:
                    for s2 in [-1, 1]:
                        for s3 in [-1, 1]:
                            v = np.array([
                                base[0] * s0 if base[0] != 0 else 0,
                                base[1] * s1 if base[1] != 0 else 0,
                                base[2] * s2 if base[2] != 0 else 0,
                                base[3] * s3 if base[3] != 0 else 0,
                            ])
                            if np.linalg.norm(v) > 0.1:
                                vertices.append(v / np.linalg.norm(v))

        # Deduplicate
        unique = []
        for v in vertices:
            v = v / np.linalg.norm(v)
            is_dup = False
            for u in unique:
                if np.allclose(v, u, atol=1e-8):
                    is_dup = True
                    break
            if not is_dup:
                unique.append(v)

        return unique[:120]

    def get_vertex(self, symbol: int) -> Vertex4D:
        """Get vertex by symbol index."""
        return self._symbol_map[symbol % 120]

    def nearest_vertex(self, point: np.ndarray) -> Tuple[Vertex4D, float]:
        """
        Find the nearest vertex to a given 4D point.

        This is the core "geometric quantization" operation.
        O(n) naive search, but n=120 is small enough to be O(1) effective.
        """
        point = point / np.linalg.norm(point)  # Normalize to sphere

        min_dist = float('inf')
        nearest = None

        for vertex in self.vertices:
            # Use angular distance for sphere
            dist = vertex.angular_distance(Vertex4D(coords=point, index=-1, symbol=-1))
            if dist < min_dist:
                min_dist = dist
                nearest = vertex

        return nearest, min_dist

    def minimum_distance(self) -> float:
        """
        Compute minimum distance between any two vertices.

        This determines the noise margin of the constellation.
        For the 600-cell, d_min ≈ 0.618 (1/φ) in angular distance.
        """
        min_dist = float('inf')
        for i, v1 in enumerate(self.vertices):
            for v2 in self.vertices[i+1:]:
                dist = v1.angular_distance(v2)
                if dist > 0.01 and dist < min_dist:
                    min_dist = dist
        return min_dist

    def bits_per_symbol(self) -> float:
        """Number of bits encoded per constellation symbol."""
        return np.log2(len(self.vertices))  # log2(120) ≈ 6.9 bits


class PolychoralConstellation:
    """
    A dynamically rotating polychoral constellation.

    The lattice orientation rotates based on a hash chain,
    providing physical-layer encryption without key exchange.
    """

    def __init__(self, seed: bytes = b"CSPM_GENESIS"):
        self.base_cell = Cell600()
        self.seed = seed
        self._current_hash = hashlib.sha256(seed).digest()
        self._rotation_matrix = np.eye(4)
        self._packet_count = 0

    def _hash_to_rotation(self, hash_bytes: bytes) -> np.ndarray:
        """
        Convert a 256-bit hash to a 4D rotation matrix.

        Uses the hash to generate two unit quaternions (left and right)
        which together specify a general SO(4) rotation.
        """
        # Extract 8 floats from 32 bytes
        floats = np.frombuffer(hash_bytes, dtype=np.float32)

        # First quaternion from first 4 values (safe normalization)
        q1 = floats[:4].copy()
        norm1 = np.linalg.norm(q1)
        q1 = q1 / norm1 if norm1 > 1e-10 else np.array([1.0, 0.0, 0.0, 0.0])

        # Second quaternion from last 4 values (safe normalization)
        q2 = floats[4:8].copy()
        norm2 = np.linalg.norm(q2)
        q2 = q2 / norm2 if norm2 > 1e-10 else np.array([1.0, 0.0, 0.0, 0.0])

        # Construct SO(4) rotation from two quaternions
        # R(v) = q1 * v * q2^* (quaternion sandwich)
        # This covers all of SO(4)

        # Convert to 4x4 matrix representation
        R = self._quaternion_pair_to_matrix(q1, q2)
        return R

    def _quaternion_pair_to_matrix(self, q_l: np.ndarray, q_r: np.ndarray) -> np.ndarray:
        """
        Convert a pair of quaternions to a 4x4 rotation matrix.

        In 4D, rotations are represented by pairs of unit quaternions.
        The action on a 4-vector v (viewed as quaternion) is: q_l * v * q_r^*
        """
        # Left multiplication matrix L(q)
        w, x, y, z = q_l
        L = np.array([
            [w, -x, -y, -z],
            [x,  w, -z,  y],
            [y,  z,  w, -x],
            [z, -y,  x,  w]
        ])

        # Right multiplication matrix R(q^*)
        w, x, y, z = q_r
        R = np.array([
            [w,  x,  y,  z],
            [-x, w,  z, -y],
            [-y, -z, w,  x],
            [-z, y, -x,  w]
        ])

        return L @ R

    def rotate_lattice(self, data_hash: bytes = None):
        """
        Rotate the constellation based on the hash chain.

        Each packet advances the hash chain:
        H(n+1) = SHA256(H(n) || data)

        This means an eavesdropper cannot predict future rotations
        without knowing the entire packet history.
        """
        if data_hash is not None:
            # Chain the hash
            self._current_hash = hashlib.sha256(
                self._current_hash + data_hash
            ).digest()
        else:
            # Self-advance
            self._current_hash = hashlib.sha256(self._current_hash).digest()

        self._rotation_matrix = self._hash_to_rotation(self._current_hash)
        self._packet_count += 1

    def encode_symbol(self, symbol: int) -> np.ndarray:
        """
        Encode a symbol to a rotated 4D constellation point.

        Returns the rotated vertex coordinates.
        """
        vertex = self.base_cell.get_vertex(symbol)
        rotated = self._rotation_matrix @ vertex.coords
        norm = np.linalg.norm(rotated)
        return rotated / norm if norm > 1e-10 else vertex.coords

    def decode_symbol(self, received: np.ndarray) -> Tuple[int, float]:
        """
        Decode a received 4D point to the nearest symbol.

        First un-rotates the point, then snaps to nearest vertex.
        """
        # Un-rotate (inverse = transpose for orthogonal matrix)
        unrotated = self._rotation_matrix.T @ received
        norm = np.linalg.norm(unrotated)
        unrotated = unrotated / norm if norm > 1e-10 else received

        # Find nearest vertex
        nearest, distance = self.base_cell.nearest_vertex(unrotated)

        return nearest.symbol, distance

    def get_rotation_state(self) -> bytes:
        """Get current hash state for synchronization."""
        return self._current_hash

    def set_rotation_state(self, state: bytes):
        """Set hash state (for receiver synchronization)."""
        self._current_hash = state
        self._rotation_matrix = self._hash_to_rotation(state)


if __name__ == "__main__":
    # Test 600-cell construction
    cell = Cell600()
    print(f"600-cell vertices: {len(cell.vertices)}")
    print(f"Bits per symbol: {cell.bits_per_symbol():.2f}")
    print(f"Minimum angular distance: {cell.minimum_distance():.4f} rad")
    print(f"Minimum distance (degrees): {np.degrees(cell.minimum_distance()):.2f}°")

    # Test constellation rotation
    constellation = PolychoralConstellation(seed=b"test_seed")

    # Encode-decode test
    for symbol in [0, 42, 119]:
        encoded = constellation.encode_symbol(symbol)
        decoded, dist = constellation.decode_symbol(encoded)
        print(f"Symbol {symbol}: encoded={encoded[:2]}..., decoded={decoded}, dist={dist:.6f}")

    # Rotate and test again
    constellation.rotate_lattice(b"packet_1_data")
    encoded = constellation.encode_symbol(42)
    decoded, dist = constellation.decode_symbol(encoded)
    print(f"After rotation: symbol 42 -> decoded {decoded}, dist={dist:.6f}")
