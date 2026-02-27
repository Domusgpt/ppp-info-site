"""
Fractal Polychoral Constellation - Hierarchical Geometric Modulation

Instead of a single 600-cell, we use NESTED HIERARCHICAL STRUCTURES
that provide:
1. Graceful degradation (decode coarse at low SNR, fine at high SNR)
2. Multi-resolution encoding (like geometric JPEG)
3. Independent rotation per level (more security dimensions)
4. Adaptive rate based on channel conditions

Architecture:
                        Level 0 (Coarse)
                             ●
                            /|\
                           / | \
                Level 1   ●  ●  ●   (Refinement)
                         /|\ |  |\
                        ● ● ●●  ● ●  Level 2 (Fine)

Each level subdivides the Voronoi cells of the previous level.

Copyright (c) 2025-2026 Clear Seas Solutions LLC
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import hashlib


@dataclass
class FractalVertex:
    """A vertex in the fractal constellation with hierarchical addressing."""
    coords: np.ndarray          # 4D coordinates on S³
    level: int                  # Hierarchy level (0 = coarsest)
    path: Tuple[int, ...]       # Path from root: (level0_idx, level1_idx, ...)

    @property
    def symbol(self) -> int:
        """Compute unique symbol ID from hierarchical path."""
        # Encode path as single integer
        result = 0
        multiplier = 1
        for idx in reversed(self.path):
            result += idx * multiplier
            multiplier *= 24  # Max branching factor
        return result

    def angular_distance(self, other: 'FractalVertex') -> float:
        """Angular distance on S³."""
        dot = np.clip(np.dot(self.coords, other.coords), -1, 1)
        return np.arccos(dot)


class RegularPolytope:
    """Base class for regular polytopes used at each fractal level."""

    def __init__(self, vertices: np.ndarray, center: np.ndarray = None):
        """
        Args:
            vertices: Array of shape (N, 4) with unit vectors
            center: Center point (for subdivision), defaults to origin
        """
        self.vertices = vertices
        self.center = center if center is not None else np.zeros(4)
        self.n_vertices = len(vertices)

    @classmethod
    def cell_24(cls, center: np.ndarray = None, scale: float = 1.0) -> 'RegularPolytope':
        """
        24-cell: 24 vertices, good for coarse level.

        Vertices are:
        - 8 axis-aligned: permutations of (±1, 0, 0, 0)
        - 16 half-integer: (±1/2, ±1/2, ±1/2, ±1/2)
        """
        vertices = []

        # 8 axis-aligned
        for i in range(4):
            for s in [-1, 1]:
                v = np.zeros(4)
                v[i] = s
                vertices.append(v)

        # 16 half-integer
        for s0 in [-1, 1]:
            for s1 in [-1, 1]:
                for s2 in [-1, 1]:
                    for s3 in [-1, 1]:
                        vertices.append(np.array([s0, s1, s2, s3]) * 0.5)

        vertices = np.array(vertices)
        # Normalize to unit sphere
        vertices = vertices / np.linalg.norm(vertices, axis=1, keepdims=True)

        if center is not None and np.linalg.norm(center) > 1e-10:
            # Translate and renormalize (geodesic offset on S³)
            vertices = cls._geodesic_translate(vertices, center, scale)

        return cls(vertices, center)

    @classmethod
    def cell_5(cls, center: np.ndarray = None, scale: float = 0.3) -> 'RegularPolytope':
        """
        5-cell (pentatope): 5 vertices, good for fine subdivision.

        Regular simplex in 4D.
        """
        # Standard 5-cell vertices (centered at origin)
        phi = (1 + np.sqrt(5)) / 2
        vertices = np.array([
            [1, 1, 1, -1/phi],
            [1, -1, -1, -1/phi],
            [-1, 1, -1, -1/phi],
            [-1, -1, 1, -1/phi],
            [0, 0, 0, phi],
        ], dtype=np.float64)

        # Normalize
        vertices = vertices / np.linalg.norm(vertices, axis=1, keepdims=True)

        if center is not None and np.linalg.norm(center) > 1e-10:
            vertices = cls._geodesic_translate(vertices, center, scale)

        return cls(vertices, center)

    @classmethod
    def cell_8(cls, center: np.ndarray = None, scale: float = 0.4) -> 'RegularPolytope':
        """
        8-cell (tesseract): 16 vertices, medium density.
        """
        vertices = []
        for s0 in [-1, 1]:
            for s1 in [-1, 1]:
                for s2 in [-1, 1]:
                    for s3 in [-1, 1]:
                        vertices.append(np.array([s0, s1, s2, s3]))

        vertices = np.array(vertices) * 0.5
        vertices = vertices / np.linalg.norm(vertices, axis=1, keepdims=True)

        if center is not None and np.linalg.norm(center) > 1e-10:
            vertices = cls._geodesic_translate(vertices, center, scale)

        return cls(vertices, center)

    @staticmethod
    def _geodesic_translate(vertices: np.ndarray, center: np.ndarray, scale: float) -> np.ndarray:
        """
        Translate vertices toward a center point on S³ using geodesic interpolation.

        This creates a "scaled copy" of the polytope centered at a different point.
        """
        center = center / np.linalg.norm(center)
        result = []

        for v in vertices:
            # Geodesic interpolation: move from center toward v by scale amount
            # slerp(center, v, scale)
            dot = np.dot(center, v)
            dot = np.clip(dot, -1, 1)
            theta = np.arccos(dot)

            if theta < 1e-10:
                result.append(center.copy())
            else:
                # Spherical interpolation
                s0 = np.sin((1 - scale) * theta) / np.sin(theta)
                s1 = np.sin(scale * theta) / np.sin(theta)
                new_v = s0 * center + s1 * v
                new_v = new_v / np.linalg.norm(new_v)
                result.append(new_v)

        return np.array(result)


class FractalConstellation:
    """
    Multi-level fractal constellation with graceful degradation.

    Structure:
        Level 0: 24-cell (24 coarse regions) - ~4.6 bits, most robust
        Level 1: 5-cell per region (5 refinements) - ~2.3 bits additional
        Level 2: 5-cell per sub-region (optional) - ~2.3 bits additional

    Total: 24 × 5 = 120 symbols at level 1 (matches 600-cell)
           24 × 5 × 5 = 600 symbols at level 2 (exceeds 600-cell!)

    Graceful degradation:
        - Low SNR: Decode level 0 only → 4.6 bits, very robust
        - Medium SNR: Decode levels 0+1 → 6.9 bits
        - High SNR: Decode levels 0+1+2 → 9.2 bits
    """

    def __init__(self,
                 max_level: int = 1,
                 level_configs: List[Tuple[str, float]] = None,
                 seed: bytes = b"FRACTAL_GENESIS"):
        """
        Args:
            max_level: Maximum refinement level (0=coarse only)
            level_configs: List of (polytope_type, scale) per level
                          Defaults: [("24-cell", 1.0), ("5-cell", 0.3), ("5-cell", 0.1)]
            seed: Random seed for hash chain rotation
        """
        self.max_level = max_level
        self.seed = seed

        # Default configuration
        if level_configs is None:
            level_configs = [
                ("24-cell", 1.0),   # Level 0: 24 coarse regions
                ("5-cell", 0.25),   # Level 1: 5 refinements each
                ("5-cell", 0.08),   # Level 2: 5 further refinements
            ]

        self.level_configs = level_configs[:max_level + 1]

        # Build the fractal structure
        self.levels: List[List[FractalVertex]] = []
        self._build_hierarchy()

        # Hash chain state per level (independent rotations!)
        self._level_hashes = [
            hashlib.sha256(seed + f"_L{i}".encode()).digest()
            for i in range(max_level + 1)
        ]
        self._rotation_matrices = [np.eye(4) for _ in range(max_level + 1)]

        # Symbol lookup
        self._build_symbol_map()

    def _build_hierarchy(self):
        """Recursively build the fractal vertex hierarchy."""
        # Level 0: Base polytope
        base_type, base_scale = self.level_configs[0]
        base_polytope = self._create_polytope(base_type, None, base_scale)

        level_0 = []
        for i, v in enumerate(base_polytope.vertices):
            level_0.append(FractalVertex(
                coords=v,
                level=0,
                path=(i,)
            ))
        self.levels.append(level_0)

        # Higher levels: Subdivide each vertex's Voronoi cell
        for level in range(1, self.max_level + 1):
            poly_type, scale = self.level_configs[level]
            level_vertices = []

            for parent in self.levels[level - 1]:
                # Create mini-polytope centered at parent
                sub_polytope = self._create_polytope(poly_type, parent.coords, scale)

                for j, v in enumerate(sub_polytope.vertices):
                    level_vertices.append(FractalVertex(
                        coords=v,
                        level=level,
                        path=parent.path + (j,)
                    ))

            self.levels.append(level_vertices)

    def _create_polytope(self, ptype: str, center: np.ndarray, scale: float) -> RegularPolytope:
        """Create a polytope of the given type."""
        if ptype == "24-cell":
            return RegularPolytope.cell_24(center, scale)
        elif ptype == "5-cell":
            return RegularPolytope.cell_5(center, scale)
        elif ptype == "8-cell":
            return RegularPolytope.cell_8(center, scale)
        else:
            raise ValueError(f"Unknown polytope type: {ptype}")

    def _build_symbol_map(self):
        """Build lookup from symbol ID to vertex at finest level."""
        self._symbol_to_vertex: Dict[int, FractalVertex] = {}
        self._path_to_vertex: Dict[Tuple[int, ...], FractalVertex] = {}

        # Map finest level vertices with sequential symbol IDs
        for i, vertex in enumerate(self.levels[self.max_level]):
            self._symbol_to_vertex[i] = vertex
            self._path_to_vertex[vertex.path] = vertex

        # Also map all intermediate levels for partial decoding
        for level in self.levels:
            for vertex in level:
                self._path_to_vertex[vertex.path] = vertex

        # Build reverse lookup: path -> symbol ID
        self._path_to_symbol: Dict[Tuple[int, ...], int] = {}
        for sym_id, vertex in self._symbol_to_vertex.items():
            self._path_to_symbol[vertex.path] = sym_id

    @property
    def n_symbols(self) -> int:
        """Total number of symbols at finest level."""
        return len(self.levels[self.max_level])

    @property
    def bits_per_level(self) -> List[float]:
        """Bits encoded at each level."""
        bits = []
        for level in self.levels:
            if level == self.levels[0]:
                bits.append(np.log2(len(level)))
            else:
                # Bits per subdivision
                parent_count = len(self.levels[self.levels.index(level) - 1])
                children_per_parent = len(level) // parent_count
                bits.append(np.log2(children_per_parent))
        return bits

    @property
    def total_bits(self) -> float:
        """Total bits at finest level."""
        return sum(self.bits_per_level)

    def _hash_to_rotation(self, hash_bytes: bytes) -> np.ndarray:
        """Convert hash to 4D rotation matrix."""
        uint_vals = np.frombuffer(hash_bytes, dtype=np.uint32)
        floats = (uint_vals.astype(np.float64) / (2**32 - 1)) * 2 - 1

        q1 = floats[:4].copy()
        q1 = q1 / np.linalg.norm(q1)

        q2 = floats[4:8].copy()
        q2 = q2 / np.linalg.norm(q2)

        return self._quaternion_pair_to_matrix(q1, q2)

    def _quaternion_pair_to_matrix(self, q_l: np.ndarray, q_r: np.ndarray) -> np.ndarray:
        """Convert quaternion pair to SO(4) rotation."""
        w, x, y, z = q_l
        L = np.array([
            [w, -x, -y, -z],
            [x,  w, -z,  y],
            [y,  z,  w, -x],
            [z, -y,  x,  w]
        ])

        w, x, y, z = q_r
        R = np.array([
            [w,  x,  y,  z],
            [-x, w,  z, -y],
            [-y, -z, w,  x],
            [-z, y, -x,  w]
        ])

        return L @ R

    def rotate_level(self, level: int, data_hash: bytes = None):
        """
        Rotate a specific level of the hierarchy.

        INDEPENDENT ROTATION PER LEVEL = more security dimensions!
        Attacker must track N hash chains, not just one.
        """
        if level > self.max_level:
            return

        if data_hash is not None:
            self._level_hashes[level] = hashlib.sha256(
                self._level_hashes[level] + data_hash
            ).digest()
        else:
            self._level_hashes[level] = hashlib.sha256(
                self._level_hashes[level]
            ).digest()

        self._rotation_matrices[level] = self._hash_to_rotation(self._level_hashes[level])

    def rotate_all(self, data_hash: bytes = None):
        """Rotate all levels (synchronized rotation)."""
        for level in range(self.max_level + 1):
            self.rotate_level(level, data_hash)

    def encode(self, symbol: int) -> np.ndarray:
        """
        Encode a symbol to rotated 4D coordinates.

        The encoding applies the hierarchical rotations:
        - Level 0 rotation applied to coarse position
        - Level 1 rotation applied to refinement offset
        - etc.
        """
        vertex = self._symbol_to_vertex[symbol % self.n_symbols]

        # Apply hierarchical rotation
        # Start with the finest level coordinates
        result = vertex.coords.copy()

        # Apply each level's rotation (from coarse to fine)
        for level in range(self.max_level + 1):
            result = self._rotation_matrices[level] @ result

        return result / np.linalg.norm(result)

    def decode(self, received: np.ndarray, max_level: int = None) -> Tuple[Tuple[int, ...], float, List[float]]:
        """
        Hierarchically decode a received signal.

        Args:
            received: 4D received signal vector
            max_level: Maximum level to decode (None = all levels)

        Returns:
            (path, total_distance, level_confidences)

        This enables GRACEFUL DEGRADATION:
        - Under noise, stop at coarse level with high confidence
        - Under good conditions, decode to finest level
        """
        if max_level is None:
            max_level = self.max_level

        # Un-rotate by applying inverse rotations (fine to coarse)
        point = received.copy()
        for level in range(self.max_level, -1, -1):
            point = self._rotation_matrices[level].T @ point
        point = point / np.linalg.norm(point)

        # Hierarchical decoding
        path = []
        confidences = []
        total_dist = 0

        current_center = np.zeros(4)

        for level in range(max_level + 1):
            # Find candidates at this level
            if level == 0:
                candidates = self.levels[0]
            else:
                # Only consider children of current path
                parent_path = tuple(path)
                candidates = [v for v in self.levels[level]
                             if v.path[:-1] == parent_path]

            # Find nearest candidate
            min_dist = float('inf')
            best_idx = 0

            for cand in candidates:
                dist = np.arccos(np.clip(np.dot(point, cand.coords), -1, 1))
                if dist < min_dist:
                    min_dist = dist
                    best_idx = cand.path[level]
                    best_vertex = cand

            path.append(best_idx)
            total_dist += min_dist

            # Confidence: how much closer than second-best?
            distances = sorted([
                np.arccos(np.clip(np.dot(point, c.coords), -1, 1))
                for c in candidates
            ])
            if len(distances) > 1:
                margin = distances[1] - distances[0]
                confidences.append(margin)
            else:
                confidences.append(float('inf'))

        return tuple(path), total_dist, confidences

    def decode_adaptive(self, received: np.ndarray,
                       confidence_threshold: float = 0.1) -> Tuple[Tuple[int, ...], int]:
        """
        Adaptively decode to the level supported by signal quality.

        Stops descending when confidence drops below threshold.
        Returns (path, decoded_level).

        This is the KEY FEATURE: automatic graceful degradation.
        """
        path, total_dist, confidences = self.decode(received)

        # Find deepest level with sufficient confidence
        decoded_level = 0
        final_path = [path[0]]

        for level, conf in enumerate(confidences):
            if conf < confidence_threshold and level > 0:
                break
            decoded_level = level
            if level < len(path):
                final_path = list(path[:level + 1])

        return tuple(final_path), decoded_level

    def get_level_vertices(self, level: int) -> List[FractalVertex]:
        """Get all vertices at a specific level."""
        return self.levels[level]

    def symbol_to_path(self, symbol: int) -> Tuple[int, ...]:
        """Convert symbol ID to hierarchical path."""
        return self._symbol_to_vertex[symbol % self.n_symbols].path

    def path_to_symbol(self, path: Tuple[int, ...]) -> int:
        """Convert hierarchical path to symbol ID."""
        if path in self._path_to_symbol:
            return self._path_to_symbol[path]
        # For partial paths (intermediate levels), find any matching full path
        for full_path, sym_id in self._path_to_symbol.items():
            if full_path[:len(path)] == path:
                return sym_id
        return 0

    def minimum_distance(self, level: int = None) -> float:
        """Minimum angular distance at given level."""
        if level is None:
            level = self.max_level

        vertices = self.levels[level]
        min_dist = float('inf')

        for i, v1 in enumerate(vertices):
            for v2 in vertices[i+1:]:
                dist = v1.angular_distance(v2)
                if dist > 0.01 and dist < min_dist:
                    min_dist = dist

        return min_dist


class FractalCSPM:
    """
    Complete Fractal CSPM system with multi-level security and adaptation.

    Features:
    - Independent hash chain per level
    - Adaptive decoding based on SNR
    - Graceful degradation under noise
    - Higher symbol density than single 600-cell
    """

    def __init__(self,
                 max_level: int = 2,
                 seed: bytes = b"FRACTAL_CSPM"):
        self.constellation = FractalConstellation(max_level=max_level, seed=seed)
        self.packet_count = 0

    def transmit_symbol(self, data: int) -> np.ndarray:
        """Encode and transmit a symbol."""
        return self.constellation.encode(data)

    def receive_symbol(self, received: np.ndarray,
                      snr_estimate: float = None) -> Tuple[int, int, float]:
        """
        Receive and decode a symbol.

        Args:
            received: 4D received vector
            snr_estimate: Optional SNR estimate for adaptive decoding

        Returns:
            (symbol, decoded_level, confidence)
        """
        if snr_estimate is not None:
            # Adaptive threshold based on SNR
            threshold = 0.3 / (1 + snr_estimate / 10)
            path, level = self.constellation.decode_adaptive(received, threshold)
        else:
            path, dist, confs = self.constellation.decode(received)
            level = self.constellation.max_level

        symbol = self.constellation.path_to_symbol(path) if path in self.constellation._path_to_vertex else 0
        confidence = min(confs) if 'confs' in dir() else 0.0

        return symbol, level, confidence

    def advance_rotation(self, packet_data: bytes = None):
        """Advance the hash chain (rotate constellation)."""
        self.constellation.rotate_all(packet_data)
        self.packet_count += 1

    def advance_level_rotation(self, level: int, data: bytes = None):
        """Advance rotation for a specific level only."""
        self.constellation.rotate_level(level, data)

    @property
    def bits_per_symbol(self) -> float:
        """Bits per symbol at full resolution."""
        return self.constellation.total_bits

    def get_rate_for_snr(self, snr_db: float) -> float:
        """
        Estimate achievable rate for given SNR.

        This is the ADAPTIVE RATE feature:
        - Low SNR → fewer bits (coarse only)
        - High SNR → more bits (full resolution)
        """
        bits = self.constellation.bits_per_level

        # Rough mapping: each level needs ~5dB more SNR
        achievable_levels = min(
            len(bits),
            max(1, int((snr_db - 5) / 5) + 1)
        )

        return sum(bits[:achievable_levels])


def demo_fractal():
    """Demonstrate fractal constellation capabilities."""
    print("=" * 70)
    print("FRACTAL CONSTELLATION DEMO")
    print("=" * 70)

    # Create 2-level fractal (24 × 5 = 120 symbols)
    fc = FractalConstellation(max_level=1)

    print(f"\nStructure:")
    print(f"  Level 0: {len(fc.levels[0])} vertices ({fc.bits_per_level[0]:.2f} bits)")
    print(f"  Level 1: {len(fc.levels[1])} vertices (+{fc.bits_per_level[1]:.2f} bits)")
    print(f"  Total: {fc.n_symbols} symbols, {fc.total_bits:.2f} bits/symbol")

    print(f"\nMinimum distances:")
    print(f"  Level 0: {np.degrees(fc.minimum_distance(0)):.2f}°")
    print(f"  Level 1: {np.degrees(fc.minimum_distance(1)):.2f}°")

    # Test encoding/decoding
    print(f"\nEncode/Decode test (no noise):")
    for sym in [0, 42, 119]:
        encoded = fc.encode(sym)
        path, dist, confs = fc.decode(encoded)
        recovered = fc.path_to_symbol(path)
        print(f"  Symbol {sym}: path={path}, recovered={recovered}, dist={dist:.6f}")

    # Test graceful degradation
    print(f"\nGraceful degradation test:")
    symbol = 42
    encoded = fc.encode(symbol)

    for noise_std in [0.0, 0.1, 0.2, 0.3, 0.5]:
        np.random.seed(42)
        noisy = encoded + np.random.randn(4) * noise_std
        noisy = noisy / np.linalg.norm(noisy)

        path, level = fc.decode_adaptive(noisy, confidence_threshold=0.15)
        bits = sum(fc.bits_per_level[:level+1])
        print(f"  Noise σ={noise_std:.1f}: decoded level={level}, "
              f"path={path}, bits={bits:.1f}")

    # Test independent level rotation
    print(f"\nIndependent level rotation:")
    fc2 = FractalConstellation(max_level=1, seed=b"TEST")

    # Rotate only level 0
    print("  Before rotation:")
    enc1 = fc2.encode(42)
    print(f"    Symbol 42 → {enc1[:2]}...")

    fc2.rotate_level(0, b"rotate_coarse")
    print("  After level 0 rotation:")
    enc2 = fc2.encode(42)
    print(f"    Symbol 42 → {enc2[:2]}...")

    fc2.rotate_level(1, b"rotate_fine")
    print("  After level 1 rotation:")
    enc3 = fc2.encode(42)
    print(f"    Symbol 42 → {enc3[:2]}...")

    # Compare to 600-cell
    print(f"\nComparison to 600-cell:")
    print(f"  600-cell: 120 symbols, 6.91 bits")
    print(f"  Fractal L1: {fc.n_symbols} symbols, {fc.total_bits:.2f} bits")

    # Level 2 demo
    fc3 = FractalConstellation(max_level=2)
    print(f"  Fractal L2: {fc3.n_symbols} symbols, {fc3.total_bits:.2f} bits")
    print(f"             (5× more symbols than 600-cell!)")


if __name__ == "__main__":
    demo_fractal()
