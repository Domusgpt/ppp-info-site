"""
Swarm Analyzer

Persistence landscape analysis of swarm geometric state.
Enables behavior classification (flock, torus, disordered)
from topological features alone.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum


class SwarmBehavior(Enum):
    """Classified swarm behavior types."""

    FLOCK = "flock"       # Aligned, cohesive group
    TORUS = "torus"       # Circular/ring formation
    DISORDERED = "disordered"  # Random, uncorrelated
    CLUSTER = "cluster"   # Multiple distinct groups
    UNKNOWN = "unknown"


@dataclass
class SwarmMetrics:
    """Metrics describing swarm state."""

    # Population
    agent_count: int = 0

    # Spatial metrics
    centroid: np.ndarray = field(default_factory=lambda: np.zeros(3))
    spread: float = 0.0  # Standard deviation from centroid
    diameter: float = 0.0  # Maximum pairwise distance

    # Orientation metrics
    polarization: float = 0.0  # Alignment of headings [0, 1]
    angular_momentum: float = 0.0  # Collective rotation

    # Topological metrics
    persistence_entropy: float = 0.0
    betti_sequence: Tuple[int, int, int] = (1, 0, 0)

    # Classification
    behavior: SwarmBehavior = SwarmBehavior.UNKNOWN
    behavior_confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "agent_count": self.agent_count,
            "centroid": self.centroid.tolist(),
            "spread": self.spread,
            "diameter": self.diameter,
            "polarization": self.polarization,
            "angular_momentum": self.angular_momentum,
            "persistence_entropy": self.persistence_entropy,
            "betti": self.betti_sequence,
            "behavior": self.behavior.value,
            "behavior_confidence": self.behavior_confidence,
        }


class SwarmAnalyzer:
    """
    Analyzes swarm state using geometric and topological methods.

    Computes metrics for behavior classification without
    requiring individual agent tracking.
    """

    def __init__(self, position_dim: int = 3):
        """
        Initialize analyzer.

        Args:
            position_dim: Dimensionality of position space
        """
        self.position_dim = position_dim
        self.positions: List[np.ndarray] = []
        self.velocities: List[np.ndarray] = []
        self.quaternions: List[np.ndarray] = []

    def set_agents(
        self,
        positions: List[np.ndarray],
        velocities: Optional[List[np.ndarray]] = None,
        quaternions: Optional[List[np.ndarray]] = None
    ) -> None:
        """Set agent state data."""
        self.positions = [np.asarray(p) for p in positions]
        self.velocities = [np.asarray(v) for v in velocities] if velocities else []
        self.quaternions = [np.asarray(q) for q in quaternions] if quaternions else []

    def compute_spatial_metrics(self) -> Dict[str, float]:
        """Compute spatial distribution metrics."""
        if not self.positions:
            return {"centroid": np.zeros(self.position_dim), "spread": 0, "diameter": 0}

        positions = np.array(self.positions)
        centroid = positions.mean(axis=0)

        # Spread (std dev from centroid)
        distances_to_center = np.linalg.norm(positions - centroid, axis=1)
        spread = np.std(distances_to_center)

        # Diameter (max pairwise distance)
        diameter = 0.0
        n = len(positions)
        for i in range(n):
            for j in range(i+1, n):
                d = np.linalg.norm(positions[i] - positions[j])
                diameter = max(diameter, d)

        return {
            "centroid": centroid,
            "spread": spread,
            "diameter": diameter,
        }

    def compute_polarization(self) -> float:
        """
        Compute polarization (alignment) of swarm.

        Polarization = |mean velocity direction|
        1.0 = all aligned, 0.0 = random orientations
        """
        if not self.velocities:
            return 0.0

        # Normalize velocities
        normalized = []
        for v in self.velocities:
            norm = np.linalg.norm(v)
            if norm > 1e-10:
                normalized.append(v / norm)

        if not normalized:
            return 0.0

        mean_dir = np.mean(normalized, axis=0)
        return np.linalg.norm(mean_dir)

    def compute_angular_momentum(self) -> float:
        """
        Compute normalized angular momentum about centroid.

        High angular momentum indicates torus/milling behavior.
        """
        if not self.positions or not self.velocities:
            return 0.0

        positions = np.array(self.positions)
        velocities = np.array(self.velocities)
        centroid = positions.mean(axis=0)

        # Relative positions
        rel_pos = positions - centroid

        # Angular momentum: L = Σ r × v
        if self.position_dim >= 3:
            L = np.zeros(3)
            for r, v in zip(rel_pos, velocities):
                L += np.cross(r[:3], v[:3])

            # Normalize by swarm size and spread
            spread = np.std(np.linalg.norm(rel_pos, axis=1))
            vel_scale = np.mean(np.linalg.norm(velocities, axis=1))

            if spread > 0 and vel_scale > 0:
                return np.linalg.norm(L) / (len(positions) * spread * vel_scale)

        return 0.0

    def compute_persistence_barcode(self, max_dim: int = 1) -> Dict[int, List[Tuple[float, float]]]:
        """
        Compute persistence barcode (birth-death pairs).

        Simplified version using Rips filtration.
        """
        if len(self.positions) < 2:
            return {0: [(0, float('inf'))], 1: []}

        positions = np.array(self.positions)
        n = len(positions)

        # Compute pairwise distances
        distances = np.zeros((n, n))
        for i in range(n):
            for j in range(i+1, n):
                d = np.linalg.norm(positions[i] - positions[j])
                distances[i, j] = distances[j, i] = d

        # Simple persistence computation
        # Connected components (dimension 0)
        barcode = {0: [], 1: []}

        # Track component merges using union-find
        parent = list(range(n))
        birth_time = [0.0] * n

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y, t):
            px, py = find(x), find(y)
            if px != py:
                # Merge: one component dies
                if birth_time[px] < birth_time[py]:
                    parent[py] = px
                    barcode[0].append((birth_time[py], t))
                else:
                    parent[px] = py
                    barcode[0].append((birth_time[px], t))

        # Sort edges by distance
        edges = []
        for i in range(n):
            for j in range(i+1, n):
                edges.append((distances[i, j], i, j))
        edges.sort()

        # Process edges
        for d, i, j in edges:
            union(i, j, d)

        # One component survives to infinity
        roots = set(find(i) for i in range(n))
        for r in roots:
            barcode[0].append((birth_time[r], float('inf')))

        return barcode

    def compute_persistence_entropy(self) -> float:
        """
        Compute entropy of persistence barcode.

        Higher entropy = more complex topological structure.
        """
        barcode = self.compute_persistence_barcode()

        # Compute total persistence (excluding infinite bars)
        persistences = []
        for dim, pairs in barcode.items():
            for birth, death in pairs:
                if death < float('inf'):
                    persistences.append(death - birth)

        if not persistences or sum(persistences) == 0:
            return 0.0

        total = sum(persistences)
        probs = [p / total for p in persistences]

        # Shannon entropy
        entropy = -sum(p * np.log(p + 1e-10) for p in probs if p > 0)
        return entropy

    def classify_behavior(self) -> Tuple[SwarmBehavior, float]:
        """
        Classify swarm behavior from metrics.

        Returns (behavior, confidence).
        """
        if not self.positions:
            return SwarmBehavior.UNKNOWN, 0.0

        polarization = self.compute_polarization()
        angular_momentum = self.compute_angular_momentum()
        spatial = self.compute_spatial_metrics()

        # Classification rules
        if polarization > 0.7:
            # High alignment = flock
            return SwarmBehavior.FLOCK, polarization

        if angular_momentum > 0.5:
            # High rotation = torus/milling
            confidence = min(1.0, angular_momentum)
            return SwarmBehavior.TORUS, confidence

        if spatial["spread"] / (spatial["diameter"] + 1e-10) > 0.5:
            # Spread out relative to diameter = disordered
            return SwarmBehavior.DISORDERED, 0.7

        # Check for clusters (simplified)
        barcode = self.compute_persistence_barcode()
        long_bars = [d - b for b, d in barcode[0] if d < float('inf') and d - b > spatial["spread"]]

        if len(long_bars) >= 2:
            return SwarmBehavior.CLUSTER, 0.6

        return SwarmBehavior.UNKNOWN, 0.3

    def analyze(self) -> SwarmMetrics:
        """Perform full swarm analysis."""
        spatial = self.compute_spatial_metrics()
        behavior, confidence = self.classify_behavior()
        barcode = self.compute_persistence_barcode()

        # Compute Betti numbers (approximate)
        b0 = len([p for p in barcode[0] if p[1] == float('inf')])
        b1 = len(barcode.get(1, []))

        return SwarmMetrics(
            agent_count=len(self.positions),
            centroid=spatial["centroid"],
            spread=spatial["spread"],
            diameter=spatial["diameter"],
            polarization=self.compute_polarization(),
            angular_momentum=self.compute_angular_momentum(),
            persistence_entropy=self.compute_persistence_entropy(),
            betti_sequence=(b0, b1, 0),
            behavior=behavior,
            behavior_confidence=confidence,
        )
