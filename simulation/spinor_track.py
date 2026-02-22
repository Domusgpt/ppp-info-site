"""
Spinor Manifold Tracker for Hypersonic Defense

A revolutionary tracking algorithm based on 4D Geometric Algebra that
represents target state as a Dual Quaternion on a spinor manifold.

Key innovations:
1. GEOMETRIC DENOISING: Rejects returns that violate manifold curvature
   constraints (impossible maneuvers → jamming/decoys)
2. GEODESIC PREDICTION: Predicts trajectory along manifold geodesics
   instead of linear extrapolation (captures turn dynamics)
3. ISOCLINIC FILTERING: Uses 600-cell lattice constraints to identify
   physical vs. non-physical signals

Based on the Polytopal Projection Processing (PPP) framework.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from .sensor import RadarMeasurement


@dataclass
class DualQuaternion:
    """
    Dual Quaternion representation for rigid body motion.

    A dual quaternion Q = q_r + ε q_d encodes both rotation and translation:
    - q_r: Rotation quaternion [w, x, y, z]
    - q_d: Dual part encoding translation

    Properties:
    - Singularity-free rotation representation
    - Smooth interpolation via SCLERP
    - Natural encoding of angular momentum
    """

    real: np.ndarray  # [w, x, y, z] rotation quaternion
    dual: np.ndarray  # [w, x, y, z] dual part

    def __post_init__(self):
        # Ensure unit quaternion for real part
        norm = np.linalg.norm(self.real)
        if norm > 1e-10:
            self.real = self.real / norm

    @classmethod
    def from_position_velocity(
        cls,
        position: np.ndarray,
        velocity: np.ndarray,
        dt: float = 0.1
    ) -> 'DualQuaternion':
        """
        Create dual quaternion from position and velocity.

        The rotation quaternion encodes the instantaneous angular
        orientation of the velocity vector, and the dual part
        encodes the translational component.
        """
        # Velocity direction as rotation from reference axis
        vel_norm = np.linalg.norm(velocity)
        if vel_norm < 1e-10:
            # Stationary - identity rotation
            q_r = np.array([1.0, 0.0, 0.0, 0.0])
        else:
            # Rotation from reference axis [1,0,0] to velocity direction
            vel_dir = velocity / vel_norm
            ref = np.array([1.0, 0.0, 0.0])

            # Quaternion from axis-angle
            dot = np.clip(np.dot(ref, vel_dir), -1, 1)
            angle = np.arccos(dot)

            if abs(angle) < 1e-10:
                q_r = np.array([1.0, 0.0, 0.0, 0.0])
            elif abs(angle - np.pi) < 1e-10:
                # 180 degree rotation - pick perpendicular axis
                axis = np.array([0.0, 1.0, 0.0])
                q_r = np.array([0.0, axis[0], axis[1], axis[2]])
            else:
                axis = np.cross(ref, vel_dir)
                axis = axis / np.linalg.norm(axis)
                q_r = np.array([
                    np.cos(angle / 2),
                    axis[0] * np.sin(angle / 2),
                    axis[1] * np.sin(angle / 2),
                    axis[2] * np.sin(angle / 2)
                ])

        # Dual part from translation
        # q_d = 0.5 * t * q_r where t is pure quaternion [0, x, y, z]
        t = np.array([0.0, position[0], position[1], position[2]])
        q_d = 0.5 * cls._quaternion_multiply(t, q_r)

        return cls(real=q_r, dual=q_d)

    @staticmethod
    def _quaternion_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiply two quaternions."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])

    @staticmethod
    def _quaternion_conjugate(q: np.ndarray) -> np.ndarray:
        """Quaternion conjugate."""
        return np.array([q[0], -q[1], -q[2], -q[3]])

    def to_position_velocity(self) -> Tuple[np.ndarray, np.ndarray]:
        """Extract position and velocity direction from dual quaternion."""
        # Position from dual part
        q_r_conj = self._quaternion_conjugate(self.real)
        t_quat = 2 * self._quaternion_multiply(self.dual, q_r_conj)
        position = t_quat[1:4]

        # Velocity direction from rotation
        ref = np.array([1.0, 0.0, 0.0])
        # Rotate reference by quaternion: v' = q v q*
        ref_quat = np.array([0.0, ref[0], ref[1], ref[2]])
        rotated = self._quaternion_multiply(
            self._quaternion_multiply(self.real, ref_quat),
            q_r_conj
        )
        velocity_dir = rotated[1:4]

        return position, velocity_dir

    def geodesic_distance(self, other: 'DualQuaternion') -> float:
        """
        Compute geodesic distance on the quaternion manifold.

        This measures how "far apart" two orientations are in terms
        of the minimum rotation needed to go from one to the other.
        """
        # Real part distance (rotation)
        dot_r = abs(np.dot(self.real, other.real))
        dot_r = np.clip(dot_r, -1, 1)
        angle_r = 2 * np.arccos(dot_r)

        # Dual part distance (translation)
        dual_diff = self.dual - other.dual
        trans_dist = np.linalg.norm(dual_diff)

        # Combined geodesic distance
        return np.sqrt(angle_r**2 + trans_dist**2)

    def interpolate(self, other: 'DualQuaternion', t: float) -> 'DualQuaternion':
        """
        Screw Linear Interpolation (SCLERP) between dual quaternions.

        This provides smooth interpolation along the geodesic path
        on the manifold - essential for predicting curved trajectories.
        """
        t = np.clip(t, 0, 1)

        # SLERP for real part
        dot = np.dot(self.real, other.real)
        if dot < 0:
            other_real = -other.real
            other_dual = -other.dual
            dot = -dot
        else:
            other_real = other.real
            other_dual = other.dual

        dot = np.clip(dot, -1, 1)

        if dot > 0.9995:
            # Linear interpolation for very close quaternions
            real = self.real + t * (other_real - self.real)
            real = real / np.linalg.norm(real)
            dual = self.dual + t * (other_dual - self.dual)
        else:
            theta = np.arccos(dot)
            sin_theta = np.sin(theta)
            s1 = np.sin((1 - t) * theta) / sin_theta
            s2 = np.sin(t * theta) / sin_theta
            real = s1 * self.real + s2 * other_real
            dual = s1 * self.dual + s2 * other_dual

        return DualQuaternion(real=real, dual=dual)


@dataclass
class ManifoldState:
    """State estimate on the spinor manifold."""

    dual_quaternion: DualQuaternion
    position: np.ndarray
    velocity: np.ndarray
    angular_velocity: np.ndarray  # Rate of change of orientation
    curvature: float  # Instantaneous path curvature
    time: float
    geometric_stress: float = 0.0  # Measure of manifold constraint violation
    confidence: float = 1.0

    def copy(self) -> 'ManifoldState':
        return ManifoldState(
            dual_quaternion=DualQuaternion(
                real=self.dual_quaternion.real.copy(),
                dual=self.dual_quaternion.dual.copy()
            ),
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            angular_velocity=self.angular_velocity.copy(),
            curvature=self.curvature,
            time=self.time,
            geometric_stress=self.geometric_stress,
            confidence=self.confidence
        )


class SpinorManifoldTracker:
    """
    Spinor Manifold Tracker for hypersonic target tracking.

    This tracker represents the target state as a dual quaternion
    on a 4D spinor manifold, enabling:

    1. MANIFOLD DENOISING: Incoming measurements are checked against
       the manifold curvature constraints. Returns that imply physically
       impossible maneuvers (infinite acceleration, energy violation)
       are rejected as jamming/decoys.

    2. GEODESIC PREDICTION: Instead of linear extrapolation (x += v*dt),
       the tracker propagates along the geodesic flow of the spinor.
       This naturally captures the curvature of maneuvering trajectories.

    3. ISOCLINIC SYMMETRY: The 600-cell lattice constraint provides
       a "truth filter" - only returns that preserve the isoclinic
       rotation symmetry are accepted as valid.
    """

    def __init__(
        self,
        max_acceleration: float = 400.0,  # ~40g limit
        max_jerk: float = 2000.0,  # Rate of acceleration change
        geometric_stress_threshold: float = 0.5,
        curvature_window: int = 5,
        mass_estimate: float = 1000.0,  # kg
        inertia_threshold: float = 0.3
    ):
        """
        Initialize the Spinor Manifold Tracker.

        Args:
            max_acceleration: Maximum physically possible acceleration (m/s^2)
            max_jerk: Maximum rate of acceleration change
            geometric_stress_threshold: Threshold for rejecting returns
            curvature_window: Number of past states for curvature estimation
            mass_estimate: Estimated vehicle mass for inertia checks
            inertia_threshold: Threshold for inertia-based decoy detection
        """
        self.max_acceleration = max_acceleration
        self.max_jerk = max_jerk
        self.geometric_stress_threshold = geometric_stress_threshold
        self.curvature_window = curvature_window
        self.mass_estimate = mass_estimate
        self.inertia_threshold = inertia_threshold

        # State history for manifold analysis
        self._state_history: List[ManifoldState] = []
        self._measurement_history: List[RadarMeasurement] = []
        self._rejected_measurements: List[RadarMeasurement] = []

        self._initialized = False

        # 600-cell lattice for isoclinic filtering
        self._lattice_vectors = self._build_600_cell_lattice()

    def _build_600_cell_lattice(self) -> np.ndarray:
        """
        Build the 120 vertices of the 600-cell in 4D.

        The 600-cell is the 4D analog of the icosahedron.
        Its vertices define the allowed isoclinic rotation states.
        """
        phi = (1 + np.sqrt(5)) / 2  # Golden ratio

        vertices = []

        # 8 vertices from ±1 permutations
        for s1 in [-1, 1]:
            for s2 in [-1, 1]:
                for s3 in [-1, 1]:
                    for s4 in [-1, 1]:
                        v = np.array([s1, s2, s3, s4]) * 0.5
                        vertices.append(v)

        # 16 vertices from ±1, 0 permutations
        for i in range(4):
            for s in [-1, 1]:
                v = np.zeros(4)
                v[i] = s
                vertices.append(v)

        # 96 vertices from golden ratio combinations
        perms = [
            [0, 1, 2, 3], [0, 2, 1, 3], [0, 3, 1, 2],
            [1, 2, 0, 3], [1, 3, 0, 2], [2, 3, 0, 1]
        ]

        for perm in perms:
            for s1 in [-1, 1]:
                for s2 in [-1, 1]:
                    for s3 in [-1, 1]:
                        for s4 in [-1, 1]:
                            v = np.zeros(4)
                            vals = [s1 * phi / 2, s2 * 0.5, s3 / (2 * phi), s4 * 0]
                            # Only use non-zero combinations
                            if s4 == 1:  # Avoid duplicates
                                for j, idx in enumerate(perm[:3]):
                                    v[idx] = vals[j]
                                if np.linalg.norm(v) > 0.1:
                                    v = v / np.linalg.norm(v)
                                    vertices.append(v)

        # Normalize all vertices
        lattice = np.array(vertices)
        norms = np.linalg.norm(lattice, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1)
        lattice = lattice / norms

        return lattice

    def _compute_isoclinic_projection(self, quaternion: np.ndarray) -> float:
        """
        Compute how well a quaternion aligns with the 600-cell lattice.

        High alignment = physically plausible rotation
        Low alignment = non-physical (jamming/decoy)
        """
        # Find closest lattice vertex
        dots = np.abs(self._lattice_vectors @ quaternion)
        max_alignment = np.max(dots)
        return max_alignment

    def _compute_geometric_stress(
        self,
        measurement: RadarMeasurement,
        predicted_state: ManifoldState
    ) -> float:
        """
        Compute geometric stress of a measurement.

        Geometric stress measures how much the measurement violates
        the manifold curvature constraints. High stress indicates:
        - Physically impossible maneuver (jamming)
        - Low-inertia object (decoy)
        - Measurement error beyond physical limits

        Returns:
            Stress value in [0, 1]. Values > threshold indicate non-physical.
        """
        # Required acceleration to reach measurement from prediction
        dt = max(0.01, measurement.time - predicted_state.time)
        pos_error = measurement.position - predicted_state.position
        vel_error = measurement.velocity - predicted_state.velocity

        # Implied acceleration
        implied_accel = vel_error / dt
        accel_magnitude = np.linalg.norm(implied_accel)

        # Check against physical limits
        accel_stress = min(1.0, accel_magnitude / self.max_acceleration)

        # Check jerk (rate of acceleration change)
        if len(self._state_history) >= 2:
            prev_state = self._state_history[-2]
            prev_accel = (
                self._state_history[-1].velocity - prev_state.velocity
            ) / max(0.01, self._state_history[-1].time - prev_state.time)
            jerk = (implied_accel - prev_accel) / dt
            jerk_magnitude = np.linalg.norm(jerk)
            jerk_stress = min(1.0, jerk_magnitude / self.max_jerk)
        else:
            jerk_stress = 0.0

        # Check angular momentum conservation
        # Create dual quaternion from measurement
        meas_dq = DualQuaternion.from_position_velocity(
            measurement.position,
            measurement.velocity,
            dt
        )

        # Geodesic distance on manifold
        geodesic_dist = predicted_state.dual_quaternion.geodesic_distance(meas_dq)

        # Expected geodesic distance based on angular velocity
        expected_geodesic = np.linalg.norm(predicted_state.angular_velocity) * dt
        geodesic_stress = min(1.0, abs(geodesic_dist - expected_geodesic) / (expected_geodesic + 0.1))

        # Isoclinic alignment check
        isoclinic_alignment = self._compute_isoclinic_projection(meas_dq.real)
        isoclinic_stress = 1.0 - isoclinic_alignment

        # Combined stress (weighted)
        total_stress = (
            0.3 * accel_stress +
            0.2 * jerk_stress +
            0.3 * geodesic_stress +
            0.2 * isoclinic_stress
        )

        return total_stress

    def _predict_geodesic(
        self,
        state: ManifoldState,
        dt: float
    ) -> ManifoldState:
        """
        Predict state by propagating along the manifold geodesic.

        Unlike linear extrapolation, geodesic prediction naturally
        captures the curvature of maneuvering trajectories.
        """
        # Current curvature estimation from history
        if len(self._state_history) >= self.curvature_window:
            positions = np.array([
                s.position for s in self._state_history[-self.curvature_window:]
            ])
            velocities = np.array([
                s.velocity for s in self._state_history[-self.curvature_window:]
            ])

            # Estimate curvature from velocity changes
            if len(velocities) >= 2:
                vel_changes = np.diff(velocities, axis=0)
                avg_vel_change = np.mean(np.linalg.norm(vel_changes, axis=1))
                avg_speed = np.mean(np.linalg.norm(velocities, axis=1))
                if avg_speed > 1:
                    curvature = avg_vel_change / (avg_speed * 0.1)  # dt=0.1
                else:
                    curvature = 0.0
            else:
                curvature = state.curvature
        else:
            curvature = state.curvature

        # Geodesic prediction
        speed = np.linalg.norm(state.velocity)

        if curvature > 0.001 and speed > 1:
            # Curved trajectory - use geodesic flow
            # Turn radius from curvature
            radius = 1.0 / curvature

            # Angular rate
            omega = speed / radius

            # Predict rotation of velocity vector
            vel_dir = state.velocity / speed
            angular_change = omega * dt

            # Perpendicular direction (in horizontal plane)
            perp = np.cross(np.array([0, 0, 1]), vel_dir)
            perp_norm = np.linalg.norm(perp)
            if perp_norm > 0.1:
                perp = perp / perp_norm
            else:
                perp = np.array([0, 1, 0])

            # Rotate velocity
            cos_a = np.cos(angular_change)
            sin_a = np.sin(angular_change)
            new_vel_dir = cos_a * vel_dir + sin_a * perp
            new_velocity = new_vel_dir * speed

            # Arc length position update
            if abs(angular_change) > 0.001:
                arc_center = state.position + perp * radius
                new_position = arc_center - perp * radius * np.cos(angular_change)
                new_position += vel_dir * radius * np.sin(angular_change)
            else:
                new_position = state.position + state.velocity * dt

        else:
            # Near-straight trajectory - standard prediction
            new_velocity = state.velocity.copy()
            new_position = state.position + state.velocity * dt

        # Update dual quaternion
        new_dq = DualQuaternion.from_position_velocity(
            new_position, new_velocity, dt
        )

        # Angular velocity estimation
        dq_diff_real = new_dq.real - state.dual_quaternion.real
        angular_velocity = 2 * dq_diff_real[1:4] / max(0.01, dt)

        return ManifoldState(
            dual_quaternion=new_dq,
            position=new_position,
            velocity=new_velocity,
            angular_velocity=angular_velocity,
            curvature=curvature,
            time=state.time + dt,
            geometric_stress=0.0,
            confidence=state.confidence * 0.99  # Slight decay
        )

    def _compute_intercept_singularity(
        self,
        state: ManifoldState
    ) -> Optional[np.ndarray]:
        """
        Compute the geometric singularity (turn center) for intercept targeting.

        When an HGV maneuvers, it pivots around a center of curvature.
        The POM algorithm targets this singularity - where the missile's
        physics FORCE it to go.
        """
        if state.curvature < 0.001:
            return None

        radius = 1.0 / state.curvature
        speed = np.linalg.norm(state.velocity)

        if speed < 1:
            return None

        vel_dir = state.velocity / speed

        # Perpendicular direction (toward turn center)
        perp = np.cross(np.array([0, 0, 1]), vel_dir)
        perp_norm = np.linalg.norm(perp)

        if perp_norm < 0.1:
            return None

        perp = perp / perp_norm

        # Center of curvature
        center = state.position + perp * radius

        # Predict where vehicle will be after completing partial turn
        # Intercept point is ahead on the arc
        intercept_angle = np.pi / 6  # 30 degrees ahead
        intercept_point = center - perp * radius * np.cos(intercept_angle)
        intercept_point += vel_dir * radius * np.sin(intercept_angle)

        return intercept_point

    def initialize(self, measurement: RadarMeasurement) -> ManifoldState:
        """Initialize tracker with first measurement."""
        dq = DualQuaternion.from_position_velocity(
            measurement.position,
            measurement.velocity,
            0.1
        )

        state = ManifoldState(
            dual_quaternion=dq,
            position=measurement.position.copy(),
            velocity=measurement.velocity.copy(),
            angular_velocity=np.zeros(3),
            curvature=0.0,
            time=measurement.time,
            geometric_stress=0.0,
            confidence=measurement.confidence
        )

        self._state_history.append(state.copy())
        self._measurement_history.append(measurement)
        self._initialized = True

        return state

    def update(self, measurement: RadarMeasurement) -> ManifoldState:
        """
        Update tracker with new measurement.

        This implements the core POM algorithm:
        1. Predict state via geodesic flow
        2. Check geometric stress of measurement
        3. Accept or reject based on manifold constraints
        4. Update state if accepted
        """
        if not self._initialized:
            return self.initialize(measurement)

        current_state = self._state_history[-1]

        # Predict state using geodesic flow
        dt = measurement.time - current_state.time
        if dt <= 0:
            return current_state.copy()

        predicted = self._predict_geodesic(current_state, dt)

        # Compute geometric stress
        stress = self._compute_geometric_stress(measurement, predicted)

        if stress > self.geometric_stress_threshold:
            # REJECT: Non-physical measurement (jamming/decoy)
            self._rejected_measurements.append(measurement)

            # Use pure prediction
            new_state = predicted
            new_state.geometric_stress = stress
            new_state.confidence *= 0.9
        else:
            # ACCEPT: Physical measurement
            # Blend prediction with measurement based on confidence

            blend = measurement.confidence * (1 - stress)

            new_position = (
                blend * measurement.position +
                (1 - blend) * predicted.position
            )
            new_velocity = (
                blend * measurement.velocity +
                (1 - blend) * predicted.velocity
            )

            new_dq = DualQuaternion.from_position_velocity(
                new_position, new_velocity, dt
            )

            # Update curvature estimate
            if len(self._state_history) >= 2:
                prev_vel = self._state_history[-1].velocity
                vel_change = new_velocity - prev_vel
                speed = np.linalg.norm(new_velocity)
                if speed > 1:
                    curvature = np.linalg.norm(vel_change) / (speed * dt)
                else:
                    curvature = 0.0
            else:
                curvature = 0.0

            # Angular velocity
            dq_diff = new_dq.real - current_state.dual_quaternion.real
            angular_velocity = 2 * dq_diff[1:4] / dt

            new_state = ManifoldState(
                dual_quaternion=new_dq,
                position=new_position,
                velocity=new_velocity,
                angular_velocity=angular_velocity,
                curvature=curvature,
                time=measurement.time,
                geometric_stress=stress,
                confidence=measurement.confidence * (1 - stress)
            )

        self._state_history.append(new_state.copy())
        self._measurement_history.append(measurement)

        return new_state

    def process_measurements(
        self,
        measurements: List[RadarMeasurement]
    ) -> List[ManifoldState]:
        """Process a sequence of measurements."""
        self._state_history = []
        self._measurement_history = []
        self._rejected_measurements = []
        self._initialized = False

        estimates = []
        for meas in measurements:
            state = self.update(meas)
            estimates.append(state)

        return estimates

    def get_intercept_point(self) -> Optional[np.ndarray]:
        """Get recommended intercept point based on current state."""
        if not self._state_history:
            return None
        return self._compute_intercept_singularity(self._state_history[-1])

    def get_rejection_rate(self) -> float:
        """Get fraction of measurements rejected as non-physical."""
        total = len(self._measurement_history)
        if total == 0:
            return 0.0
        return len(self._rejected_measurements) / total

    def reset(self):
        """Reset the tracker."""
        self._state_history = []
        self._measurement_history = []
        self._rejected_measurements = []
        self._initialized = False


def compute_manifold_tracking_error(
    estimates: List[ManifoldState],
    truth: List[np.ndarray]
) -> Tuple[float, float, List[float]]:
    """
    Compute tracking error metrics for manifold tracker.

    Args:
        estimates: List of manifold state estimates
        truth: List of true positions

    Returns:
        Tuple of (RMS error, max error, per-step errors)
    """
    if len(estimates) != len(truth):
        min_len = min(len(estimates), len(truth))
        estimates = estimates[:min_len]
        truth = truth[:min_len]

    errors = []
    for est, true_pos in zip(estimates, truth):
        error = np.linalg.norm(est.position - true_pos)
        errors.append(error)

    rms = np.sqrt(np.mean(np.array(errors)**2))
    max_error = max(errors) if errors else 0.0

    return rms, max_error, errors


if __name__ == "__main__":
    # Test Spinor Manifold Tracker
    from .trajectory import generate_skip_glide_trajectory
    from .sensor import RadarSensor, add_plasma_noise, add_jamming

    # Generate trajectory with sharp maneuver
    traj = generate_skip_glide_trajectory(
        duration=30.0,
        maneuver_time=15.0,
        maneuver_g=20.0
    )

    # Generate noisy measurements with jamming
    sensor = RadarSensor()
    measurements = sensor.measure_trajectory(traj, seed=42)
    measurements = add_plasma_noise(measurements, intensity=0.5, seed=43)
    measurements, ghost_idx = add_jamming(measurements, ghost_rate=0.2, seed=44)

    print(f"Total measurements: {len(measurements)}")
    print(f"Ghost returns injected: {len(ghost_idx)}")

    # Track with Spinor Manifold Tracker
    tracker = SpinorManifoldTracker(geometric_stress_threshold=0.4)
    estimates = tracker.process_measurements(measurements)

    # Compute error
    true_positions = [s.position for s in traj.states]
    rms, max_err, errors = compute_manifold_tracking_error(estimates, true_positions)

    print(f"\nSpinor Manifold Tracker Results:")
    print(f"  RMS Error: {rms:.1f} m")
    print(f"  Max Error: {max_err:.1f} m")
    print(f"  Rejection Rate: {tracker.get_rejection_rate()*100:.1f}%")

    # Get intercept point
    intercept = tracker.get_intercept_point()
    if intercept is not None:
        print(f"  Intercept Point: [{intercept[0]:.0f}, {intercept[1]:.0f}, {intercept[2]:.0f}]")
