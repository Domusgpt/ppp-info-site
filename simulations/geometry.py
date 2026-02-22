#!/usr/bin/env python3
"""
=============================================================================
GEOMETRY ENGINE - 4D Polytope Generation and Nearest-Neighbor Lookup
=============================================================================

This module implements the geometric foundations for Polytopal Orthogonal
Modulation (POM). It generates high-dimensional polytopes and provides
efficient spatial indexing for geometric quantization.

PHYSICAL INTERPRETATION:
------------------------
In the POM protocol, data is modulated onto the vertices of regular polytopes
inscribed on a unit hypersphere. The 600-cell (Hexacosichoron) is optimal for
4D because:

1. It has the maximum number of vertices (120) among regular 4D polytopes
2. Its kissing number (12) provides optimal sphere packing
3. The golden ratio symmetry enables efficient recursive subdivision

The vertices represent "codewords" in a spherical code. The minimum distance
between codewords (d_min = 1/φ ≈ 0.618) determines noise tolerance.

Author: PPP Research Team
License: MIT
=============================================================================
"""

import numpy as np
from scipy.spatial import KDTree
from typing import Tuple, Optional, List
from dataclasses import dataclass


# =============================================================================
# MATHEMATICAL CONSTANTS
# =============================================================================

# The Golden Ratio - fundamental constant of icosahedral symmetry
PHI = (1 + np.sqrt(5)) / 2  # φ ≈ 1.6180339887498949

# Inverse Golden Ratio (also equals φ - 1)
PHI_INV = PHI - 1  # 1/φ ≈ 0.6180339887498949


# =============================================================================
# DATA CLASSES FOR GEOMETRIC PROPERTIES
# =============================================================================

@dataclass
class ConstellationMetrics:
    """Container for constellation performance metrics."""
    num_vertices: int
    bits_per_symbol: float  # log2(num_vertices)
    usable_bits: int        # floor(bits_per_symbol)
    min_distance: float     # Minimum Euclidean distance between vertices
    avg_distance: float     # Average pairwise distance
    kissing_number: int     # Number of nearest neighbors per vertex
    packing_efficiency: float  # Ratio of min_distance to theoretical max
    dimensionality: int


# =============================================================================
# CLASS: Polychoron600 - The 600-Cell Geometry Engine
# =============================================================================

class Polychoron600:
    """
    Generates and indexes the 120 vertices of the 600-cell on a unit 4-sphere.

    The 600-cell is a regular 4-dimensional polytope with:
    - 120 vertices
    - 720 edges
    - 1200 triangular faces
    - 600 tetrahedral cells

    VERTEX FAMILIES:
    ----------------
    The 120 vertices decompose into three orbits under the symmetry group H4:

    Family 1 (8 vertices):
        Permutations of (±1, 0, 0, 0)
        These form the vertices of a 16-cell (hyperoctahedron)

    Family 2 (16 vertices):
        All sign combinations of (±1/2, ±1/2, ±1/2, ±1/2)
        These form the vertices of a tesseract (8-cell)

    Family 3 (96 vertices):
        Even permutations of (0, ±1/(2φ), ±1/2, ±φ/2)
        These encode the icosahedral golden ratio symmetry

    Together, these 120 vertices form the binary icosahedral group 2I,
    which is isomorphic to SL(2,5) - the special linear group over F5.

    SPATIAL INDEXING:
    -----------------
    Uses scipy's KDTree for O(log N) nearest-neighbor queries, enabling
    real-time geometric quantization in the demodulator.
    """

    def __init__(self, use_kdtree: bool = True):
        """
        Initialize the 600-cell geometry.

        Args:
            use_kdtree: If True, build a KDTree for fast nearest-neighbor lookup.
                        Set to False for memory-constrained environments.
        """
        self.vertices = self._generate_vertices()
        self.num_vertices = len(self.vertices)
        self.dimensionality = 4

        # Compute constellation metrics
        self.metrics = self._compute_metrics()

        # Build spatial index for fast demodulation
        self.kdtree = KDTree(self.vertices) if use_kdtree else None

        # Precompute the vertex-to-vertex distance matrix for batch operations
        self._distance_matrix: Optional[np.ndarray] = None

    def _generate_vertices(self) -> np.ndarray:
        """
        Generate all 120 vertices of the 600-cell.

        The construction follows the standard mathematical definition using
        quaternion representation. Each vertex can be viewed as a unit quaternion
        in the binary icosahedral group.

        Returns:
            np.ndarray: Shape (120, 4), each row is a unit 4D vector
        """
        vertices = []

        # =====================================================================
        # FAMILY 1: Axis-aligned vertices (±1, 0, 0, 0) - 8 vertices
        # =====================================================================
        # These are the vertices where exactly one coordinate is ±1
        # They form the vertices of a cross-polytope (16-cell with only + and -)
        for axis in range(4):
            for sign in [-1.0, 1.0]:
                v = np.zeros(4)
                v[axis] = sign
                vertices.append(v)

        # =====================================================================
        # FAMILY 2: Hypercube vertices (±1/2, ±1/2, ±1/2, ±1/2) - 16 vertices
        # =====================================================================
        # All 2^4 = 16 combinations of signs
        # These form the vertices of a tesseract inscribed in the unit sphere
        for s0 in [-0.5, 0.5]:
            for s1 in [-0.5, 0.5]:
                for s2 in [-0.5, 0.5]:
                    for s3 in [-0.5, 0.5]:
                        vertices.append(np.array([s0, s1, s2, s3]))

        # =====================================================================
        # FAMILY 3: Golden ratio vertices - 96 vertices
        # =====================================================================
        # Even permutations of (0, ±1/(2φ), ±1/2, ±φ/2)
        #
        # The three non-zero magnitudes satisfy:
        #   (1/(2φ))² + (1/2)² + (φ/2)² = 1
        #
        # This ensures all vertices lie on the unit 3-sphere.
        #
        # Values:
        #   φ/2 ≈ 0.809016994  (largest)
        #   1/2 = 0.5          (middle)
        #   1/(2φ) ≈ 0.309016994 (smallest)

        half = 0.5
        half_phi = PHI / 2          # ≈ 0.809016994
        half_phi_inv = PHI_INV / 2  # ≈ 0.309016994

        # Base coordinates: (0, 1/(2φ), 1/2, φ/2) in ascending order of position
        base_values = [0.0, half_phi_inv, half, half_phi]

        # The 12 even permutations of 4 elements (alternating group A4)
        # An even permutation has an even number of transpositions
        even_permutations = [
            [0, 1, 2, 3], [0, 2, 3, 1], [0, 3, 1, 2],
            [1, 0, 3, 2], [1, 2, 0, 3], [1, 3, 2, 0],
            [2, 0, 1, 3], [2, 1, 3, 0], [2, 3, 0, 1],
            [3, 0, 2, 1], [3, 1, 0, 2], [3, 2, 1, 0]
        ]

        for perm in even_permutations:
            # Apply permutation: result[i] = base_values[perm[i]]
            permuted = [base_values[perm[i]] for i in range(4)]

            # Generate all 16 sign combinations
            # (Zero coordinates remain zero regardless of sign)
            for s0 in [-1, 1]:
                for s1 in [-1, 1]:
                    for s2 in [-1, 1]:
                        for s3 in [-1, 1]:
                            v = np.array([
                                s0 * permuted[0],
                                s1 * permuted[1],
                                s2 * permuted[2],
                                s3 * permuted[3]
                            ])
                            vertices.append(v)

        # Convert to numpy array
        vertices = np.array(vertices)

        # Normalize to ensure unit magnitude (handles numerical precision)
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        vertices = vertices / norms

        # Remove duplicates from sign combinations on zero coordinates
        vertices = np.unique(np.round(vertices, decimals=12), axis=0)

        return vertices

    def _compute_metrics(self) -> ConstellationMetrics:
        """
        Compute and return constellation performance metrics.

        These metrics are crucial for comparing POM against QAM:
        - min_distance determines noise tolerance
        - kissing_number indicates packing efficiency
        - bits_per_symbol determines throughput
        """
        n = self.num_vertices

        # Compute pairwise distance matrix
        diff = self.vertices[:, np.newaxis, :] - self.vertices[np.newaxis, :, :]
        distances = np.linalg.norm(diff, axis=2)

        # Mask diagonal (self-distances)
        np.fill_diagonal(distances, np.inf)

        # Minimum distance (determines noise tolerance)
        min_dist = np.min(distances)

        # Average distance (excluding self)
        avg_dist = np.mean(distances[distances != np.inf])

        # Kissing number: neighbors at minimum distance
        # For 600-cell, this should be exactly 12
        threshold = min_dist * 1.001  # Small tolerance for numerical precision
        kissing = int(np.median([np.sum(distances[i] < threshold) for i in range(n)]))

        # Theoretical maximum min_distance for N points on unit sphere in 4D
        # This is the spherical code bound (approximate)
        theoretical_max = 2.0  # Diameter of unit sphere

        return ConstellationMetrics(
            num_vertices=n,
            bits_per_symbol=np.log2(n),
            usable_bits=int(np.floor(np.log2(n))),
            min_distance=min_dist,
            avg_distance=avg_dist,
            kissing_number=kissing,
            packing_efficiency=min_dist / theoretical_max,
            dimensionality=4
        )

    def nearest_vertex(self, point: np.ndarray) -> Tuple[int, float]:
        """
        Find the nearest vertex to a given 4D point.

        This is the core operation of geometric quantization (demodulation).
        Uses KDTree for O(log N) complexity.

        Args:
            point: A 4D numpy array (single point)

        Returns:
            Tuple of (vertex_index, distance)
        """
        if self.kdtree is not None:
            dist, idx = self.kdtree.query(point)
            return int(idx), float(dist)
        else:
            # Fallback to brute force
            distances = np.linalg.norm(self.vertices - point, axis=1)
            idx = np.argmin(distances)
            return int(idx), float(distances[idx])

    def batch_nearest_vertices(self, points: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Vectorized nearest-vertex lookup for multiple points.

        This is the high-performance demodulation path for batch processing.

        Args:
            points: Shape (N, 4) array of 4D points

        Returns:
            Tuple of (indices array, distances array)
        """
        if self.kdtree is not None:
            distances, indices = self.kdtree.query(points)
            return indices.astype(np.int32), distances
        else:
            # Brute force fallback (still vectorized)
            diff = points[:, np.newaxis, :] - self.vertices[np.newaxis, :, :]
            all_distances = np.linalg.norm(diff, axis=2)
            indices = np.argmin(all_distances, axis=1)
            distances = all_distances[np.arange(len(points)), indices]
            return indices.astype(np.int32), distances

    def get_vertex(self, index: int) -> np.ndarray:
        """Get vertex by index (with wraparound)."""
        return self.vertices[index % self.num_vertices].copy()

    def project_to_3d(self, method: str = 'stereographic') -> np.ndarray:
        """
        Project 4D vertices to 3D for visualization.

        Args:
            method:
                'stereographic' - Conformal projection from north pole (0,0,0,1)
                'orthographic' - Simply drop the 4th coordinate

        Returns:
            Shape (N, 3) array of 3D coordinates
        """
        if method == 'stereographic':
            # Stereographic projection: S³ → R³
            # Projects from the "north pole" (0,0,0,1)
            # Formula: (x,y,z,w) → (x,y,z)/(1-w)
            w = self.vertices[:, 3]
            denom = 1.0 - w + 1e-10  # Avoid division by zero at pole
            return self.vertices[:, :3] / denom[:, np.newaxis]
        else:
            # Orthographic: just drop w
            return self.vertices[:, :3].copy()

    def get_voronoi_neighbors(self, index: int) -> np.ndarray:
        """
        Get indices of Voronoi neighbors (vertices at minimum distance).

        For the 600-cell, each vertex has exactly 12 Voronoi neighbors
        (the kissing number of the 4D lattice).

        Args:
            index: Vertex index

        Returns:
            Array of neighbor indices
        """
        vertex = self.vertices[index]
        distances = np.linalg.norm(self.vertices - vertex, axis=1)
        threshold = self.metrics.min_distance * 1.001
        neighbors = np.where((distances < threshold) & (distances > 0))[0]
        return neighbors

    def __repr__(self) -> str:
        m = self.metrics
        return (
            f"Polychoron600(\n"
            f"  vertices: {m.num_vertices}\n"
            f"  bits_per_symbol: {m.bits_per_symbol:.3f} ({m.usable_bits} usable)\n"
            f"  min_distance: {m.min_distance:.6f}\n"
            f"  kissing_number: {m.kissing_number}\n"
            f"  packing_efficiency: {m.packing_efficiency:.4f}\n"
            f")"
        )


# =============================================================================
# CLASS: QAM64Constellation - Standard 64-QAM for Comparison
# =============================================================================

class QAM64Constellation:
    """
    Standard 64-QAM constellation for benchmarking.

    64-QAM uses an 8×8 grid of complex symbols:
    - 64 symbols = 6 bits per symbol
    - Real and Imaginary parts each take values from {-7,-5,-3,-1,1,3,5,7}

    For fair comparison with POM, we:
    1. Normalize to unit average energy
    2. Embed the 2D constellation in 4D as (Re, Im, 0, 0)

    This embedding allows us to use the same noise model (4D Gaussian)
    while respecting the fact that QAM only uses 2 dimensions.
    """

    def __init__(self):
        """Generate and normalize the 64-QAM constellation."""
        # Standard 8-level PAM values
        levels = np.array([-7, -5, -3, -1, 1, 3, 5, 7], dtype=np.float64)

        # Create 8×8 grid
        re, im = np.meshgrid(levels, levels)
        self.symbols_2d = np.stack([re.flatten(), im.flatten()], axis=1)

        # Normalize to unit average power
        # E[|s|²] = E[Re² + Im²] = 2 * E[level²] = 2 * mean([49,25,9,1,1,9,25,49]) = 42
        avg_power = np.mean(np.sum(self.symbols_2d**2, axis=1))
        self.symbols_2d = self.symbols_2d / np.sqrt(avg_power)

        # Embed in 4D for fair noise comparison
        self.symbols_4d = np.zeros((64, 4))
        self.symbols_4d[:, :2] = self.symbols_2d

        self.num_symbols = 64
        self.dimensionality = 2  # Actual dimension used
        self.dimensionality_embedded = 4  # Embedded dimension

        # Build KDTree for 2D lookups (more efficient than 4D)
        self.kdtree_2d = KDTree(self.symbols_2d)

        # Compute metrics
        self.metrics = self._compute_metrics()

    def _compute_metrics(self) -> ConstellationMetrics:
        """Compute QAM constellation metrics."""
        diff = self.symbols_2d[:, np.newaxis, :] - self.symbols_2d[np.newaxis, :, :]
        distances = np.linalg.norm(diff, axis=2)
        np.fill_diagonal(distances, np.inf)

        min_dist = np.min(distances)
        avg_dist = np.mean(distances[distances != np.inf])

        # Kissing number for square lattice is 4
        threshold = min_dist * 1.001
        kissing = int(np.median([np.sum(distances[i] < threshold) for i in range(64)]))

        return ConstellationMetrics(
            num_vertices=64,
            bits_per_symbol=6.0,
            usable_bits=6,
            min_distance=min_dist,
            avg_distance=avg_dist,
            kissing_number=kissing,
            packing_efficiency=min_dist / 2.0,
            dimensionality=2
        )

    def nearest_symbol_2d(self, point_2d: np.ndarray) -> Tuple[int, float]:
        """Find nearest symbol in 2D space."""
        dist, idx = self.kdtree_2d.query(point_2d)
        return int(idx), float(dist)

    def batch_nearest_symbols_2d(self, points_2d: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Batch nearest-symbol lookup in 2D."""
        distances, indices = self.kdtree_2d.query(points_2d)
        return indices.astype(np.int32), distances

    def get_symbol_2d(self, index: int) -> np.ndarray:
        """Get 2D symbol by index."""
        return self.symbols_2d[index % 64].copy()

    def get_symbol_4d(self, index: int) -> np.ndarray:
        """Get 4D-embedded symbol by index."""
        return self.symbols_4d[index % 64].copy()

    def __repr__(self) -> str:
        m = self.metrics
        return (
            f"QAM64Constellation(\n"
            f"  symbols: {m.num_vertices}\n"
            f"  bits_per_symbol: {m.bits_per_symbol:.1f}\n"
            f"  min_distance: {m.min_distance:.6f}\n"
            f"  kissing_number: {m.kissing_number}\n"
            f"  dimensionality: {m.dimensionality}D\n"
            f")"
        )


# =============================================================================
# ADDITIONAL POLYTOPES FOR EXTENDED ANALYSIS
# =============================================================================

class Polytope24Cell:
    """
    The 24-cell (Icositetrachoron) - another regular 4D polytope.

    Has 24 vertices with kissing number 8.
    Useful for comparing different 4D lattice structures.

    Vertices are permutations of (±1, ±1, 0, 0).
    """

    def __init__(self, use_kdtree: bool = True):
        self.vertices = self._generate_vertices()
        self.num_vertices = len(self.vertices)
        self.dimensionality = 4
        self.kdtree = KDTree(self.vertices) if use_kdtree else None

    def _generate_vertices(self) -> np.ndarray:
        vertices = []

        # All permutations of (±1, ±1, 0, 0)
        for i in range(4):
            for j in range(i + 1, 4):
                for si in [-1, 1]:
                    for sj in [-1, 1]:
                        v = np.zeros(4)
                        v[i] = si
                        v[j] = sj
                        vertices.append(v)

        vertices = np.array(vertices)
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        return vertices / norms

    def batch_nearest_vertices(self, points: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self.kdtree is not None:
            distances, indices = self.kdtree.query(points)
            return indices.astype(np.int32), distances
        else:
            diff = points[:, np.newaxis, :] - self.vertices[np.newaxis, :, :]
            all_distances = np.linalg.norm(diff, axis=2)
            indices = np.argmin(all_distances, axis=1)
            distances = all_distances[np.arange(len(points)), indices]
            return indices.astype(np.int32), distances


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def compute_sphere_packing_bound(n_points: int, dimension: int) -> float:
    """
    Compute theoretical upper bound on minimum distance for N points on unit sphere.

    This is the "Rankin bound" for spherical codes.
    For large N: d_min ≤ 2 * sqrt(1 - (1 - 2/N)^(2/(d-1)))

    Args:
        n_points: Number of points
        dimension: Dimension of the sphere (d for S^(d-1))

    Returns:
        Upper bound on minimum distance
    """
    if n_points <= 1:
        return 2.0

    # Approximate formula for well-separated points
    # Based on covering density arguments
    return 2.0 * np.sqrt(1 - (1 - 2/n_points)**(2/(dimension-1)))


def golden_ratio_verify() -> bool:
    """
    Verify that the 600-cell vertices use correct golden ratio values.

    The identity φ² = φ + 1 should hold, and:
    (1/(2φ))² + (1/2)² + (φ/2)² = 1
    """
    phi = PHI

    # Check φ² = φ + 1
    identity1 = np.isclose(phi**2, phi + 1)

    # Check vertex normalization
    a = 1 / (2 * phi)  # ≈ 0.309
    b = 0.5
    c = phi / 2        # ≈ 0.809
    identity2 = np.isclose(a**2 + b**2 + c**2, 1.0)

    return identity1 and identity2


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GEOMETRY ENGINE - Unit Tests")
    print("=" * 60)

    # Test golden ratio
    print(f"\nGolden ratio verification: {golden_ratio_verify()}")
    print(f"φ = {PHI:.10f}")
    print(f"1/φ = {PHI_INV:.10f}")

    # Test 600-cell
    print("\n" + "-" * 60)
    print("600-Cell Polychoron:")
    p600 = Polychoron600()
    print(p600)

    # Verify geometry
    assert p600.num_vertices == 120, f"Expected 120 vertices, got {p600.num_vertices}"
    assert p600.metrics.kissing_number == 12, f"Expected kissing number 12, got {p600.metrics.kissing_number}"
    assert np.isclose(p600.metrics.min_distance, PHI_INV, atol=1e-6), "Unexpected min distance"

    # Test nearest neighbor
    test_point = np.array([0.9, 0.1, 0.1, 0.1])
    test_point = test_point / np.linalg.norm(test_point)
    idx, dist = p600.nearest_vertex(test_point)
    print(f"\nNearest vertex to {test_point}: index {idx}, distance {dist:.6f}")

    # Test 64-QAM
    print("\n" + "-" * 60)
    print("64-QAM Constellation:")
    qam = QAM64Constellation()
    print(qam)

    # Compare metrics
    print("\n" + "-" * 60)
    print("Comparison:")
    print(f"  POM min_distance: {p600.metrics.min_distance:.6f}")
    print(f"  QAM min_distance: {qam.metrics.min_distance:.6f}")
    print(f"  Ratio (POM/QAM): {p600.metrics.min_distance / qam.metrics.min_distance:.2f}x")

    print("\n✓ All geometry tests passed!")
