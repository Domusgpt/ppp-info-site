#!/usr/bin/env python3
"""
=============================================================================
COMPREHENSIVE 4D POLYTOPE LIBRARY
=============================================================================

This module implements ALL regular 4D polytopes (polychora) plus useful
semi-regular and compound structures for modulation analysis.

REGULAR CONVEX 4-POLYTOPES (6 total):
=====================================

1. 5-Cell (Pentachoron/4-Simplex)
   - Vertices: 5
   - Cells: 5 tetrahedra
   - Self-dual
   - Bits: 2.32

2. 8-Cell (Tesseract/Hypercube)
   - Vertices: 16
   - Cells: 8 cubes
   - Dual: 16-cell
   - Bits: 4.00

3. 16-Cell (Hexadecachoron/4-Orthoplex)
   - Vertices: 8
   - Cells: 16 tetrahedra
   - Dual: 8-cell
   - Bits: 3.00

4. 24-Cell (Icositetrachoron)
   - Vertices: 24
   - Cells: 24 octahedra
   - Self-dual, unique to 4D
   - Bits: 4.58

5. 120-Cell (Hecatonicosachoron)
   - Vertices: 600
   - Cells: 120 dodecahedra
   - Dual: 600-cell
   - Bits: 9.23

6. 600-Cell (Hexacosichoron)
   - Vertices: 120
   - Cells: 600 tetrahedra
   - Dual: 120-cell
   - Bits: 6.91

ADDITIONAL USEFUL STRUCTURES:
=============================

- Rectified 24-Cell (Rectified Icositetrachoron)
  - 96 vertices, good intermediate density

- Bitruncated 24-Cell
  - 192 vertices

- Snub 24-Cell
  - 96 vertices, chiral

- D4 Lattice Points (densest 4D packing)
  - Configurable density

- E8 Root System (projected to 4D)
  - 240 vertices in 8D, various 4D projections

Author: PPP Research Team
License: MIT
=============================================================================
"""

import numpy as np
from scipy.spatial import KDTree
from typing import Tuple, Optional, List, Dict
from dataclasses import dataclass
from itertools import permutations, combinations
from abc import ABC, abstractmethod


# =============================================================================
# CONSTANTS
# =============================================================================

PHI = (1 + np.sqrt(5)) / 2  # Golden ratio ≈ 1.618
PHI_INV = PHI - 1           # 1/φ ≈ 0.618
SQRT2 = np.sqrt(2)
SQRT5 = np.sqrt(5)


# =============================================================================
# BASE CLASS
# =============================================================================

@dataclass
class PolytopeMetrics:
    """Container for polytope metrics."""
    name: str
    num_vertices: int
    bits_per_symbol: float
    usable_bits: int
    min_distance: float
    avg_distance: float
    kissing_number: int
    dimensionality: int
    is_regular: bool
    dual_name: Optional[str] = None


class Polytope4D(ABC):
    """Abstract base class for all 4D polytopes."""

    def __init__(self, name: str, use_kdtree: bool = True):
        self.name = name
        self.vertices = self._generate_vertices()
        self.num_vertices = len(self.vertices)
        self.dimensionality = 4
        self.kdtree = KDTree(self.vertices) if use_kdtree else None
        self._metrics = None

    @abstractmethod
    def _generate_vertices(self) -> np.ndarray:
        """Generate vertices. Must return normalized unit vectors."""
        pass

    @property
    def metrics(self) -> PolytopeMetrics:
        if self._metrics is None:
            self._metrics = self._compute_metrics()
        return self._metrics

    def _compute_metrics(self) -> PolytopeMetrics:
        """Compute polytope metrics."""
        n = self.num_vertices

        if n < 2:
            return PolytopeMetrics(
                name=self.name, num_vertices=n, bits_per_symbol=0,
                usable_bits=0, min_distance=0, avg_distance=0,
                kissing_number=0, dimensionality=4, is_regular=True
            )

        # Compute pairwise distances
        diff = self.vertices[:, np.newaxis, :] - self.vertices[np.newaxis, :, :]
        distances = np.linalg.norm(diff, axis=2)
        np.fill_diagonal(distances, np.inf)

        min_dist = np.min(distances)
        avg_dist = np.mean(distances[distances != np.inf])

        # Kissing number
        threshold = min_dist * 1.01
        kissing = int(np.median([np.sum(distances[i] < threshold) for i in range(n)]))

        return PolytopeMetrics(
            name=self.name,
            num_vertices=n,
            bits_per_symbol=np.log2(n) if n > 0 else 0,
            usable_bits=int(np.floor(np.log2(n))) if n > 0 else 0,
            min_distance=min_dist,
            avg_distance=avg_dist,
            kissing_number=kissing,
            dimensionality=4,
            is_regular=True,
            dual_name=getattr(self, 'dual_name', None)
        )

    def nearest_vertex(self, point: np.ndarray) -> Tuple[int, float]:
        """Find nearest vertex to a point."""
        if self.kdtree is not None:
            dist, idx = self.kdtree.query(point)
            return int(idx), float(dist)
        distances = np.linalg.norm(self.vertices - point, axis=1)
        idx = np.argmin(distances)
        return int(idx), float(distances[idx])

    def batch_nearest(self, points: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Batch nearest-vertex lookup."""
        if self.kdtree is not None:
            distances, indices = self.kdtree.query(points)
            return indices.astype(np.int32), distances
        diff = points[:, np.newaxis, :] - self.vertices[np.newaxis, :, :]
        all_dist = np.linalg.norm(diff, axis=2)
        indices = np.argmin(all_dist, axis=1)
        distances = all_dist[np.arange(len(points)), indices]
        return indices.astype(np.int32), distances

    def __repr__(self) -> str:
        m = self.metrics
        return (f"{self.name}(vertices={m.num_vertices}, "
                f"bits={m.bits_per_symbol:.2f}, d_min={m.min_distance:.4f}, "
                f"kissing={m.kissing_number})")


# =============================================================================
# REGULAR POLYCHORA
# =============================================================================

class Pentachoron(Polytope4D):
    """
    5-Cell (Pentachoron) - The 4D simplex.

    - 5 vertices, 10 edges, 10 triangular faces, 5 tetrahedral cells
    - Self-dual
    - Smallest regular 4-polytope
    - Vertices form a regular tetrahedron in 3D projection
    """
    dual_name = "Pentachoron"

    def __init__(self, use_kdtree: bool = True):
        super().__init__("5-Cell (Pentachoron)", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        # Standard embedding: vertices of 4-simplex
        # One vertex at (1,1,1,-1/√5)/r, etc.
        vertices = []

        # First 4 vertices: standard basis shifted
        for i in range(4):
            v = np.zeros(4)
            v[i] = 1
            vertices.append(v)

        # 5th vertex: equal contribution from all
        vertices.append(np.array([-1, -1, -1, -1]) / 2)

        vertices = np.array(vertices)

        # Center at origin
        center = np.mean(vertices, axis=0)
        vertices = vertices - center

        # Normalize
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        return vertices / norms


class Tesseract(Polytope4D):
    """
    8-Cell (Tesseract/Hypercube) - The 4D cube.

    - 16 vertices, 32 edges, 24 square faces, 8 cubic cells
    - Dual: 16-cell
    - Vertices are all combinations of (±1, ±1, ±1, ±1)
    """
    dual_name = "16-Cell"

    def __init__(self, use_kdtree: bool = True):
        super().__init__("8-Cell (Tesseract)", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        vertices = []
        for s0 in [-1, 1]:
            for s1 in [-1, 1]:
                for s2 in [-1, 1]:
                    for s3 in [-1, 1]:
                        vertices.append([s0, s1, s2, s3])

        vertices = np.array(vertices, dtype=np.float64)
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        return vertices / norms


class Hexadecachoron(Polytope4D):
    """
    16-Cell (Hexadecachoron/4-Orthoplex) - The 4D cross-polytope.

    - 8 vertices, 24 edges, 32 triangular faces, 16 tetrahedral cells
    - Dual: Tesseract
    - Vertices are permutations of (±1, 0, 0, 0)
    """
    dual_name = "Tesseract"

    def __init__(self, use_kdtree: bool = True):
        super().__init__("16-Cell (Hexadecachoron)", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        vertices = []
        for axis in range(4):
            for sign in [-1, 1]:
                v = np.zeros(4)
                v[axis] = sign
                vertices.append(v)
        return np.array(vertices)


class Icositetrachoron(Polytope4D):
    """
    24-Cell (Icositetrachoron) - Unique to 4D, self-dual.

    - 24 vertices, 96 edges, 96 triangular faces, 24 octahedral cells
    - Self-dual (no analog in other dimensions)
    - Vertices are permutations of (±1, ±1, 0, 0)
    - Kissing number: 8
    """
    dual_name = "24-Cell"

    def __init__(self, use_kdtree: bool = True):
        super().__init__("24-Cell (Icositetrachoron)", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        vertices = []
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


class Hexacosichoron(Polytope4D):
    """
    600-Cell (Hexacosichoron) - The most vertices among regular polychora.

    - 120 vertices, 720 edges, 1200 triangular faces, 600 tetrahedral cells
    - Dual: 120-cell
    - Based on icosahedral symmetry and golden ratio
    - Kissing number: 12
    """
    dual_name = "120-Cell"

    def __init__(self, use_kdtree: bool = True):
        super().__init__("600-Cell (Hexacosichoron)", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        vertices = []

        # Family 1: 8 vertices - (±1, 0, 0, 0) permutations
        for axis in range(4):
            for sign in [-1.0, 1.0]:
                v = np.zeros(4)
                v[axis] = sign
                vertices.append(v)

        # Family 2: 16 vertices - (±1/2, ±1/2, ±1/2, ±1/2)
        for s0 in [-0.5, 0.5]:
            for s1 in [-0.5, 0.5]:
                for s2 in [-0.5, 0.5]:
                    for s3 in [-0.5, 0.5]:
                        vertices.append(np.array([s0, s1, s2, s3]))

        # Family 3: 96 vertices - even permutations of (0, ±1/(2φ), ±1/2, ±φ/2)
        half = 0.5
        half_phi = PHI / 2
        half_phi_inv = PHI_INV / 2

        base_values = [0.0, half_phi_inv, half, half_phi]

        even_perms = [
            [0, 1, 2, 3], [0, 2, 3, 1], [0, 3, 1, 2],
            [1, 0, 3, 2], [1, 2, 0, 3], [1, 3, 2, 0],
            [2, 0, 1, 3], [2, 1, 3, 0], [2, 3, 0, 1],
            [3, 0, 2, 1], [3, 1, 0, 2], [3, 2, 1, 0]
        ]

        for perm in even_perms:
            permuted = [base_values[perm[i]] for i in range(4)]
            for s0 in [-1, 1]:
                for s1 in [-1, 1]:
                    for s2 in [-1, 1]:
                        for s3 in [-1, 1]:
                            v = np.array([
                                s0 * permuted[0], s1 * permuted[1],
                                s2 * permuted[2], s3 * permuted[3]
                            ])
                            vertices.append(v)

        vertices = np.array(vertices)
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        vertices = vertices / norms

        # Remove duplicates
        vertices = np.unique(np.round(vertices, decimals=12), axis=0)
        return vertices


class Hecatonicosachoron(Polytope4D):
    """
    120-Cell (Hecatonicosachoron) - The largest regular polychoron.

    - 600 vertices, 1200 edges, 720 pentagonal faces, 120 dodecahedral cells
    - Dual: 600-cell
    - Most vertices among regular 4-polytopes
    - Extremely dense constellation
    """
    dual_name = "600-Cell"

    def __init__(self, use_kdtree: bool = True):
        super().__init__("120-Cell (Hecatonicosachoron)", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        """
        Generate 600 vertices of the 120-cell.

        The vertices can be constructed from 8 groups based on golden ratio.
        """
        vertices = []

        phi = PHI
        phi2 = phi * phi
        phi3 = phi2 * phi

        # All permutations and sign changes of:
        # (0, 0, ±2, ±2)
        # (±1, ±1, ±1, ±√5)
        # (±φ^-2, ±φ, ±φ, ±φ)
        # (±φ^-1, ±φ^-1, ±φ^-1, ±φ^2)
        # (0, ±φ^-2, ±1, ±φ^2)
        # (0, ±φ^-1, ±φ, ±√5)
        # (±φ^-1, ±1, ±φ, ±2)

        def add_all_signs(coords_list, vertices_list):
            """Add all sign combinations for each coordinate tuple."""
            for coords in coords_list:
                for s0 in [-1, 1]:
                    for s1 in [-1, 1]:
                        for s2 in [-1, 1]:
                            for s3 in [-1, 1]:
                                v = np.array([s0*coords[0], s1*coords[1],
                                             s2*coords[2], s3*coords[3]])
                                vertices_list.append(v)

        def add_all_perms_and_signs(base, vertices_list):
            """Add all permutations and sign combinations."""
            seen = set()
            for perm in permutations(range(4)):
                coords = tuple(base[i] for i in perm)
                for s0 in [-1, 1]:
                    for s1 in [-1, 1]:
                        for s2 in [-1, 1]:
                            for s3 in [-1, 1]:
                                v = (s0*coords[0], s1*coords[1],
                                     s2*coords[2], s3*coords[3])
                                v_rounded = tuple(round(x, 10) for x in v)
                                if v_rounded not in seen:
                                    seen.add(v_rounded)
                                    vertices_list.append(np.array(v))

        # Group 1: (0, 0, 2, 2)
        add_all_perms_and_signs([0, 0, 2, 2], vertices)

        # Group 2: (1, 1, 1, √5)
        add_all_perms_and_signs([1, 1, 1, SQRT5], vertices)

        # Group 3: (φ^-2, φ, φ, φ)
        add_all_perms_and_signs([1/phi2, phi, phi, phi], vertices)

        # Group 4: (φ^-1, φ^-1, φ^-1, φ^2)
        add_all_perms_and_signs([1/phi, 1/phi, 1/phi, phi2], vertices)

        # Group 5: (0, φ^-2, 1, φ^2)
        add_all_perms_and_signs([0, 1/phi2, 1, phi2], vertices)

        # Group 6: (0, φ^-1, φ, √5)
        add_all_perms_and_signs([0, 1/phi, phi, SQRT5], vertices)

        # Group 7: (φ^-1, 1, φ, 2)
        add_all_perms_and_signs([1/phi, 1, phi, 2], vertices)

        vertices = np.array(vertices)

        # Normalize to unit sphere
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        vertices = vertices / norms

        # Remove duplicates
        vertices = np.unique(np.round(vertices, decimals=10), axis=0)

        return vertices


# =============================================================================
# SEMI-REGULAR AND COMPOUND POLYTOPES
# =============================================================================

class RectifiedTesseract(Polytope4D):
    """
    Rectified Tesseract - A semi-regular 4-polytope.

    - 32 vertices (midpoints of tesseract edges)
    - Good intermediate density between 24-cell and 600-cell
    """

    def __init__(self, use_kdtree: bool = True):
        super().__init__("Rectified Tesseract", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        # Vertices are permutations of (0, ±1, ±1, ±1)
        vertices = []

        for zero_pos in range(4):
            for s1 in [-1, 1]:
                for s2 in [-1, 1]:
                    for s3 in [-1, 1]:
                        v = [s1, s2, s3]
                        v.insert(zero_pos, 0)
                        vertices.append(v)

        vertices = np.array(vertices, dtype=np.float64)
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        return vertices / norms


class Rectified24Cell(Polytope4D):
    """
    Rectified 24-Cell - 48 vertices.

    Vertices are midpoints of 24-cell edges.
    """

    def __init__(self, use_kdtree: bool = True):
        super().__init__("Rectified 24-Cell", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        # Vertices are permutations of (0, ±1, ±1, ±2)/2
        vertices = []

        base_coords = [0, 1, 1, 2]

        for perm in permutations(range(4)):
            coords = [base_coords[perm[i]] for i in range(4)]
            for s1 in [-1, 1]:
                for s2 in [-1, 1]:
                    for s3 in [-1, 1]:
                        v = [coords[0], s1*coords[1], s2*coords[2], s3*coords[3]]
                        # Skip if first non-zero is negative (avoid duplicates)
                        if coords[0] == 0:
                            vertices.append(v)

        vertices = np.array(vertices, dtype=np.float64) / 2
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        vertices = vertices / norms

        # Remove duplicates
        vertices = np.unique(np.round(vertices, decimals=12), axis=0)
        return vertices


class Snub24Cell(Polytope4D):
    """
    Snub 24-Cell - A chiral semi-regular 4-polytope.

    - 96 vertices
    - Combines 24-cell with icosahedral symmetry
    - Has no mirror image - exists in left and right forms
    """

    def __init__(self, use_kdtree: bool = True, chirality: str = 'left'):
        self.chirality = chirality
        super().__init__(f"Snub 24-Cell ({chirality})", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        # The snub 24-cell vertices include the 24-cell plus additional
        # vertices based on even permutations of (φ, 1, 1/φ, 0)

        vertices = []

        # 24-cell vertices (24 total)
        for i in range(4):
            for j in range(i + 1, 4):
                for si in [-1, 1]:
                    for sj in [-1, 1]:
                        v = np.zeros(4)
                        v[i] = si
                        v[j] = sj
                        vertices.append(v)

        # Additional snub vertices (96 - 24 = 72 additional)
        phi = PHI
        base = [phi, 1, 1/phi, 0]

        # Even permutations only (for chirality)
        even_perms = [
            [0, 1, 2, 3], [0, 2, 3, 1], [0, 3, 1, 2],
            [1, 0, 3, 2], [1, 2, 0, 3], [1, 3, 2, 0],
            [2, 0, 1, 3], [2, 1, 3, 0], [2, 3, 0, 1],
            [3, 0, 2, 1], [3, 1, 0, 2], [3, 2, 1, 0]
        ]

        for perm in even_perms:
            coords = [base[perm[i]] for i in range(4)]
            for s0 in [-1, 1]:
                for s1 in [-1, 1]:
                    for s2 in [-1, 1]:
                        v = [s0*coords[0], s1*coords[1], s2*coords[2], coords[3]]
                        vertices.append(v)

        vertices = np.array(vertices, dtype=np.float64)
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        vertices = vertices / norms

        # Remove duplicates
        vertices = np.unique(np.round(vertices, decimals=12), axis=0)
        return vertices


class GrandAntiprism(Polytope4D):
    """
    Grand Antiprism - A uniform 4-polytope with 100 vertices.

    - Not regular but highly symmetric
    - Contains antiprism-like structures
    - 100 vertices provide ~6.64 bits
    """

    def __init__(self, use_kdtree: bool = True):
        super().__init__("Grand Antiprism", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        # Grand antiprism vertices are based on two interlocking
        # pentagonal antiprism rings in 4D

        vertices = []
        n = 10  # Number of vertices per ring

        # Two rings of 50 vertices each
        for ring in range(2):
            phase = ring * np.pi / n
            for k in range(n):
                for layer in range(5):
                    theta = 2 * np.pi * k / n + phase
                    z = (layer - 2) / 2
                    r = np.sqrt(1 - z*z) if abs(z) < 1 else 0

                    if ring == 0:
                        v = [r * np.cos(theta), r * np.sin(theta), z, 0]
                    else:
                        v = [0, z, r * np.cos(theta), r * np.sin(theta)]
                    vertices.append(v)

        vertices = np.array(vertices, dtype=np.float64)
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vertices = vertices / norms

        # Remove duplicates and near-zero vertices
        vertices = vertices[np.linalg.norm(vertices, axis=1) > 0.1]
        vertices = np.unique(np.round(vertices, decimals=10), axis=0)

        return vertices


# =============================================================================
# LATTICE-BASED STRUCTURES
# =============================================================================

class D4Lattice(Polytope4D):
    """
    D4 Lattice Points - The densest 4D sphere packing.

    The D4 lattice achieves the densest known sphere packing in 4D.
    Points are integer coordinates summing to an even number.

    radius parameter controls how many shells to include.
    """

    def __init__(self, radius: int = 2, use_kdtree: bool = True):
        self.radius = radius
        super().__init__(f"D4 Lattice (r={radius})", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        vertices = []
        r = self.radius

        for x0 in range(-r, r + 1):
            for x1 in range(-r, r + 1):
                for x2 in range(-r, r + 1):
                    for x3 in range(-r, r + 1):
                        # D4 condition: sum must be even
                        if (x0 + x1 + x2 + x3) % 2 == 0:
                            if x0 != 0 or x1 != 0 or x2 != 0 or x3 != 0:
                                vertices.append([x0, x1, x2, x3])

        vertices = np.array(vertices, dtype=np.float64)

        # Normalize to unit sphere
        norms = np.linalg.norm(vertices, axis=1, keepdims=True)
        vertices = vertices / norms

        # Remove duplicates (points that normalize to same direction)
        vertices = np.unique(np.round(vertices, decimals=10), axis=0)

        return vertices


class E8Projection(Polytope4D):
    """
    E8 Root System Projected to 4D.

    The E8 lattice is the densest sphere packing in 8D.
    Various projections to 4D give useful constellations.

    The 240 root vectors of E8 can be projected to 4D in multiple ways.
    """

    def __init__(self, projection: str = 'standard', use_kdtree: bool = True):
        self.projection = projection
        super().__init__(f"E8 Projection ({projection})", use_kdtree)

    def _generate_e8_roots(self) -> np.ndarray:
        """Generate the 240 root vectors of E8 in 8D."""
        roots = []

        # Type 1: all permutations of (±1, ±1, 0, 0, 0, 0, 0, 0) - 112 roots
        for i in range(8):
            for j in range(i + 1, 8):
                for si in [-1, 1]:
                    for sj in [-1, 1]:
                        v = np.zeros(8)
                        v[i] = si
                        v[j] = sj
                        roots.append(v)

        # Type 2: (±1/2, ±1/2, ...) with even number of minus signs - 128 roots
        for num_neg in [0, 2, 4, 6, 8]:
            for neg_positions in combinations(range(8), num_neg):
                v = np.ones(8) * 0.5
                for pos in neg_positions:
                    v[pos] = -0.5
                roots.append(v)

        return np.array(roots)

    def _generate_vertices(self) -> np.ndarray:
        roots_8d = self._generate_e8_roots()

        if self.projection == 'standard':
            # Simple projection: take first 4 coordinates
            vertices = roots_8d[:, :4]
        elif self.projection == 'symmetric':
            # Symmetric projection preserving more structure
            # Use a rotation that respects E8 symmetry
            proj = np.array([
                [1, 0, 0, 0, 1, 0, 0, 0],
                [0, 1, 0, 0, 0, 1, 0, 0],
                [0, 0, 1, 0, 0, 0, 1, 0],
                [0, 0, 0, 1, 0, 0, 0, 1]
            ]) / np.sqrt(2)
            vertices = roots_8d @ proj.T
        else:
            # Golden ratio projection
            phi = PHI
            proj = np.array([
                [1, phi, 0, 0, 0, 0, 0, 0],
                [0, 0, 1, phi, 0, 0, 0, 0],
                [0, 0, 0, 0, 1, phi, 0, 0],
                [0, 0, 0, 0, 0, 0, 1, phi]
            ]) / np.sqrt(1 + phi*phi)
            vertices = roots_8d @ proj.T

        # Remove zero-norm vertices before normalizing
        norms = np.linalg.norm(vertices, axis=1)
        vertices = vertices[norms > 1e-10]
        norms = norms[norms > 1e-10]

        # Normalize
        vertices = vertices / norms[:, np.newaxis]

        # Remove duplicates
        vertices = np.unique(np.round(vertices, decimals=10), axis=0)

        return vertices


# =============================================================================
# QAM CONSTELLATIONS FOR COMPARISON
# =============================================================================

class QAM(Polytope4D):
    """
    Standard M-QAM constellation embedded in 4D.

    For fair comparison, we embed 2D QAM in 4D space.
    """

    def __init__(self, m: int = 64, use_kdtree: bool = True):
        self.m = m
        self.size = int(np.sqrt(m))
        assert self.size ** 2 == m, "M must be a perfect square"
        super().__init__(f"{m}-QAM", use_kdtree)

    def _generate_vertices(self) -> np.ndarray:
        # Generate M-QAM grid
        levels = np.arange(self.size) - (self.size - 1) / 2
        levels = levels * 2  # Standard spacing

        symbols = []
        for i in levels:
            for q in levels:
                symbols.append([i, q, 0, 0])  # Embed in 4D

        symbols = np.array(symbols, dtype=np.float64)

        # Normalize to unit average power
        power_2d = symbols[:, 0]**2 + symbols[:, 1]**2
        avg_power = np.mean(power_2d)
        symbols = symbols / np.sqrt(avg_power)

        return symbols

    @property
    def symbols_2d(self) -> np.ndarray:
        """Return 2D symbols for 2D channel simulation."""
        return self.vertices[:, :2]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_all_regular_polychora() -> Dict[str, Polytope4D]:
    """Get all 6 regular 4-polytopes."""
    return {
        '5-cell': Pentachoron(),
        '8-cell': Tesseract(),
        '16-cell': Hexadecachoron(),
        '24-cell': Icositetrachoron(),
        '120-cell': Hecatonicosachoron(),
        '600-cell': Hexacosichoron(),
    }


def get_all_polytopes() -> Dict[str, Polytope4D]:
    """Get all implemented polytopes."""
    polytopes = get_all_regular_polychora()

    # Add semi-regular
    polytopes['rectified-tesseract'] = RectifiedTesseract()
    polytopes['rectified-24-cell'] = Rectified24Cell()
    polytopes['snub-24-cell'] = Snub24Cell()

    # Add lattice-based
    polytopes['d4-lattice'] = D4Lattice(radius=2)
    polytopes['e8-projection'] = E8Projection(projection='standard')

    # Add QAM for comparison
    for m in [16, 64, 256]:
        polytopes[f'{m}-qam'] = QAM(m=m)

    return polytopes


def compare_polytopes(polytopes: Optional[Dict[str, Polytope4D]] = None) -> None:
    """Print comparison table of all polytopes."""
    if polytopes is None:
        polytopes = get_all_polytopes()

    print("\n" + "=" * 90)
    print("4D POLYTOPE COMPARISON")
    print("=" * 90)
    print(f"{'Name':<30} {'Vertices':>10} {'Bits':>8} {'d_min':>10} {'Kissing':>10}")
    print("-" * 90)

    # Sort by number of vertices
    sorted_items = sorted(polytopes.items(), key=lambda x: x[1].num_vertices)

    for name, poly in sorted_items:
        m = poly.metrics
        print(f"{m.name:<30} {m.num_vertices:>10} {m.bits_per_symbol:>8.2f} "
              f"{m.min_distance:>10.4f} {m.kissing_number:>10}")

    print("=" * 90)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Generating all 4D polytopes...")

    polytopes = get_all_polytopes()
    compare_polytopes(polytopes)

    # Verify vertex counts for regular polychora
    print("\nVerifying regular polychora:")
    expected = {
        '5-cell': 5,
        '8-cell': 16,
        '16-cell': 8,
        '24-cell': 24,
        '120-cell': 600,
        '600-cell': 120,
    }

    for name, expected_n in expected.items():
        actual_n = polytopes[name].num_vertices
        status = "✓" if actual_n == expected_n else f"✗ (got {actual_n})"
        print(f"  {name}: {status}")
