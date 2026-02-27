"""
Geometric State Container

Unified state representation for PPP-CRA integration.
Combines polytope coordinates, spinor states, and topological signatures
into a single auditable container.

Design Principles:
- Immutable state snapshots for audit trails
- Lazy computation of derived quantities
- Canonical serialization for hashing
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import json
from datetime import datetime

from .quaternion import Quaternion, DualQuaternion
from .clifford import Multivector


@dataclass(frozen=True)
class GeometricState:
    """
    Immutable snapshot of geometric system state.

    Captures the complete state needed for audit:
    - Polytope vertex positions (4D coordinates)
    - Quaternion bridge state (left/right isoclinic)
    - Spinor coherence metrics
    - Topological invariants (Betti numbers approximation)

    Frozen dataclass ensures immutability for audit trails.
    """

    # Timestamp
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())

    # 4D polytope state (600-cell or other)
    polytope_vertices: Tuple[Tuple[float, ...], ...] = field(default_factory=tuple)
    polytope_centroid: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    polytope_type: str = "600-cell"

    # Quaternion state
    quaternion_components: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    dual_quaternion_real: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    dual_quaternion_dual: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    # Isoclinic decomposition
    left_isoclinic_angle: float = 0.0
    right_isoclinic_angle: float = 0.0

    # Spinor metrics
    spinor_coherence: float = 1.0
    bridge_magnitude: float = 1.0
    hopf_fiber: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)

    # Topological invariants (approximate Betti numbers)
    betti_0: int = 1  # Connected components
    betti_1: int = 0  # 1-cycles (loops)
    betti_2: int = 0  # 2-cycles (voids)

    # Manifold metrics
    delta_hyperbolicity: float = 0.0  # Tree-likeness measure
    geodesic_distance: float = 0.0    # Distance from reference state

    # Continuum parameters
    flux_density: float = 0.0
    orientation_residual: float = 0.0

    # Metadata
    state_id: str = ""
    previous_state_id: str = ""

    def __post_init__(self):
        """Compute state_id if not provided."""
        if not self.state_id:
            # Use object.__setattr__ since frozen
            object.__setattr__(self, 'state_id', self._compute_state_id())

    def _compute_state_id(self) -> str:
        """Compute deterministic state ID from content."""
        # Canonical JSON representation
        canonical = self.to_canonical_dict()
        canonical_json = json.dumps(canonical, sort_keys=True)
        return hashlib.sha256(canonical_json.encode()).hexdigest()[:16]

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Convert to canonical dictionary for hashing."""
        return {
            "timestamp": round(self.timestamp, 6),
            "polytope_type": self.polytope_type,
            "polytope_centroid": [round(x, 10) for x in self.polytope_centroid],
            "quaternion": [round(x, 10) for x in self.quaternion_components],
            "left_angle": round(self.left_isoclinic_angle, 10),
            "right_angle": round(self.right_isoclinic_angle, 10),
            "coherence": round(self.spinor_coherence, 10),
            "bridge_mag": round(self.bridge_magnitude, 10),
            "betti": [self.betti_0, self.betti_1, self.betti_2],
            "delta_h": round(self.delta_hyperbolicity, 10),
            "prev_id": self.previous_state_id,
        }

    def fingerprint(self) -> bytes:
        """Compute cryptographic fingerprint."""
        canonical = self.to_canonical_dict()
        canonical_json = json.dumps(canonical, sort_keys=True)
        return hashlib.sha256(canonical_json.encode()).digest()

    def fingerprint_hex(self) -> str:
        """Compute fingerprint as hex string."""
        return self.fingerprint().hex()

    @property
    def quaternion(self) -> Quaternion:
        """Get quaternion object."""
        return Quaternion(np.array(self.quaternion_components))

    @property
    def dual_quaternion(self) -> DualQuaternion:
        """Get dual quaternion object."""
        return DualQuaternion(
            real=Quaternion(np.array(self.dual_quaternion_real)),
            dual=Quaternion(np.array(self.dual_quaternion_dual))
        )

    @property
    def isoclinic_defect(self) -> float:
        """
        Measure of non-isoclinicity.

        Zero for pure isoclinic rotations.
        Non-zero indicates general 4D rotation or noise.
        """
        return abs(self.left_isoclinic_angle - self.right_isoclinic_angle)

    @property
    def topological_signature(self) -> Tuple[int, int, int]:
        """Betti numbers as tuple."""
        return (self.betti_0, self.betti_1, self.betti_2)

    def distance_to(self, other: 'GeometricState') -> float:
        """Compute geometric distance to another state."""
        # Quaternion distance
        q_dist = self.quaternion.angular_distance(other.quaternion)

        # Centroid distance
        c1 = np.array(self.polytope_centroid)
        c2 = np.array(other.polytope_centroid)
        c_dist = np.linalg.norm(c1 - c2)

        # Coherence difference
        coh_diff = abs(self.spinor_coherence - other.spinor_coherence)

        # Combined distance
        return np.sqrt(q_dist**2 + c_dist**2 + coh_diff**2)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "state_id": self.state_id,
            "previous_state_id": self.previous_state_id,
            "timestamp": self.timestamp,
            "polytope": {
                "type": self.polytope_type,
                "centroid": list(self.polytope_centroid),
                "vertex_count": len(self.polytope_vertices),
            },
            "quaternion": {
                "components": list(self.quaternion_components),
                "left_angle": self.left_isoclinic_angle,
                "right_angle": self.right_isoclinic_angle,
            },
            "spinor": {
                "coherence": self.spinor_coherence,
                "bridge_magnitude": self.bridge_magnitude,
                "hopf_fiber": list(self.hopf_fiber),
            },
            "topology": {
                "betti_0": self.betti_0,
                "betti_1": self.betti_1,
                "betti_2": self.betti_2,
            },
            "manifold": {
                "delta_hyperbolicity": self.delta_hyperbolicity,
                "geodesic_distance": self.geodesic_distance,
                "flux_density": self.flux_density,
                "orientation_residual": self.orientation_residual,
            },
            "fingerprint": self.fingerprint_hex(),
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'GeometricState':
        """Deserialize from JSON string."""
        data = json.loads(json_str)

        return cls(
            state_id=data.get("state_id", ""),
            previous_state_id=data.get("previous_state_id", ""),
            timestamp=data.get("timestamp", 0.0),
            polytope_type=data.get("polytope", {}).get("type", "600-cell"),
            polytope_centroid=tuple(data.get("polytope", {}).get("centroid", [0, 0, 0, 0])),
            quaternion_components=tuple(data.get("quaternion", {}).get("components", [1, 0, 0, 0])),
            left_isoclinic_angle=data.get("quaternion", {}).get("left_angle", 0.0),
            right_isoclinic_angle=data.get("quaternion", {}).get("right_angle", 0.0),
            spinor_coherence=data.get("spinor", {}).get("coherence", 1.0),
            bridge_magnitude=data.get("spinor", {}).get("bridge_magnitude", 1.0),
            hopf_fiber=tuple(data.get("spinor", {}).get("hopf_fiber", [1, 0, 0, 0])),
            betti_0=data.get("topology", {}).get("betti_0", 1),
            betti_1=data.get("topology", {}).get("betti_1", 0),
            betti_2=data.get("topology", {}).get("betti_2", 0),
            delta_hyperbolicity=data.get("manifold", {}).get("delta_hyperbolicity", 0.0),
            geodesic_distance=data.get("manifold", {}).get("geodesic_distance", 0.0),
            flux_density=data.get("manifold", {}).get("flux_density", 0.0),
            orientation_residual=data.get("manifold", {}).get("orientation_residual", 0.0),
        )


@dataclass
class StateBundle:
    """
    Mutable container for building geometric state.

    Used during computation before creating immutable GeometricState.
    """

    polytope_vertices: List[np.ndarray] = field(default_factory=list)
    quaternion: Quaternion = field(default_factory=Quaternion.identity)
    dual_quaternion: DualQuaternion = field(default_factory=DualQuaternion.identity)
    spinor_coherence: float = 1.0
    bridge_magnitude: float = 1.0
    hopf_fiber: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0]))
    betti_numbers: Tuple[int, int, int] = (1, 0, 0)
    delta_hyperbolicity: float = 0.0
    flux_density: float = 0.0
    orientation_residual: float = 0.0
    previous_state_id: str = ""

    def finalize(self) -> GeometricState:
        """Convert to immutable GeometricState."""
        # Compute centroid
        if self.polytope_vertices:
            vertices = np.array(self.polytope_vertices)
            centroid = vertices.mean(axis=0)
            vertex_tuples = tuple(tuple(v) for v in self.polytope_vertices)
        else:
            centroid = np.zeros(4)
            vertex_tuples = ()

        # Get isoclinic angles
        left_angle, right_angle = self.quaternion.isoclinic_angles()

        return GeometricState(
            polytope_vertices=vertex_tuples,
            polytope_centroid=tuple(centroid),
            quaternion_components=tuple(self.quaternion.components),
            dual_quaternion_real=tuple(self.dual_quaternion.real.components),
            dual_quaternion_dual=tuple(self.dual_quaternion.dual.components),
            left_isoclinic_angle=left_angle,
            right_isoclinic_angle=right_angle,
            spinor_coherence=self.spinor_coherence,
            bridge_magnitude=self.bridge_magnitude,
            hopf_fiber=tuple(self.hopf_fiber),
            betti_0=self.betti_numbers[0],
            betti_1=self.betti_numbers[1],
            betti_2=self.betti_numbers[2],
            delta_hyperbolicity=self.delta_hyperbolicity,
            flux_density=self.flux_density,
            orientation_residual=self.orientation_residual,
            previous_state_id=self.previous_state_id,
        )

    def update_from_ppp_telemetry(self, telemetry: Dict[str, Any]) -> None:
        """
        Update state from PPP SonicGeometryEngine telemetry.

        Parses the telemetry schemas defined in docs/telemetry-schemas.md.
        """
        # Quaternion bridge data
        if "quaternion" in telemetry:
            q_data = telemetry["quaternion"]
            if "bridge" in q_data:
                bridge = q_data["bridge"]
                self.quaternion = Quaternion(np.array([
                    bridge.get("w", 1.0),
                    bridge.get("x", 0.0),
                    bridge.get("y", 0.0),
                    bridge.get("z", 0.0)
                ]))
            if "bridgeMagnitude" in q_data:
                self.bridge_magnitude = q_data["bridgeMagnitude"]

        # Spinor data
        if "spinor" in telemetry:
            s_data = telemetry["spinor"]
            if "coherence" in s_data:
                self.spinor_coherence = s_data["coherence"]

        # Hopf fiber
        if "hopfFiber" in telemetry:
            hf = telemetry["hopfFiber"]
            self.hopf_fiber = np.array([
                hf.get("w", 1.0),
                hf.get("x", 0.0),
                hf.get("y", 0.0),
                hf.get("z", 0.0)
            ])

        # Continuum data
        if "continuum" in telemetry:
            c_data = telemetry["continuum"]
            if "fluxDensity" in c_data:
                self.flux_density = c_data["fluxDensity"]
            if "orientationResidual" in c_data:
                self.orientation_residual = c_data["orientationResidual"]

        # Manifold metrics
        if "manifold" in telemetry:
            m_data = telemetry["manifold"]
            if "deltaHyperbolicity" in m_data:
                self.delta_hyperbolicity = m_data["deltaHyperbolicity"]
