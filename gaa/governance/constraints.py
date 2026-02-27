"""
Geometric Constraints

Defines manifold regions and polytope constraints for governance.
Agents must operate within permitted geometric boundaries.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class RegionType(Enum):
    """Types of manifold regions."""

    SPHERICAL = "spherical"      # Ball in quaternion space
    POLYTOPE = "polytope"        # Convex polytope
    CONE = "cone"                # Conical region
    VORONOI = "voronoi"          # Voronoi cell around vertex
    GEODESIC = "geodesic"        # Geodesic neighborhood


@dataclass
class ManifoldRegion:
    """
    Defines a permitted region on the geometric manifold.

    Agents constrained to this region can only produce
    states within its boundaries.
    """

    region_id: str
    region_type: RegionType
    name: str = ""
    description: str = ""

    # Center point (for spherical/Voronoi)
    center: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0]))

    # Radius (for spherical/geodesic)
    radius: float = 0.5

    # Vertices (for polytope)
    vertices: List[np.ndarray] = field(default_factory=list)

    # Normal vectors (for half-space intersection)
    normals: List[np.ndarray] = field(default_factory=list)
    offsets: List[float] = field(default_factory=list)

    def contains_point(self, point: np.ndarray) -> bool:
        """Check if point lies within region."""
        point = np.asarray(point, dtype=np.float64)

        if self.region_type == RegionType.SPHERICAL:
            return self._contains_spherical(point)
        elif self.region_type == RegionType.GEODESIC:
            return self._contains_geodesic(point)
        elif self.region_type == RegionType.POLYTOPE:
            return self._contains_polytope(point)
        elif self.region_type == RegionType.VORONOI:
            return self._contains_voronoi(point)
        elif self.region_type == RegionType.CONE:
            return self._contains_cone(point)
        else:
            return True

    def _contains_spherical(self, point: np.ndarray) -> bool:
        """Check containment in spherical region."""
        distance = np.linalg.norm(point - self.center)
        return distance <= self.radius

    def _contains_geodesic(self, point: np.ndarray) -> bool:
        """Check containment in geodesic neighborhood."""
        # Normalize for angular distance
        p_norm = point / np.linalg.norm(point)
        c_norm = self.center / np.linalg.norm(self.center)

        # Angular distance
        dot = np.clip(np.dot(p_norm, c_norm), -1.0, 1.0)
        angle = np.arccos(abs(dot))

        return angle <= self.radius

    def _contains_polytope(self, point: np.ndarray) -> bool:
        """Check containment in convex polytope (half-space intersection)."""
        if not self.normals or not self.offsets:
            return True

        for normal, offset in zip(self.normals, self.offsets):
            normal = np.asarray(normal)
            if np.dot(normal, point) > offset:
                return False
        return True

    def _contains_voronoi(self, point: np.ndarray) -> bool:
        """Check if point is in Voronoi cell of center."""
        # Point must be closer to center than to any vertex
        p_norm = point / np.linalg.norm(point)
        c_norm = self.center / np.linalg.norm(self.center)

        center_dist = np.linalg.norm(p_norm - c_norm)

        for vertex in self.vertices:
            v_norm = vertex / np.linalg.norm(vertex)
            vertex_dist = np.linalg.norm(p_norm - v_norm)
            if vertex_dist < center_dist:
                return False

        return True

    def _contains_cone(self, point: np.ndarray) -> bool:
        """Check containment in conical region."""
        # Cone defined by center (apex direction) and radius (half-angle)
        p_norm = point / np.linalg.norm(point)
        c_norm = self.center / np.linalg.norm(self.center)

        dot = np.dot(p_norm, c_norm)
        return dot >= np.cos(self.radius)

    def distance_to_boundary(self, point: np.ndarray) -> float:
        """Compute distance from point to region boundary."""
        point = np.asarray(point, dtype=np.float64)

        if self.region_type == RegionType.SPHERICAL:
            dist = np.linalg.norm(point - self.center)
            return abs(self.radius - dist)
        elif self.region_type == RegionType.GEODESIC:
            p_norm = point / np.linalg.norm(point)
            c_norm = self.center / np.linalg.norm(self.center)
            angle = np.arccos(np.clip(abs(np.dot(p_norm, c_norm)), -1, 1))
            return abs(self.radius - angle)
        else:
            return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "region_id": self.region_id,
            "region_type": self.region_type.value,
            "name": self.name,
            "description": self.description,
            "center": self.center.tolist(),
            "radius": self.radius,
            "vertices": [v.tolist() for v in self.vertices],
            "normals": [n.tolist() for n in self.normals],
            "offsets": self.offsets,
        }


@dataclass
class GeometricConstraint:
    """
    Collection of geometric constraints for governance.

    Combines multiple manifold regions and provides
    unified containment checking.
    """

    constraint_id: str
    name: str = ""
    description: str = ""

    # Permitted regions (OR semantics - point must be in at least one)
    permitted_regions: List[ManifoldRegion] = field(default_factory=list)

    # Forbidden regions (point must not be in any)
    forbidden_regions: List[ManifoldRegion] = field(default_factory=list)

    # Coherence bounds
    min_coherence: float = 0.0
    max_coherence: float = 1.0

    # Angular velocity limit
    max_angular_velocity: float = float('inf')

    def is_satisfied(
        self,
        point: np.ndarray,
        coherence: float = 1.0,
        angular_velocity: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Check if state satisfies all constraints.

        Returns (satisfied, reason) tuple.
        """
        point = np.asarray(point, dtype=np.float64)

        # Check coherence bounds
        if coherence < self.min_coherence:
            return False, f"Coherence {coherence} below minimum {self.min_coherence}"
        if coherence > self.max_coherence:
            return False, f"Coherence {coherence} above maximum {self.max_coherence}"

        # Check angular velocity
        if angular_velocity > self.max_angular_velocity:
            return False, f"Angular velocity {angular_velocity} exceeds limit {self.max_angular_velocity}"

        # Check forbidden regions
        for region in self.forbidden_regions:
            if region.contains_point(point):
                return False, f"Point in forbidden region '{region.name}'"

        # Check permitted regions (if any defined)
        if self.permitted_regions:
            in_permitted = any(r.contains_point(point) for r in self.permitted_regions)
            if not in_permitted:
                return False, "Point not in any permitted region"

        return True, "All constraints satisfied"

    def add_permitted_region(self, region: ManifoldRegion) -> None:
        """Add a permitted region."""
        self.permitted_regions.append(region)

    def add_forbidden_region(self, region: ManifoldRegion) -> None:
        """Add a forbidden region."""
        self.forbidden_regions.append(region)

    def add_600_cell_constraint(self, vertex_indices: List[int]) -> None:
        """
        Add constraint limiting to specific 600-cell vertices.

        Creates Voronoi regions around specified vertices.
        """
        from ..foundational.quaternion import Quaternion

        # 600-cell vertices (simplified - would need full construction)
        phi = (1 + np.sqrt(5)) / 2

        # Add Voronoi regions for specified indices
        for idx in vertex_indices:
            # Generate vertex (simplified)
            angle = idx * 2 * np.pi / 120
            vertex = np.array([
                np.cos(angle),
                np.sin(angle) * 0.5,
                np.sin(angle) * 0.5,
                np.sin(angle) * 0.5,
            ])
            vertex = vertex / np.linalg.norm(vertex)

            region = ManifoldRegion(
                region_id=f"600cell_v{idx}",
                region_type=RegionType.VORONOI,
                name=f"600-cell vertex {idx}",
                center=vertex,
            )
            self.add_permitted_region(region)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "constraint_id": self.constraint_id,
            "name": self.name,
            "description": self.description,
            "permitted_regions": [r.to_dict() for r in self.permitted_regions],
            "forbidden_regions": [r.to_dict() for r in self.forbidden_regions],
            "min_coherence": self.min_coherence,
            "max_coherence": self.max_coherence,
            "max_angular_velocity": self.max_angular_velocity,
        }
