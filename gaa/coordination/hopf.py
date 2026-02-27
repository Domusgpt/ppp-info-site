"""
Hopf Fibration Coordinator

Decomposes 3D orientation consensus into independent
pointing (S²) and roll (S¹) consensus problems.

Based on Watterson & Kumar's Hopf Fibration Control Algorithm
for aggressive quadrotor maneuvers.
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional

from ..foundational.quaternion import Quaternion


@dataclass
class HopfDecomposition:
    """Decomposition of quaternion via Hopf fibration."""

    # Original quaternion
    quaternion: Quaternion

    # Pointing direction (on S² base space)
    pointing: np.ndarray  # Unit vector in R³

    # Roll angle (fiber S¹)
    roll: float  # Radians

    # Spherical coordinates of pointing
    theta: float  # Polar angle
    phi: float    # Azimuthal angle

    def to_dict(self):
        return {
            "quaternion": self.quaternion.components.tolist(),
            "pointing": self.pointing.tolist(),
            "roll": self.roll,
            "theta": self.theta,
            "phi": self.phi,
        }


class HopfCoordinator:
    """
    Coordination using Hopf fibration decomposition.

    The Hopf fibration is a map π: S³ → S² with fiber S¹.
    This allows decomposing quaternion consensus into:
    1. Pointing consensus on S² (where to look)
    2. Roll consensus on S¹ (rotation about pointing axis)

    This separation is natural for many robotics tasks
    and allows independent control of pointing vs roll.
    """

    def __init__(self, reference_axis: np.ndarray = None):
        """
        Initialize coordinator.

        Args:
            reference_axis: Reference axis for measuring roll
                          (default: [0, 0, 1] = z-axis)
        """
        self.reference_axis = reference_axis if reference_axis is not None else np.array([0, 0, 1])
        self.reference_axis = self.reference_axis / np.linalg.norm(self.reference_axis)

    def decompose(self, quaternion: Quaternion) -> HopfDecomposition:
        """
        Decompose quaternion into pointing + roll.

        The Hopf fibration maps:
        q = (w, x, y, z) → pointing direction on S²

        The fiber (roll) is the rotation about that pointing direction.
        """
        # Extract rotation matrix
        R = quaternion.to_rotation_matrix()

        # Pointing direction: where reference axis maps to
        pointing = R @ self.reference_axis

        # Spherical coordinates of pointing
        theta = np.arccos(np.clip(pointing[2], -1, 1))  # Polar
        phi = np.arctan2(pointing[1], pointing[0])       # Azimuthal

        # Roll: rotation about pointing axis
        # Find the rotation that aligns reference to pointing
        align_quat = self._quaternion_from_axis_to_axis(self.reference_axis, pointing)

        # The remaining rotation is the roll
        align_inv = align_quat.inverse()
        roll_quat = align_inv * quaternion

        # Extract roll angle
        roll = 2 * np.arctan2(
            np.linalg.norm(roll_quat.vector),
            roll_quat.w
        )
        # Adjust sign
        if np.dot(roll_quat.vector, pointing) < 0:
            roll = -roll

        return HopfDecomposition(
            quaternion=quaternion,
            pointing=pointing,
            roll=roll,
            theta=theta,
            phi=phi,
        )

    def _quaternion_from_axis_to_axis(
        self,
        from_axis: np.ndarray,
        to_axis: np.ndarray
    ) -> Quaternion:
        """Create quaternion that rotates from_axis to to_axis."""
        from_axis = from_axis / np.linalg.norm(from_axis)
        to_axis = to_axis / np.linalg.norm(to_axis)

        dot = np.dot(from_axis, to_axis)

        if dot > 0.9999:
            return Quaternion.identity()

        if dot < -0.9999:
            # 180 degree rotation - find perpendicular axis
            perp = np.array([1, 0, 0])
            if abs(np.dot(from_axis, perp)) > 0.9:
                perp = np.array([0, 1, 0])
            axis = np.cross(from_axis, perp)
            axis = axis / np.linalg.norm(axis)
            return Quaternion.from_axis_angle(axis, np.pi)

        axis = np.cross(from_axis, to_axis)
        axis = axis / np.linalg.norm(axis)
        angle = np.arccos(dot)

        return Quaternion.from_axis_angle(axis, angle)

    def compose(
        self,
        pointing: np.ndarray,
        roll: float
    ) -> Quaternion:
        """
        Compose quaternion from pointing + roll.

        Inverse of decompose.
        """
        pointing = pointing / np.linalg.norm(pointing)

        # Quaternion to align reference axis to pointing
        align_quat = self._quaternion_from_axis_to_axis(self.reference_axis, pointing)

        # Roll quaternion about pointing axis
        roll_quat = Quaternion.from_axis_angle(pointing, roll)

        # Combined: first align, then roll
        return align_quat * roll_quat

    def pointing_consensus(
        self,
        decompositions: list,
        weights: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Compute consensus pointing direction on S².

        Uses weighted average on the sphere.
        """
        if not decompositions:
            return self.reference_axis.copy()

        n = len(decompositions)
        if weights is None:
            weights = np.ones(n) / n

        # Weighted average of pointing vectors
        avg = np.zeros(3)
        for d, w in zip(decompositions, weights):
            avg += w * d.pointing

        norm = np.linalg.norm(avg)
        if norm < 1e-10:
            return self.reference_axis.copy()

        return avg / norm

    def roll_consensus(
        self,
        decompositions: list,
        weights: Optional[np.ndarray] = None
    ) -> float:
        """
        Compute consensus roll angle on S¹.

        Uses circular mean.
        """
        if not decompositions:
            return 0.0

        n = len(decompositions)
        if weights is None:
            weights = np.ones(n) / n

        # Circular mean
        sin_sum = sum(w * np.sin(d.roll) for w, d in zip(weights, decompositions))
        cos_sum = sum(w * np.cos(d.roll) for w, d in zip(weights, decompositions))

        return np.arctan2(sin_sum, cos_sum)

    def full_consensus(
        self,
        quaternions: list,
        weights: Optional[np.ndarray] = None
    ) -> Quaternion:
        """
        Compute full consensus using Hopf decomposition.

        Independently averages pointing and roll, then recomposes.
        """
        decomps = [self.decompose(q) for q in quaternions]

        consensus_pointing = self.pointing_consensus(decomps, weights)
        consensus_roll = self.roll_consensus(decomps, weights)

        return self.compose(consensus_pointing, consensus_roll)

    def pointing_disagreement(self, decompositions: list) -> float:
        """Compute disagreement in pointing directions."""
        if len(decompositions) < 2:
            return 0.0

        total = 0.0
        count = 0
        for i, d1 in enumerate(decompositions):
            for d2 in decompositions[i+1:]:
                # Angular distance between pointing vectors
                dot = np.clip(np.dot(d1.pointing, d2.pointing), -1, 1)
                angle = np.arccos(dot)
                total += angle ** 2
                count += 1

        return total / count if count > 0 else 0.0

    def roll_disagreement(self, decompositions: list) -> float:
        """Compute disagreement in roll angles."""
        if len(decompositions) < 2:
            return 0.0

        rolls = [d.roll for d in decompositions]
        # Circular variance
        sin_mean = np.mean([np.sin(r) for r in rolls])
        cos_mean = np.mean([np.cos(r) for r in rolls])
        R = np.sqrt(sin_mean**2 + cos_mean**2)

        # Circular variance: 1 - R
        return 1.0 - R
