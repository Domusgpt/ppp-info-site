"""
Drift Detection for Reasoning Monitoring

Implements multiple drift detection metrics:
- δ-Hyperbolicity: Measures tree-likeness of reasoning chains
- Quaternion Coherence: Stability of orientation state
- Persistence Homology Comparison: Topological similarity

High drift indicates reasoning corruption or deviation
from valid cognitive trajectories.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any
from collections import deque

from ..foundational.quaternion import Quaternion


@dataclass
class DriftMetrics:
    """Collection of drift detection metrics."""

    delta_hyperbolicity: float = 0.0
    quaternion_coherence: float = 1.0
    persistence_distance: float = 0.0
    angular_velocity: float = 0.0
    isoclinic_defect: float = 0.0

    # Thresholds for each metric
    delta_threshold: float = 0.2
    coherence_threshold: float = 0.7
    persistence_threshold: float = 0.5
    velocity_threshold: float = 1.0
    isoclinic_threshold: float = 0.3

    @property
    def is_drifting(self) -> bool:
        """Check if any metric exceeds threshold."""
        return (
            self.delta_hyperbolicity > self.delta_threshold or
            self.quaternion_coherence < self.coherence_threshold or
            self.persistence_distance > self.persistence_threshold or
            self.angular_velocity > self.velocity_threshold or
            self.isoclinic_defect > self.isoclinic_threshold
        )

    @property
    def drift_severity(self) -> float:
        """Compute aggregate drift severity [0, 1]."""
        scores = [
            self.delta_hyperbolicity / self.delta_threshold,
            1.0 - (self.quaternion_coherence / self.coherence_threshold),
            self.persistence_distance / self.persistence_threshold,
            self.angular_velocity / self.velocity_threshold,
            self.isoclinic_defect / self.isoclinic_threshold,
        ]
        # Clamp and average
        clamped = [max(0, min(1, s)) for s in scores]
        return np.mean(clamped)

    @property
    def primary_drift_source(self) -> str:
        """Identify the primary source of drift."""
        metrics = {
            "hyperbolicity": self.delta_hyperbolicity / self.delta_threshold,
            "coherence": 1.0 - (self.quaternion_coherence / self.coherence_threshold),
            "topology": self.persistence_distance / self.persistence_threshold,
            "velocity": self.angular_velocity / self.velocity_threshold,
            "isoclinic": self.isoclinic_defect / self.isoclinic_threshold,
        }
        return max(metrics, key=metrics.get)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with JSON-serializable types."""
        return {
            "delta_hyperbolicity": float(self.delta_hyperbolicity),
            "quaternion_coherence": float(self.quaternion_coherence),
            "persistence_distance": float(self.persistence_distance),
            "angular_velocity": float(self.angular_velocity),
            "isoclinic_defect": float(self.isoclinic_defect),
            "is_drifting": bool(self.is_drifting),
            "drift_severity": float(self.drift_severity),
            "primary_source": self.primary_drift_source,
        }


class DriftDetector:
    """
    Monitors reasoning state for drift from valid trajectories.

    Tracks history of states and computes drift metrics
    to detect corruption or deviation.
    """

    def __init__(
        self,
        history_length: int = 50,
        delta_threshold: float = 0.2,
        coherence_threshold: float = 0.7,
        velocity_threshold: float = 1.0
    ):
        """
        Initialize drift detector.

        Args:
            history_length: Number of states to keep in history
            delta_threshold: Threshold for δ-hyperbolicity
            coherence_threshold: Minimum quaternion coherence
            velocity_threshold: Maximum angular velocity
        """
        self.history_length = history_length
        self.delta_threshold = delta_threshold
        self.coherence_threshold = coherence_threshold
        self.velocity_threshold = velocity_threshold

        # State history
        self.quaternion_history: deque = deque(maxlen=history_length)
        self.coherence_history: deque = deque(maxlen=history_length)
        self.fingerprint_history: deque = deque(maxlen=history_length)

        # Reference state for comparison
        self.reference_quaternion: Optional[Quaternion] = None
        self.reference_coherence: float = 1.0

    def set_reference(
        self,
        quaternion: Quaternion,
        coherence: float = 1.0
    ) -> None:
        """Set reference state for drift comparison."""
        self.reference_quaternion = quaternion
        self.reference_coherence = coherence

    def update(
        self,
        quaternion: Quaternion,
        coherence: float,
        fingerprint: Optional[str] = None
    ) -> DriftMetrics:
        """
        Update detector with new state and compute drift metrics.

        Args:
            quaternion: Current quaternion state
            coherence: Current spinor coherence
            fingerprint: Optional geometric fingerprint

        Returns:
            DriftMetrics for current state
        """
        # Store in history
        self.quaternion_history.append(quaternion)
        self.coherence_history.append(coherence)
        if fingerprint:
            self.fingerprint_history.append(fingerprint)

        # Compute metrics
        metrics = DriftMetrics(
            delta_threshold=self.delta_threshold,
            coherence_threshold=self.coherence_threshold,
            velocity_threshold=self.velocity_threshold,
        )

        # δ-Hyperbolicity from quaternion history
        if len(self.quaternion_history) >= 4:
            metrics.delta_hyperbolicity = self._compute_hyperbolicity()

        # Quaternion coherence
        metrics.quaternion_coherence = coherence

        # Angular velocity
        if len(self.quaternion_history) >= 2:
            metrics.angular_velocity = self._compute_angular_velocity()

        # Isoclinic defect
        left_angle, right_angle = quaternion.isoclinic_angles()
        metrics.isoclinic_defect = abs(left_angle - right_angle)

        # Persistence distance (simplified)
        if self.reference_quaternion:
            metrics.persistence_distance = quaternion.angular_distance(
                self.reference_quaternion
            )

        return metrics

    def _compute_hyperbolicity(self) -> float:
        """
        Compute δ-hyperbolicity of quaternion trajectory.

        δ-hyperbolicity measures how tree-like the space is.
        Lower values indicate more hierarchical structure.

        Uses Gromov's four-point condition on last 4 quaternions.
        """
        if len(self.quaternion_history) < 4:
            return 0.0

        # Take last 4 quaternions
        quats = list(self.quaternion_history)[-4:]

        # Compute all pairwise distances
        d = np.zeros((4, 4))
        for i in range(4):
            for j in range(i + 1, 4):
                d[i, j] = d[j, i] = quats[i].angular_distance(quats[j])

        # Gromov product: (x|y)_w = 0.5 * (d(x,w) + d(y,w) - d(x,y))
        # δ = max over all x,y,z,w of:
        #   min((x|y)_w, (y|z)_w) - (x|z)_w

        delta = 0.0
        for w in range(4):
            others = [i for i in range(4) if i != w]
            x, y, z = others

            # Gromov products
            xy_w = 0.5 * (d[x, w] + d[y, w] - d[x, y])
            yz_w = 0.5 * (d[y, w] + d[z, w] - d[y, z])
            xz_w = 0.5 * (d[x, w] + d[z, w] - d[x, z])

            # Four-point condition
            delta_candidate = min(xy_w, yz_w) - xz_w
            delta = max(delta, delta_candidate)

        return max(0, delta)

    def _compute_angular_velocity(self) -> float:
        """Compute angular velocity from recent quaternion history."""
        if len(self.quaternion_history) < 2:
            return 0.0

        quats = list(self.quaternion_history)[-2:]
        angle = quats[1].angular_distance(quats[0])

        # Assuming unit time step
        return angle

    def detect_anomaly(self, metrics: DriftMetrics) -> Dict[str, bool]:
        """
        Detect specific anomaly types from metrics.

        Returns dictionary of anomaly flags.
        """
        return {
            "tree_structure_loss": metrics.delta_hyperbolicity > self.delta_threshold,
            "coherence_drop": metrics.quaternion_coherence < self.coherence_threshold,
            "rapid_rotation": metrics.angular_velocity > self.velocity_threshold,
            "isoclinic_violation": metrics.isoclinic_defect > 0.3,
            "reference_deviation": metrics.persistence_distance > 0.5,
        }

    def get_baseline_metrics(self) -> DriftMetrics:
        """Compute baseline metrics from history."""
        if not self.coherence_history:
            return DriftMetrics()

        coherences = list(self.coherence_history)
        mean_coherence = np.mean(coherences)

        metrics = DriftMetrics()
        metrics.quaternion_coherence = mean_coherence

        if len(self.quaternion_history) >= 4:
            metrics.delta_hyperbolicity = self._compute_hyperbolicity()

        return metrics

    def reset(self) -> None:
        """Clear history and reset detector."""
        self.quaternion_history.clear()
        self.coherence_history.clear()
        self.fingerprint_history.clear()
        self.reference_quaternion = None
        self.reference_coherence = 1.0
