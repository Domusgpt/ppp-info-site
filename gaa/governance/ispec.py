"""
Intent Specification (ISpec)

Defines geometric constraints as part of an agent's constitution.
Specifies permitted manifold regions, coherence thresholds, and
topological invariants that must be preserved.

ISpec Structure:
- Geometric constraints (permitted polytope regions)
- Coherence requirements (minimum spinor coherence)
- Topological invariants (required Betti numbers)
- Drift limits (maximum allowed drift metrics)
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class ConstraintType(Enum):
    """Types of geometric constraints in ISpec."""

    MANIFOLD_REGION = "manifold_region"
    COHERENCE_THRESHOLD = "coherence_threshold"
    TOPOLOGICAL_INVARIANT = "topological_invariant"
    DRIFT_LIMIT = "drift_limit"
    ISOCLINIC_BOUND = "isoclinic_bound"
    QUATERNION_RANGE = "quaternion_range"


@dataclass
class ISpec:
    """
    Intent Specification for geometric agent governance.

    Defines the constitution of permitted geometric behaviors.
    Agents must operate within these constraints.
    """

    # Identification
    spec_id: str = ""
    name: str = ""
    version: str = "1.0.0"
    created: float = field(default_factory=lambda: datetime.utcnow().timestamp())

    # Coherence requirements
    min_spinor_coherence: float = 0.7
    max_isoclinic_defect: float = 0.3

    # Drift limits
    max_delta_hyperbolicity: float = 0.2
    max_angular_velocity: float = 1.0
    max_persistence_drift: float = 0.5

    # Topological requirements
    required_betti_0: Optional[int] = None  # Connected components
    required_betti_1: Optional[int] = None  # 1-cycles
    required_betti_2: Optional[int] = None  # 2-cycles

    # Manifold region constraints (list of permitted region IDs)
    permitted_regions: List[str] = field(default_factory=list)

    # Quaternion bounds (optional)
    quaternion_w_min: float = -1.0
    quaternion_w_max: float = 1.0

    # Custom constraints
    custom_constraints: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    description: str = ""
    author: str = ""

    def validate_coherence(self, coherence: float) -> bool:
        """Check if coherence meets requirement."""
        return coherence >= self.min_spinor_coherence

    def validate_isoclinic(self, left_angle: float, right_angle: float) -> bool:
        """Check if isoclinic angles are within bound."""
        defect = abs(left_angle - right_angle)
        return defect <= self.max_isoclinic_defect

    def validate_drift(
        self,
        delta_hyperbolicity: float,
        angular_velocity: float,
        persistence_drift: float
    ) -> Dict[str, bool]:
        """Validate drift metrics against limits."""
        return {
            "hyperbolicity": delta_hyperbolicity <= self.max_delta_hyperbolicity,
            "angular_velocity": angular_velocity <= self.max_angular_velocity,
            "persistence": persistence_drift <= self.max_persistence_drift,
        }

    def validate_topology(
        self,
        betti_0: int,
        betti_1: int,
        betti_2: int
    ) -> bool:
        """Validate topological invariants."""
        if self.required_betti_0 is not None and betti_0 != self.required_betti_0:
            return False
        if self.required_betti_1 is not None and betti_1 != self.required_betti_1:
            return False
        if self.required_betti_2 is not None and betti_2 != self.required_betti_2:
            return False
        return True

    def validate_region(self, region_id: str) -> bool:
        """Check if region is permitted."""
        if not self.permitted_regions:
            return True  # No restrictions
        return region_id in self.permitted_regions

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "spec_id": self.spec_id,
            "name": self.name,
            "version": self.version,
            "created": self.created,
            "coherence": {
                "min_spinor": self.min_spinor_coherence,
                "max_isoclinic_defect": self.max_isoclinic_defect,
            },
            "drift_limits": {
                "max_hyperbolicity": self.max_delta_hyperbolicity,
                "max_angular_velocity": self.max_angular_velocity,
                "max_persistence": self.max_persistence_drift,
            },
            "topology": {
                "betti_0": self.required_betti_0,
                "betti_1": self.required_betti_1,
                "betti_2": self.required_betti_2,
            },
            "permitted_regions": self.permitted_regions,
            "quaternion_bounds": {
                "w_min": self.quaternion_w_min,
                "w_max": self.quaternion_w_max,
            },
            "custom": self.custom_constraints,
            "metadata": {
                "description": self.description,
                "author": self.author,
            },
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ISpec':
        """Create from dictionary."""
        coherence = data.get("coherence", {})
        drift = data.get("drift_limits", {})
        topology = data.get("topology", {})
        quat = data.get("quaternion_bounds", {})
        meta = data.get("metadata", {})

        return cls(
            spec_id=data.get("spec_id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            created=data.get("created", datetime.utcnow().timestamp()),
            min_spinor_coherence=coherence.get("min_spinor", 0.7),
            max_isoclinic_defect=coherence.get("max_isoclinic_defect", 0.3),
            max_delta_hyperbolicity=drift.get("max_hyperbolicity", 0.2),
            max_angular_velocity=drift.get("max_angular_velocity", 1.0),
            max_persistence_drift=drift.get("max_persistence", 0.5),
            required_betti_0=topology.get("betti_0"),
            required_betti_1=topology.get("betti_1"),
            required_betti_2=topology.get("betti_2"),
            permitted_regions=data.get("permitted_regions", []),
            quaternion_w_min=quat.get("w_min", -1.0),
            quaternion_w_max=quat.get("w_max", 1.0),
            custom_constraints=data.get("custom", {}),
            description=meta.get("description", ""),
            author=meta.get("author", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'ISpec':
        """Deserialize from JSON."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def permissive(cls, name: str = "permissive") -> 'ISpec':
        """Create permissive ISpec with relaxed constraints."""
        return cls(
            name=name,
            min_spinor_coherence=0.3,
            max_isoclinic_defect=1.0,
            max_delta_hyperbolicity=0.5,
            max_angular_velocity=5.0,
            max_persistence_drift=1.0,
        )

    @classmethod
    def strict(cls, name: str = "strict") -> 'ISpec':
        """Create strict ISpec with tight constraints."""
        return cls(
            name=name,
            min_spinor_coherence=0.9,
            max_isoclinic_defect=0.1,
            max_delta_hyperbolicity=0.1,
            max_angular_velocity=0.5,
            max_persistence_drift=0.2,
        )
