"""
Topology Verification

Coordinate-free coverage verification using topological methods.
Based on De Silva & Ghrist's work proving that coverage can be
verified using only connectivity data.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional


@dataclass
class CoverageResult:
    """Result of topology-based coverage verification."""

    covered: bool
    coverage_fraction: float = 0.0
    betti_0: int = 1  # Connected components
    betti_1: int = 0  # Cycles
    betti_2: int = 0  # Voids
    rips_diameter: float = 0.0
    verification_method: str = "rips"

    def to_dict(self) -> Dict:
        return {
            "covered": self.covered,
            "coverage_fraction": self.coverage_fraction,
            "betti": [self.betti_0, self.betti_1, self.betti_2],
            "rips_diameter": self.rips_diameter,
            "method": self.verification_method,
        }


class TopologyVerifier:
    """
    Coordinate-free coverage verification.

    Uses Rips complex construction and homology computation
    to verify coverage without requiring global coordinates.

    Key theorem (De Silva & Ghrist):
    If H₂(Rips, fence) has a generator with non-vanishing
    boundary, then sensor coverage is guaranteed.
    """

    def __init__(self, coverage_radius: float = 1.0):
        """
        Initialize verifier.

        Args:
            coverage_radius: Sensing/coverage radius for each agent
        """
        self.coverage_radius = coverage_radius
        self.agents: Dict[str, np.ndarray] = {}
        self.connectivity: Dict[str, Set[str]] = {}

    def add_agent(self, agent_id: str, position: Optional[np.ndarray] = None) -> None:
        """Add an agent (position optional - can work with connectivity only)."""
        if position is not None:
            self.agents[agent_id] = np.asarray(position)
        else:
            self.agents[agent_id] = None
        self.connectivity[agent_id] = set()

    def set_neighbors(self, agent_id: str, neighbors: List[str]) -> None:
        """Set neighbors for an agent (connectivity-only mode)."""
        self.connectivity[agent_id] = set(neighbors)
        # Make symmetric
        for n in neighbors:
            if n in self.connectivity:
                self.connectivity[n].add(agent_id)

    def compute_connectivity_from_positions(self, radius: Optional[float] = None) -> None:
        """Compute connectivity graph from positions and radius."""
        r = radius or (2 * self.coverage_radius)

        agent_ids = [a for a, p in self.agents.items() if p is not None]

        for i, a1 in enumerate(agent_ids):
            self.connectivity[a1] = set()
            for a2 in agent_ids[i+1:]:
                dist = np.linalg.norm(self.agents[a1] - self.agents[a2])
                if dist <= r:
                    self.connectivity[a1].add(a2)
                    if a2 not in self.connectivity:
                        self.connectivity[a2] = set()
                    self.connectivity[a2].add(a1)

    def build_rips_complex(self, max_dimension: int = 2) -> Dict[int, List[Tuple]]:
        """
        Build Vietoris-Rips complex from connectivity.

        Returns simplices organized by dimension.
        """
        agent_ids = list(self.connectivity.keys())
        n = len(agent_ids)

        simplices = {
            0: [(a,) for a in agent_ids],  # 0-simplices (vertices)
            1: [],  # 1-simplices (edges)
            2: [],  # 2-simplices (triangles)
        }

        # Edges from connectivity
        seen_edges = set()
        for a1, neighbors in self.connectivity.items():
            for a2 in neighbors:
                edge = tuple(sorted([a1, a2]))
                if edge not in seen_edges:
                    seen_edges.add(edge)
                    simplices[1].append(edge)

        if max_dimension >= 2:
            # Triangles: cliques of size 3
            for a1 in agent_ids:
                n1 = self.connectivity.get(a1, set())
                for a2 in n1:
                    if a2 <= a1:
                        continue
                    n2 = self.connectivity.get(a2, set())
                    # Common neighbors form triangles
                    common = n1 & n2
                    for a3 in common:
                        if a3 <= a2:
                            continue
                        triangle = tuple(sorted([a1, a2, a3]))
                        if triangle not in simplices[2]:
                            simplices[2].append(triangle)

        return simplices

    def compute_betti_numbers(self) -> Tuple[int, int, int]:
        """
        Compute Betti numbers from Rips complex.

        β₀ = connected components
        β₁ = independent cycles
        β₂ = independent voids

        Uses Euler characteristic relation:
        χ = V - E + F = β₀ - β₁ + β₂
        """
        simplices = self.build_rips_complex(max_dimension=2)

        v = len(simplices[0])  # Vertices
        e = len(simplices[1])  # Edges
        f = len(simplices[2])  # Faces

        # Connected components via DFS
        visited = set()
        components = 0

        def dfs(agent):
            stack = [agent]
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                stack.extend(self.connectivity.get(current, set()) - visited)

        for agent in self.connectivity:
            if agent not in visited:
                dfs(agent)
                components += 1

        betti_0 = components

        # Euler characteristic
        euler = v - e + f

        # For connected graph: β₁ = E - V + 1
        # For k components: β₁ = E - V + k
        betti_1 = e - v + betti_0

        # β₂ estimation (simplified)
        # In 2D Rips complex, β₂ typically counts enclosed regions
        betti_2 = euler - betti_0 + betti_1

        return max(0, betti_0), max(0, betti_1), max(0, betti_2)

    def verify_coverage(self) -> CoverageResult:
        """
        Verify coverage using topological criteria.

        Coverage is verified if:
        1. Network is connected (β₀ = 1)
        2. Appropriate homology class exists

        For sensor coverage, the key criterion is that the
        Rips complex "fills in" the coverage region.
        """
        b0, b1, b2 = self.compute_betti_numbers()

        # Connected check
        is_connected = (b0 == 1)

        # Coverage heuristic: β₂ > 0 suggests enclosed region
        # This is simplified - full verification requires fence complex
        has_enclosed_region = (b2 > 0) or (b1 == 0 and len(self.agents) >= 3)

        covered = is_connected and has_enclosed_region

        # Estimate coverage fraction from density
        # (very rough approximation)
        if self.agents and all(p is not None for p in self.agents.values()):
            positions = np.array([p for p in self.agents.values() if p is not None])
            if len(positions) > 0:
                # Bounding box
                bbox_min = positions.min(axis=0)
                bbox_max = positions.max(axis=0)
                bbox_vol = np.prod(bbox_max - bbox_min + 1e-10)

                # Coverage volume (crude estimate)
                coverage_vol = len(positions) * (4/3 * np.pi * self.coverage_radius**3)
                coverage_fraction = min(1.0, coverage_vol / bbox_vol)
            else:
                coverage_fraction = 0.0
        else:
            coverage_fraction = 1.0 if covered else 0.0

        return CoverageResult(
            covered=covered,
            coverage_fraction=coverage_fraction,
            betti_0=b0,
            betti_1=b1,
            betti_2=b2,
            rips_diameter=self.coverage_radius * 2,
        )

    def get_connectivity_matrix(self) -> np.ndarray:
        """Get adjacency matrix of connectivity graph."""
        agents = list(self.connectivity.keys())
        n = len(agents)
        idx_map = {a: i for i, a in enumerate(agents)}

        A = np.zeros((n, n))
        for agent, neighbors in self.connectivity.items():
            i = idx_map[agent]
            for neighbor in neighbors:
                j = idx_map.get(neighbor)
                if j is not None:
                    A[i, j] = 1
                    A[j, i] = 1

        return A
