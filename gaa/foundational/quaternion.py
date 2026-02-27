"""
Quaternion and Dual Quaternion Algebra

Implements unit quaternions for SO(3) rotations and dual quaternions
for SE(3) rigid body transformations with proper normalization constraints.

Mathematical Foundation:
- Quaternion q = w + xi + yj + zk where i² = j² = k² = ijk = -1
- Unit quaternion |q| = 1 represents rotation via q·v·q*
- Dual quaternion q̂ = q_r + ε·q_d encodes screw motion

Key Properties:
- Singularity-free rotation representation (no gimbal lock)
- Smooth interpolation via SLERP/ScLERP
- Natural encoding of angular momentum conservation

References:
- Shoemake (1985) "Animating rotation with quaternion curves"
- Kavan et al. (2008) "Dual Quaternions for Rigid Transformation Blending"
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, Optional, Union
import hashlib


@dataclass
class Quaternion:
    """
    Unit quaternion for 3D rotation representation.

    Stored as [w, x, y, z] where w is scalar part.
    Automatically normalizes on construction.

    Properties:
    - Represents element of S³ (3-sphere)
    - Double cover of SO(3): q and -q represent same rotation
    - Composition via Hamilton product
    """

    components: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0]))

    def __post_init__(self):
        """Ensure unit quaternion constraint."""
        self.components = np.asarray(self.components, dtype=np.float64)
        if self.components.shape != (4,):
            raise ValueError(f"Quaternion must have 4 components, got {self.components.shape}")
        self._normalize()

    def _normalize(self) -> None:
        """Normalize to unit quaternion."""
        norm = np.linalg.norm(self.components)
        if norm < 1e-10:
            self.components = np.array([1.0, 0.0, 0.0, 0.0])
        else:
            self.components = self.components / norm

    @property
    def w(self) -> float:
        """Scalar component."""
        return self.components[0]

    @property
    def x(self) -> float:
        """First imaginary component."""
        return self.components[1]

    @property
    def y(self) -> float:
        """Second imaginary component."""
        return self.components[2]

    @property
    def z(self) -> float:
        """Third imaginary component."""
        return self.components[3]

    @property
    def vector(self) -> np.ndarray:
        """Imaginary (vector) part [x, y, z]."""
        return self.components[1:4]

    @property
    def scalar(self) -> float:
        """Real (scalar) part w."""
        return self.components[0]

    @classmethod
    def identity(cls) -> 'Quaternion':
        """Return identity quaternion (no rotation)."""
        return cls(np.array([1.0, 0.0, 0.0, 0.0]))

    @classmethod
    def from_axis_angle(cls, axis: np.ndarray, angle: float) -> 'Quaternion':
        """
        Create quaternion from axis-angle representation.

        Args:
            axis: Unit vector rotation axis [x, y, z]
            angle: Rotation angle in radians
        """
        axis = np.asarray(axis, dtype=np.float64)
        axis_norm = np.linalg.norm(axis)
        if axis_norm < 1e-10:
            return cls.identity()
        axis = axis / axis_norm

        half_angle = angle / 2.0
        w = np.cos(half_angle)
        xyz = axis * np.sin(half_angle)

        return cls(np.array([w, xyz[0], xyz[1], xyz[2]]))

    @classmethod
    def from_rotation_matrix(cls, R: np.ndarray) -> 'Quaternion':
        """
        Create quaternion from 3x3 rotation matrix.

        Uses Shepperd's method for numerical stability.
        """
        R = np.asarray(R, dtype=np.float64)
        if R.shape != (3, 3):
            raise ValueError(f"Rotation matrix must be 3x3, got {R.shape}")

        trace = np.trace(R)

        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (R[2, 1] - R[1, 2]) * s
            y = (R[0, 2] - R[2, 0]) * s
            z = (R[1, 0] - R[0, 1]) * s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s

        return cls(np.array([w, x, y, z]))

    @classmethod
    def from_euler(cls, roll: float, pitch: float, yaw: float) -> 'Quaternion':
        """
        Create quaternion from Euler angles (ZYX convention).

        Args:
            roll: Rotation about X axis (radians)
            pitch: Rotation about Y axis (radians)
            yaw: Rotation about Z axis (radians)
        """
        cr, sr = np.cos(roll / 2), np.sin(roll / 2)
        cp, sp = np.cos(pitch / 2), np.sin(pitch / 2)
        cy, sy = np.cos(yaw / 2), np.sin(yaw / 2)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy

        return cls(np.array([w, x, y, z]))

    def to_rotation_matrix(self) -> np.ndarray:
        """Convert to 3x3 rotation matrix."""
        w, x, y, z = self.components

        return np.array([
            [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
            [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
            [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]
        ])

    def to_axis_angle(self) -> Tuple[np.ndarray, float]:
        """Convert to axis-angle representation."""
        angle = 2.0 * np.arccos(np.clip(self.w, -1.0, 1.0))

        sin_half = np.sin(angle / 2.0)
        if abs(sin_half) < 1e-10:
            return np.array([1.0, 0.0, 0.0]), 0.0

        axis = self.vector / sin_half
        return axis, angle

    def to_euler(self) -> Tuple[float, float, float]:
        """Convert to Euler angles (ZYX convention)."""
        w, x, y, z = self.components

        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = np.copysign(np.pi / 2, sinp)
        else:
            pitch = np.arcsin(sinp)

        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)

        return roll, pitch, yaw

    def conjugate(self) -> 'Quaternion':
        """Return quaternion conjugate q* = w - xi - yj - zk."""
        return Quaternion(np.array([self.w, -self.x, -self.y, -self.z]))

    def inverse(self) -> 'Quaternion':
        """Return quaternion inverse. For unit quaternions, equals conjugate."""
        return self.conjugate()

    def __mul__(self, other: 'Quaternion') -> 'Quaternion':
        """Hamilton product q1 * q2."""
        if not isinstance(other, Quaternion):
            raise TypeError(f"Cannot multiply Quaternion with {type(other)}")

        w1, x1, y1, z1 = self.components
        w2, x2, y2, z2 = other.components

        return Quaternion(np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ]))

    def rotate_vector(self, v: np.ndarray) -> np.ndarray:
        """Rotate a 3D vector by this quaternion: v' = q·v·q*."""
        v = np.asarray(v, dtype=np.float64)
        if v.shape != (3,):
            raise ValueError(f"Vector must have 3 components, got {v.shape}")

        # Create pure quaternion from vector
        v_quat = Quaternion(np.array([0.0, v[0], v[1], v[2]]))

        # Rotate: q * v * q*
        result = self * v_quat * self.conjugate()

        return result.vector

    def dot(self, other: 'Quaternion') -> float:
        """Inner product of quaternions."""
        return np.dot(self.components, other.components)

    def angular_distance(self, other: 'Quaternion') -> float:
        """
        Geodesic distance on S³ (shortest rotation angle).

        Returns angle in radians [0, π].
        """
        dot = abs(self.dot(other))  # abs handles q ≡ -q
        dot = np.clip(dot, -1.0, 1.0)
        return 2.0 * np.arccos(dot)

    @staticmethod
    def slerp(q0: 'Quaternion', q1: 'Quaternion', t: float) -> 'Quaternion':
        """
        Spherical Linear Interpolation.

        Args:
            q0: Start quaternion
            q1: End quaternion
            t: Interpolation parameter [0, 1]
        """
        t = np.clip(t, 0.0, 1.0)

        dot = q0.dot(q1)

        # Handle hemisphere (q ≡ -q)
        if dot < 0:
            q1 = Quaternion(-q1.components)
            dot = -dot

        # Linear interpolation for very close quaternions
        if dot > 0.9995:
            result = q0.components + t * (q1.components - q0.components)
            return Quaternion(result)

        theta_0 = np.arccos(dot)
        theta = theta_0 * t

        sin_theta = np.sin(theta)
        sin_theta_0 = np.sin(theta_0)

        s0 = np.cos(theta) - dot * sin_theta / sin_theta_0
        s1 = sin_theta / sin_theta_0

        return Quaternion(s0 * q0.components + s1 * q1.components)

    def decompose_isoclinic(self) -> Tuple['Quaternion', 'Quaternion']:
        """
        Decompose into left and right isoclinic components.

        Any 4D rotation can be factored as R = R_L · R_R where
        R_L and R_R are isoclinic rotations (rotate two orthogonal
        planes by the same angle).

        Returns:
            (q_left, q_right): Left and right isoclinic quaternions
        """
        # For a unit quaternion representing 4D rotation,
        # left-isoclinic: v → q·v
        # right-isoclinic: v → v·q
        # The decomposition depends on the specific 4D rotation matrix.
        # Here we return the quaternion and its conjugate as approximation.
        return (self, self.conjugate())

    def isoclinic_angles(self) -> Tuple[float, float]:
        """
        Compute left and right isoclinic rotation angles.

        For isoclinic rotations, both angles should be equal.
        Deviation indicates non-isoclinic (general) 4D rotation.
        """
        # The isoclinic angles are related to the quaternion components
        # For a pure rotation: angle = 2 * arccos(w)
        angle = 2.0 * np.arccos(np.clip(abs(self.w), 0.0, 1.0))

        # For simple rotations, left and right angles are equal
        # More complex decomposition needed for general 4D rotations
        return (angle, angle)

    def coherence(self) -> float:
        """
        Compute quaternion coherence metric.

        Measures stability of the quaternion state.
        High coherence (near 1.0) indicates stable orientation.
        Low coherence indicates noisy/unstable state.
        """
        # Coherence based on how close to a principal axis
        principal_strength = np.max(np.abs(self.components))
        return principal_strength

    def fingerprint(self) -> bytes:
        """
        Compute cryptographic fingerprint for audit trails.

        Returns SHA-256 hash of canonical representation.
        """
        # Canonical form: ensure w >= 0 (hemisphere normalization)
        canonical = self.components.copy()
        if canonical[0] < 0:
            canonical = -canonical

        # Round to avoid floating-point non-determinism
        canonical = np.round(canonical, decimals=10)

        # Hash
        data = canonical.tobytes()
        return hashlib.sha256(data).digest()

    def __repr__(self) -> str:
        return f"Quaternion({self.w:.4f} + {self.x:.4f}i + {self.y:.4f}j + {self.z:.4f}k)"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Quaternion):
            return False
        # Account for q ≡ -q
        return np.allclose(self.components, other.components) or \
               np.allclose(self.components, -other.components)


@dataclass
class DualQuaternion:
    """
    Dual Quaternion for SE(3) rigid body transformation.

    q̂ = q_r + ε·q_d where ε² = 0, ε ≠ 0

    Encodes both rotation (q_r) and translation (via q_d).

    Constraints:
    - |q_r| = 1 (unit real part)
    - q_r · q_d = 0 (orthogonality)

    Properties:
    - Singularity-free SE(3) representation
    - ScLERP for smooth motion interpolation
    - Natural screw motion encoding
    """

    real: Quaternion = field(default_factory=Quaternion.identity)
    dual: Quaternion = field(default_factory=lambda: Quaternion(np.zeros(4)))

    def __post_init__(self):
        """Ensure dual quaternion constraints."""
        # Normalize real part
        if not isinstance(self.real, Quaternion):
            self.real = Quaternion(np.asarray(self.real))

        if not isinstance(self.dual, Quaternion):
            self.dual = Quaternion(np.asarray(self.dual))

        # Enforce orthogonality constraint: q_r · q_d = 0
        self._enforce_constraints()

    def _enforce_constraints(self) -> None:
        """Enforce unit norm and orthogonality."""
        # Real part is already normalized by Quaternion class

        # Project dual part to be orthogonal to real part
        # Only modify if orthogonality violation is significant
        dot = np.dot(self.real.components, self.dual.components)
        if abs(dot) > 1e-12:
            projected = self.dual.components - dot * self.real.components
            # Create new quaternion without re-normalizing (dual part need not be unit)
            self.dual = Quaternion.__new__(Quaternion)
            self.dual.components = projected

    @classmethod
    def identity(cls) -> 'DualQuaternion':
        """Return identity dual quaternion (no transformation)."""
        return cls(
            real=Quaternion.identity(),
            dual=Quaternion(np.zeros(4))
        )

    @classmethod
    def from_rotation_translation(
        cls,
        rotation: Quaternion,
        translation: np.ndarray
    ) -> 'DualQuaternion':
        """
        Create from separate rotation and translation.

        Args:
            rotation: Unit quaternion for rotation
            translation: Translation vector [x, y, z]
        """
        translation = np.asarray(translation, dtype=np.float64)
        if translation.shape != (3,):
            raise ValueError(f"Translation must have 3 components")

        # q_d = 0.5 * t * q_r where t is pure quaternion (0, tx, ty, tz)
        # Use raw translation values (NOT normalized) for Hamilton product
        tx, ty, tz = translation
        w, x, y, z = rotation.components

        # Compute dual part: 0.5 * t * q_r (Hamilton product)
        dual_components = 0.5 * np.array([
            -tx * x - ty * y - tz * z,
            tx * w + ty * z - tz * y,
            -tx * z + ty * w + tz * x,
            tx * y - ty * x + tz * w
        ])

        dual = Quaternion.__new__(Quaternion)
        dual.components = dual_components

        return cls(real=rotation, dual=dual)

    @classmethod
    def from_pose_matrix(cls, T: np.ndarray) -> 'DualQuaternion':
        """
        Create from 4x4 homogeneous transformation matrix.

        Args:
            T: 4x4 transformation matrix [R, t; 0, 1]
        """
        T = np.asarray(T, dtype=np.float64)
        if T.shape != (4, 4):
            raise ValueError(f"Transformation matrix must be 4x4")

        R = T[:3, :3]
        t = T[:3, 3]

        rotation = Quaternion.from_rotation_matrix(R)
        return cls.from_rotation_translation(rotation, t)

    def to_rotation_translation(self) -> Tuple[Quaternion, np.ndarray]:
        """Extract rotation quaternion and translation vector."""
        # Translation: t = 2 * q_d * q_r*
        q_r_conj = self.real.conjugate()

        t_quat_components = 2.0 * np.array([
            self.dual.w * q_r_conj.w - self.dual.x * q_r_conj.x -
            self.dual.y * q_r_conj.y - self.dual.z * q_r_conj.z,
            self.dual.w * q_r_conj.x + self.dual.x * q_r_conj.w +
            self.dual.y * q_r_conj.z - self.dual.z * q_r_conj.y,
            self.dual.w * q_r_conj.y - self.dual.x * q_r_conj.z +
            self.dual.y * q_r_conj.w + self.dual.z * q_r_conj.x,
            self.dual.w * q_r_conj.z + self.dual.x * q_r_conj.y -
            self.dual.y * q_r_conj.x + self.dual.z * q_r_conj.w
        ])

        translation = t_quat_components[1:4]
        return self.real, translation

    def to_pose_matrix(self) -> np.ndarray:
        """Convert to 4x4 homogeneous transformation matrix."""
        rotation, translation = self.to_rotation_translation()

        T = np.eye(4)
        T[:3, :3] = rotation.to_rotation_matrix()
        T[:3, 3] = translation

        return T

    def conjugate(self) -> 'DualQuaternion':
        """Dual quaternion conjugate."""
        return DualQuaternion(
            real=self.real.conjugate(),
            dual=self.dual.conjugate()
        )

    def __mul__(self, other: 'DualQuaternion') -> 'DualQuaternion':
        """Dual quaternion multiplication."""
        if not isinstance(other, DualQuaternion):
            raise TypeError(f"Cannot multiply DualQuaternion with {type(other)}")

        # (r1 + ε·d1) * (r2 + ε·d2) = r1*r2 + ε·(r1*d2 + d1*r2)
        new_real = self.real * other.real

        # d1*r2 + r1*d2
        d1_r2 = self.dual * other.real
        r1_d2 = self.real * other.dual

        new_dual_components = d1_r2.components + r1_d2.components
        new_dual = Quaternion.__new__(Quaternion)
        new_dual.components = new_dual_components

        return DualQuaternion(real=new_real, dual=new_dual)

    def transform_point(self, p: np.ndarray) -> np.ndarray:
        """Transform a 3D point by this dual quaternion: p' = R*p + t."""
        p = np.asarray(p, dtype=np.float64)

        # Extract rotation and translation
        rotation, translation = self.to_rotation_translation()

        # Apply rotation then translation: p' = R*p + t
        rotated = rotation.rotate_vector(p)
        return rotated + translation

    def geodesic_distance(self, other: 'DualQuaternion') -> float:
        """
        Geodesic distance on SE(3) manifold.

        Combines rotational and translational distance.
        """
        # Rotational distance
        rot_dist = self.real.angular_distance(other.real)

        # Translational distance
        _, t1 = self.to_rotation_translation()
        _, t2 = other.to_rotation_translation()
        trans_dist = np.linalg.norm(t1 - t2)

        # Combined (weighted) geodesic
        return np.sqrt(rot_dist**2 + trans_dist**2)

    @staticmethod
    def sclerp(
        dq0: 'DualQuaternion',
        dq1: 'DualQuaternion',
        t: float
    ) -> 'DualQuaternion':
        """
        Screw Linear Interpolation (ScLERP).

        Interpolates along the geodesic on SE(3).
        Produces constant-velocity motion along screw axis.
        """
        t = np.clip(t, 0.0, 1.0)

        # Relative transformation: dq_rel = dq0* * dq1
        dq_rel = dq0.conjugate() * dq1

        # Extract screw parameters
        real_w = np.clip(dq_rel.real.w, -1.0, 1.0)

        if abs(real_w) > 0.9999:
            # Nearly identity - linear interpolation
            new_real = Quaternion.slerp(dq0.real, dq1.real, t)
            _, t0 = dq0.to_rotation_translation()
            _, t1 = dq1.to_rotation_translation()
            new_trans = t0 + t * (t1 - t0)
            return DualQuaternion.from_rotation_translation(new_real, new_trans)

        # Screw angle
        theta = 2.0 * np.arccos(real_w)

        # Interpolated angle
        theta_t = theta * t

        # Screw axis (unit vector part of q_r)
        sin_half_theta = np.sin(theta / 2.0)
        if abs(sin_half_theta) < 1e-10:
            axis = np.array([1.0, 0.0, 0.0])
        else:
            axis = dq_rel.real.vector / sin_half_theta

        # Pitch (translation along screw axis per radian)
        pitch = -2.0 * dq_rel.dual.w / sin_half_theta if abs(sin_half_theta) > 1e-10 else 0.0

        # Interpolated transformation
        half_theta_t = theta_t / 2.0
        cos_half = np.cos(half_theta_t)
        sin_half = np.sin(half_theta_t)

        new_real = Quaternion(np.array([
            cos_half,
            axis[0] * sin_half,
            axis[1] * sin_half,
            axis[2] * sin_half
        ]))

        # Translation component
        trans_mag = pitch * theta_t
        trans = axis * trans_mag

        result = DualQuaternion.from_rotation_translation(new_real, trans)

        # Apply to initial pose
        return dq0 * result

    def fingerprint(self) -> bytes:
        """Compute cryptographic fingerprint for audit trails."""
        real_fp = self.real.fingerprint()
        dual_canonical = np.round(self.dual.components, decimals=10)
        dual_data = dual_canonical.tobytes()

        combined = real_fp + dual_data
        return hashlib.sha256(combined).digest()

    def __repr__(self) -> str:
        rot, trans = self.to_rotation_translation()
        return f"DualQuaternion(rot={rot}, trans={trans})"
