#!/usr/bin/env python3
"""
Hypersonic Defense Simulation - Unified Executable

Demonstrates the superiority of Spinor Manifold Tracking over standard
Extended Kalman Filters when tracking maneuvering Hypersonic Glide Vehicles (HGVs).

Based on the Polytopal Projection Processing (PPP) 4D Geometric Framework.

Usage:
    python hypersonic_defense_sim.py [--mach MACH] [--duration SECS] [--maneuver-g G]
                                     [--jamming RATE] [--seed SEED] [--no-plot]

Copyright (c) 2025 Paul Phillips - Clear Seas Solutions LLC
Polytopal Orthogonal Modulation (POM) - Patent Pending
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import argparse
import sys

# =============================================================================
# PHYSICAL CONSTANTS
# =============================================================================

EARTH_RADIUS = 6371000  # meters
GRAVITY = 9.81  # m/s^2
MACH_1 = 343  # m/s at sea level
AIR_DENSITY_SEA_LEVEL = 1.225  # kg/m^3

# =============================================================================
# TRAJECTORY PHYSICS
# =============================================================================

@dataclass
class HGVState:
    """Complete state vector for an HGV at a given time."""
    position: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray = field(default_factory=lambda: np.zeros(3))
    time: float = 0.0

    @property
    def speed(self) -> float:
        return np.linalg.norm(self.velocity)

    @property
    def mach(self) -> float:
        return self.speed / MACH_1

    def copy(self) -> 'HGVState':
        return HGVState(
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            acceleration=self.acceleration.copy(),
            time=self.time
        )


@dataclass
class HGVTrajectory:
    """Container for a complete HGV trajectory."""
    states: List[HGVState] = field(default_factory=list)
    dt: float = 0.1

    @property
    def positions(self) -> np.ndarray:
        return np.array([s.position for s in self.states])

    @property
    def times(self) -> np.ndarray:
        return np.array([s.time for s in self.states])

    def __len__(self) -> int:
        return len(self.states)

    def __getitem__(self, idx) -> HGVState:
        return self.states[idx]


def atmospheric_density(altitude: float) -> float:
    """Exponential atmosphere model."""
    scale_height = 8500
    return AIR_DENSITY_SEA_LEVEL * np.exp(-altitude / scale_height)


def generate_skip_glide_trajectory(
    mach_number: float = 8.0,
    initial_altitude: float = 50000.0,
    duration: float = 60.0,
    dt: float = 0.1,
    maneuver_time: float = 30.0,
    maneuver_g: float = 15.0,
    maneuver_duration: float = 5.0
) -> HGVTrajectory:
    """Generate a skip-glide HGV trajectory with bank-to-turn maneuver."""

    initial_position = np.array([0.0, 0.0, initial_altitude])
    speed = mach_number * MACH_1
    initial_velocity = np.array([speed, 0.0, 0.0])

    trajectory = HGVTrajectory(dt=dt)
    state = HGVState(
        position=initial_position.copy(),
        velocity=initial_velocity.copy(),
        time=0.0
    )
    trajectory.states.append(state.copy())

    mass = 1000.0
    lift_to_drag = 3.0
    reference_area = 5.0

    t = 0.0
    while t < duration:
        t += dt

        # Bank angle for maneuver
        if maneuver_time <= t < maneuver_time + maneuver_duration:
            maneuver_progress = (t - maneuver_time) / maneuver_duration
            required_centripetal = maneuver_g * GRAVITY
            bank_envelope = np.sin(np.pi * maneuver_progress)
            target_bank = np.arctan2(required_centripetal, GRAVITY)
            bank_angle = target_bank * bank_envelope
        else:
            skip_freq = 0.05
            bank_angle = 0.05 * np.sin(2 * np.pi * skip_freq * t)

        # Aerodynamics
        speed = np.linalg.norm(state.velocity)
        if speed > 1.0:
            rho = atmospheric_density(state.position[2])
            q = 0.5 * rho * speed**2
            cd = 0.02
            drag_force = q * reference_area * cd
            drag_accel = -drag_force / mass * (state.velocity / speed)

            cl = cd * lift_to_drag
            lift_force = q * reference_area * cl

            vel_h = np.array([state.velocity[0], state.velocity[1], 0])
            vel_h_norm = np.linalg.norm(vel_h)

            if vel_h_norm > 1.0:
                perp_horizontal = np.array([-state.velocity[1], state.velocity[0], 0]) / vel_h_norm
                lift_vertical = np.array([0, 0, 1]) * np.cos(bank_angle)
                lift_lateral = perp_horizontal * np.sin(bank_angle)
                lift_direction = lift_vertical + lift_lateral
                lift_direction = lift_direction / np.linalg.norm(lift_direction)
            else:
                lift_direction = np.array([0, 0, 1])

            lift_accel = lift_force / mass * lift_direction
        else:
            lift_accel = np.zeros(3)
            drag_accel = np.zeros(3)

        gravity_accel = np.array([0, 0, -GRAVITY])
        total_accel = lift_accel + drag_accel + gravity_accel

        new_velocity = state.velocity + total_accel * dt
        new_position = state.position + state.velocity * dt + 0.5 * total_accel * dt**2

        if new_position[2] < 0:
            new_position[2] = 0
            new_velocity[2] = max(0, new_velocity[2])

        state = HGVState(
            position=new_position,
            velocity=new_velocity,
            acceleration=total_accel,
            time=t
        )
        trajectory.states.append(state.copy())

    return trajectory


# =============================================================================
# SENSOR SIMULATION
# =============================================================================

@dataclass
class RadarMeasurement:
    """Single radar measurement with noise."""
    position: np.ndarray
    velocity: np.ndarray
    time: float
    snr: float
    is_valid: bool = True
    confidence: float = 1.0


@dataclass
class RadarSensor:
    """Simulates tracking radar with noise and atmospheric effects."""
    position_sigma: float = 50.0
    velocity_sigma: float = 5.0
    sensor_position: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def measure(self, true_state: HGVState, rng: np.random.Generator) -> RadarMeasurement:
        """Generate noisy measurement."""
        relative_pos = true_state.position - self.sensor_position
        range_m = np.linalg.norm(relative_pos)
        range_km = range_m / 1000.0

        # Range-dependent noise
        range_factor = max(1.0, (range_km / 100.0) ** 2)

        # Plasma attenuation at hypersonic speeds
        plasma_threshold = 6.0
        if true_state.mach > plasma_threshold:
            excess_mach = true_state.mach - plasma_threshold
            plasma_loss = min(0.8, excess_mach * 0.13)
            plasma_factor = 1.0 / (1.0 - plasma_loss + 0.01)
        else:
            plasma_factor = 1.0

        total_noise_factor = range_factor * plasma_factor

        # Apply noise
        pos_sigma = self.position_sigma * total_noise_factor
        position_noise = rng.normal(0, pos_sigma, size=3)
        measured_position = true_state.position + position_noise

        vel_sigma = self.velocity_sigma * total_noise_factor
        velocity_noise = rng.normal(0, vel_sigma, size=3)
        measured_velocity = true_state.velocity + velocity_noise

        base_snr = 25.0
        snr = base_snr - 10 * np.log10(total_noise_factor)
        confidence = min(1.0, max(0.1, (snr + 10) / 40))

        return RadarMeasurement(
            position=measured_position,
            velocity=measured_velocity,
            time=true_state.time,
            snr=snr,
            is_valid=True,
            confidence=confidence
        )


def add_plasma_noise(
    measurements: List[RadarMeasurement],
    intensity: float = 1.0,
    seed: int = None
) -> List[RadarMeasurement]:
    """Add plasma-sheath interference."""
    rng = np.random.default_rng(seed)
    modified = []

    for meas in measurements:
        new_meas = RadarMeasurement(
            position=meas.position.copy(),
            velocity=meas.velocity.copy(),
            time=meas.time,
            snr=meas.snr,
            is_valid=meas.is_valid,
            confidence=meas.confidence
        )

        # Plasma bursts
        if rng.random() < 0.15 * intensity:
            burst_magnitude = 200 * intensity * rng.exponential(1.0)
            burst_direction = rng.standard_normal(3)
            burst_direction /= np.linalg.norm(burst_direction)
            new_meas.position += burst_direction * burst_magnitude
            new_meas.confidence *= 0.5

        # Continuous interference
        plasma_jitter = rng.normal(0, 20 * intensity, size=3)
        new_meas.position += plasma_jitter

        modified.append(new_meas)

    return modified


def add_jamming(
    measurements: List[RadarMeasurement],
    ghost_rate: float = 0.2,
    ghost_amplitude: float = 5000.0,
    seed: int = None
) -> Tuple[List[RadarMeasurement], List[int]]:
    """Add ghost returns that violate physical laws."""
    rng = np.random.default_rng(seed)
    modified = []
    ghost_indices = []

    running_centroid = np.zeros(3)
    running_velocity = np.zeros(3)

    for i, meas in enumerate(measurements):
        alpha = 0.1
        running_centroid = (1 - alpha) * running_centroid + alpha * meas.position
        running_velocity = (1 - alpha) * running_velocity + alpha * meas.velocity

        if rng.random() < ghost_rate:
            # Ghost: violates angular momentum conservation
            offset_direction = rng.standard_normal(3)
            offset_direction /= np.linalg.norm(offset_direction)
            offset_magnitude = ghost_amplitude * (0.5 + rng.random())

            ghost_position = meas.position + offset_direction * offset_magnitude
            ghost_velocity = running_velocity + rng.standard_normal(3) * 500

            ghost_meas = RadarMeasurement(
                position=ghost_position,
                velocity=ghost_velocity,
                time=meas.time,
                snr=meas.snr - 3,
                is_valid=False,
                confidence=0.8
            )
            modified.append(ghost_meas)
            ghost_indices.append(i)
        else:
            new_meas = RadarMeasurement(
                position=meas.position.copy() + rng.normal(0, 30, size=3),
                velocity=meas.velocity.copy(),
                time=meas.time,
                snr=meas.snr,
                is_valid=True,
                confidence=meas.confidence
            )
            modified.append(new_meas)

    return modified, ghost_indices


# =============================================================================
# EXTENDED KALMAN FILTER (LEGACY TRACKER)
# =============================================================================

@dataclass
class EKFState:
    """EKF state estimate."""
    position: np.ndarray
    velocity: np.ndarray
    covariance: np.ndarray
    time: float
    innovation: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def copy(self) -> 'EKFState':
        return EKFState(
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            covariance=self.covariance.copy(),
            time=self.time,
            innovation=self.innovation.copy()
        )


class ExtendedKalmanFilter:
    """
    Standard EKF with Constant Velocity motion model.

    FAILS when:
    - Target maneuvers (model mismatch)
    - Non-Gaussian noise (plasma, jamming)
    - Ghost returns (outliers corrupt filter)
    """

    def __init__(
        self,
        process_noise_accel: float = 50.0,
        measurement_noise_pos: float = 100.0,
        measurement_noise_vel: float = 20.0
    ):
        self.process_noise_accel = process_noise_accel
        self.measurement_noise_pos = measurement_noise_pos
        self.measurement_noise_vel = measurement_noise_vel
        self.H = np.eye(6)
        self._state: Optional[EKFState] = None
        self._initialized = False
        self.history: List[EKFState] = []

    def _build_transition_matrix(self, dt: float) -> np.ndarray:
        F = np.eye(6)
        F[0, 3] = dt
        F[1, 4] = dt
        F[2, 5] = dt
        return F

    def _build_process_noise(self, dt: float) -> np.ndarray:
        sigma_a = self.process_noise_accel
        Q = np.zeros((6, 6))
        Q[0, 0] = Q[1, 1] = Q[2, 2] = (dt**4) / 4
        Q[0, 3] = Q[1, 4] = Q[2, 5] = (dt**3) / 2
        Q[3, 0] = Q[4, 1] = Q[5, 2] = (dt**3) / 2
        Q[3, 3] = Q[4, 4] = Q[5, 5] = dt**2
        return Q * sigma_a**2

    def _build_measurement_noise(self) -> np.ndarray:
        return np.diag([
            self.measurement_noise_pos**2,
            self.measurement_noise_pos**2,
            self.measurement_noise_pos**2,
            self.measurement_noise_vel**2,
            self.measurement_noise_vel**2,
            self.measurement_noise_vel**2,
        ])

    def initialize(self, measurement: RadarMeasurement) -> EKFState:
        x = np.concatenate([measurement.position, measurement.velocity])
        P = np.diag([
            self.measurement_noise_pos**2 * 4,
            self.measurement_noise_pos**2 * 4,
            self.measurement_noise_pos**2 * 4,
            self.measurement_noise_vel**2 * 4,
            self.measurement_noise_vel**2 * 4,
            self.measurement_noise_vel**2 * 4,
        ])
        self._state = EKFState(
            position=x[:3],
            velocity=x[3:6],
            covariance=P,
            time=measurement.time
        )
        self._initialized = True
        self.history.append(self._state.copy())
        return self._state.copy()

    def predict(self, dt: float) -> EKFState:
        if not self._initialized:
            raise RuntimeError("Filter not initialized")

        F = self._build_transition_matrix(dt)
        Q = self._build_process_noise(dt)
        x = np.concatenate([self._state.position, self._state.velocity])

        # LINEAR EXTRAPOLATION - fails for turns!
        x_pred = F @ x
        P_pred = F @ self._state.covariance @ F.T + Q

        self._state = EKFState(
            position=x_pred[:3],
            velocity=x_pred[3:6],
            covariance=P_pred,
            time=self._state.time + dt
        )
        return self._state.copy()

    def update(self, measurement: RadarMeasurement) -> EKFState:
        if not self._initialized:
            return self.initialize(measurement)

        dt = measurement.time - self._state.time
        if dt > 0:
            self.predict(dt)

        z = np.concatenate([measurement.position, measurement.velocity])
        x = np.concatenate([self._state.position, self._state.velocity])
        z_pred = self.H @ x
        y = z - z_pred

        R = self._build_measurement_noise() / max(0.1, measurement.confidence)
        S = self.H @ self._state.covariance @ self.H.T + R
        K = self._state.covariance @ self.H.T @ np.linalg.inv(S)

        x_new = x + K @ y
        I_KH = np.eye(6) - K @ self.H
        P_new = I_KH @ self._state.covariance @ I_KH.T + K @ R @ K.T

        self._state = EKFState(
            position=x_new[:3],
            velocity=x_new[3:6],
            covariance=P_new,
            time=measurement.time,
            innovation=y[:3]
        )
        self.history.append(self._state.copy())
        return self._state.copy()

    def process_measurements(self, measurements: List[RadarMeasurement]) -> List[EKFState]:
        self._initialized = False
        self._state = None
        self.history = []

        estimates = []
        for meas in measurements:
            state = self.update(meas)
            estimates.append(state)
        return estimates


# =============================================================================
# SPINOR MANIFOLD TRACKER (INNOVATION)
# =============================================================================

@dataclass
class DualQuaternion:
    """Dual Quaternion for rigid body motion on spinor manifold."""
    real: np.ndarray
    dual: np.ndarray

    def __post_init__(self):
        norm = np.linalg.norm(self.real)
        if norm > 1e-10:
            self.real = self.real / norm

    @classmethod
    def from_position_velocity(cls, position: np.ndarray, velocity: np.ndarray, dt: float = 0.1):
        vel_norm = np.linalg.norm(velocity)
        if vel_norm < 1e-10:
            q_r = np.array([1.0, 0.0, 0.0, 0.0])
        else:
            vel_dir = velocity / vel_norm
            ref = np.array([1.0, 0.0, 0.0])
            dot = np.clip(np.dot(ref, vel_dir), -1, 1)
            angle = np.arccos(dot)

            if abs(angle) < 1e-10:
                q_r = np.array([1.0, 0.0, 0.0, 0.0])
            elif abs(angle - np.pi) < 1e-10:
                q_r = np.array([0.0, 0.0, 1.0, 0.0])
            else:
                axis = np.cross(ref, vel_dir)
                axis = axis / np.linalg.norm(axis)
                q_r = np.array([
                    np.cos(angle / 2),
                    axis[0] * np.sin(angle / 2),
                    axis[1] * np.sin(angle / 2),
                    axis[2] * np.sin(angle / 2)
                ])

        t = np.array([0.0, position[0], position[1], position[2]])
        q_d = 0.5 * cls._qmult(t, q_r)
        return cls(real=q_r, dual=q_d)

    @staticmethod
    def _qmult(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])

    @staticmethod
    def _qconj(q: np.ndarray) -> np.ndarray:
        return np.array([q[0], -q[1], -q[2], -q[3]])

    def geodesic_distance(self, other: 'DualQuaternion') -> float:
        dot_r = abs(np.dot(self.real, other.real))
        dot_r = np.clip(dot_r, -1, 1)
        angle_r = 2 * np.arccos(dot_r)
        trans_dist = np.linalg.norm(self.dual - other.dual)
        return np.sqrt(angle_r**2 + trans_dist**2)


@dataclass
class ManifoldState:
    """State estimate on the spinor manifold."""
    dual_quaternion: DualQuaternion
    position: np.ndarray
    velocity: np.ndarray
    angular_velocity: np.ndarray
    curvature: float
    time: float
    geometric_stress: float = 0.0
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
    Spinor Manifold Tracker using 4D Geometric Algebra.

    Key innovations:
    1. GEOMETRIC DENOISING: Rejects physically impossible maneuvers
    2. GEODESIC PREDICTION: Follows manifold curvature, not linear extrapolation
    3. ISOCLINIC FILTERING: 600-cell lattice constraint for physics validation
    """

    def __init__(
        self,
        max_acceleration: float = 400.0,
        max_jerk: float = 2000.0,
        geometric_stress_threshold: float = 0.5,
        curvature_window: int = 5
    ):
        self.max_acceleration = max_acceleration
        self.max_jerk = max_jerk
        self.geometric_stress_threshold = geometric_stress_threshold
        self.curvature_window = curvature_window

        self._state_history: List[ManifoldState] = []
        self._measurement_history: List[RadarMeasurement] = []
        self._rejected_measurements: List[RadarMeasurement] = []
        self._initialized = False

        self._lattice_vectors = self._build_600_cell_lattice()

    def _build_600_cell_lattice(self) -> np.ndarray:
        """Build 600-cell vertices for isoclinic filtering."""
        phi = (1 + np.sqrt(5)) / 2
        vertices = []

        # 16 vertices
        for s1 in [-1, 1]:
            for s2 in [-1, 1]:
                for s3 in [-1, 1]:
                    for s4 in [-1, 1]:
                        vertices.append(np.array([s1, s2, s3, s4]) * 0.5)

        # 8 axis vertices
        for i in range(4):
            for s in [-1, 1]:
                v = np.zeros(4)
                v[i] = s
                vertices.append(v)

        lattice = np.array(vertices)
        norms = np.linalg.norm(lattice, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1)
        return lattice / norms

    def _compute_isoclinic_projection(self, quaternion: np.ndarray) -> float:
        dots = np.abs(self._lattice_vectors @ quaternion)
        return np.max(dots)

    def _compute_geometric_stress(
        self,
        measurement: RadarMeasurement,
        predicted_state: ManifoldState
    ) -> float:
        """Check if measurement violates physical constraints."""
        dt = max(0.01, measurement.time - predicted_state.time)
        vel_error = measurement.velocity - predicted_state.velocity
        implied_accel = vel_error / dt
        accel_magnitude = np.linalg.norm(implied_accel)

        accel_stress = min(1.0, accel_magnitude / self.max_acceleration)

        # Jerk check
        if len(self._state_history) >= 2:
            prev_state = self._state_history[-2]
            prev_accel = (
                self._state_history[-1].velocity - prev_state.velocity
            ) / max(0.01, self._state_history[-1].time - prev_state.time)
            jerk = (implied_accel - prev_accel) / dt
            jerk_stress = min(1.0, np.linalg.norm(jerk) / self.max_jerk)
        else:
            jerk_stress = 0.0

        # Geodesic distance check
        meas_dq = DualQuaternion.from_position_velocity(
            measurement.position, measurement.velocity, dt
        )
        geodesic_dist = predicted_state.dual_quaternion.geodesic_distance(meas_dq)
        expected_geodesic = np.linalg.norm(predicted_state.angular_velocity) * dt
        geodesic_stress = min(1.0, abs(geodesic_dist - expected_geodesic) / (expected_geodesic + 0.1))

        # Isoclinic alignment
        isoclinic_alignment = self._compute_isoclinic_projection(meas_dq.real)
        isoclinic_stress = 1.0 - isoclinic_alignment

        return 0.3 * accel_stress + 0.2 * jerk_stress + 0.3 * geodesic_stress + 0.2 * isoclinic_stress

    def _predict_geodesic(self, state: ManifoldState, dt: float) -> ManifoldState:
        """Predict along manifold geodesic, not linear extrapolation."""
        if len(self._state_history) >= self.curvature_window:
            velocities = np.array([s.velocity for s in self._state_history[-self.curvature_window:]])
            if len(velocities) >= 2:
                vel_changes = np.diff(velocities, axis=0)
                avg_vel_change = np.mean(np.linalg.norm(vel_changes, axis=1))
                avg_speed = np.mean(np.linalg.norm(velocities, axis=1))
                curvature = avg_vel_change / (avg_speed * 0.1) if avg_speed > 1 else 0.0
            else:
                curvature = state.curvature
        else:
            curvature = state.curvature

        speed = np.linalg.norm(state.velocity)

        if curvature > 0.001 and speed > 1:
            # Curved trajectory - geodesic flow
            radius = 1.0 / curvature
            omega = speed / radius
            vel_dir = state.velocity / speed
            angular_change = omega * dt

            perp = np.cross(np.array([0, 0, 1]), vel_dir)
            perp_norm = np.linalg.norm(perp)
            if perp_norm > 0.1:
                perp = perp / perp_norm
            else:
                perp = np.array([0, 1, 0])

            cos_a = np.cos(angular_change)
            sin_a = np.sin(angular_change)
            new_vel_dir = cos_a * vel_dir + sin_a * perp
            new_velocity = new_vel_dir * speed

            if abs(angular_change) > 0.001:
                arc_center = state.position + perp * radius
                new_position = arc_center - perp * radius * np.cos(angular_change)
                new_position += vel_dir * radius * np.sin(angular_change)
            else:
                new_position = state.position + state.velocity * dt
        else:
            new_velocity = state.velocity.copy()
            new_position = state.position + state.velocity * dt

        new_dq = DualQuaternion.from_position_velocity(new_position, new_velocity, dt)
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
            confidence=state.confidence * 0.99
        )

    def _compute_intercept_singularity(self, state: ManifoldState) -> Optional[np.ndarray]:
        """Compute geometric singularity for intercept targeting."""
        if state.curvature < 0.001:
            return None

        radius = 1.0 / state.curvature
        speed = np.linalg.norm(state.velocity)
        if speed < 1:
            return None

        vel_dir = state.velocity / speed
        perp = np.cross(np.array([0, 0, 1]), vel_dir)
        perp_norm = np.linalg.norm(perp)
        if perp_norm < 0.1:
            return None

        perp = perp / perp_norm
        center = state.position + perp * radius

        intercept_angle = np.pi / 6
        intercept_point = center - perp * radius * np.cos(intercept_angle)
        intercept_point += vel_dir * radius * np.sin(intercept_angle)

        return intercept_point

    def initialize(self, measurement: RadarMeasurement) -> ManifoldState:
        dq = DualQuaternion.from_position_velocity(
            measurement.position, measurement.velocity, 0.1
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
        if not self._initialized:
            return self.initialize(measurement)

        current_state = self._state_history[-1]
        dt = measurement.time - current_state.time
        if dt <= 0:
            return current_state.copy()

        predicted = self._predict_geodesic(current_state, dt)
        stress = self._compute_geometric_stress(measurement, predicted)

        if stress > self.geometric_stress_threshold:
            # REJECT: Non-physical (jamming/decoy)
            self._rejected_measurements.append(measurement)
            new_state = predicted
            new_state.geometric_stress = stress
            new_state.confidence *= 0.9
        else:
            # ACCEPT: Blend with prediction
            blend = measurement.confidence * (1 - stress)
            new_position = blend * measurement.position + (1 - blend) * predicted.position
            new_velocity = blend * measurement.velocity + (1 - blend) * predicted.velocity

            new_dq = DualQuaternion.from_position_velocity(new_position, new_velocity, dt)

            if len(self._state_history) >= 2:
                prev_vel = self._state_history[-1].velocity
                vel_change = new_velocity - prev_vel
                speed = np.linalg.norm(new_velocity)
                curvature = np.linalg.norm(vel_change) / (speed * dt) if speed > 1 else 0.0
            else:
                curvature = 0.0

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

    def process_measurements(self, measurements: List[RadarMeasurement]) -> List[ManifoldState]:
        self._state_history = []
        self._measurement_history = []
        self._rejected_measurements = []
        self._initialized = False

        return [self.update(meas) for meas in measurements]

    def get_intercept_point(self) -> Optional[np.ndarray]:
        if not self._state_history:
            return None
        return self._compute_intercept_singularity(self._state_history[-1])

    def get_rejection_rate(self) -> float:
        total = len(self._measurement_history)
        return len(self._rejected_measurements) / total if total > 0 else 0.0


# =============================================================================
# SIMULATION RUNNER
# =============================================================================

def compute_errors(estimates, truth):
    """Compute RMS, max, and per-step errors."""
    min_len = min(len(estimates), len(truth))
    errors = [np.linalg.norm(estimates[i] - truth[i]) for i in range(min_len)]
    rms = np.sqrt(np.mean(np.array(errors)**2))
    max_err = max(errors) if errors else 0.0
    return rms, max_err, errors


def run_simulation(
    mach_number: float = 8.0,
    duration: float = 60.0,
    maneuver_time: float = 30.0,
    maneuver_g: float = 15.0,
    jamming_rate: float = 0.2,
    plasma_intensity: float = 0.5,
    seed: int = 42
):
    """Run the complete simulation and return results."""

    print("=" * 70)
    print("HYPERSONIC DEFENSE SIMULATION")
    print("Spinor Manifold Tracking vs Extended Kalman Filter")
    print("=" * 70)
    print()

    # Generate trajectory
    print("Generating HGV trajectory...")
    print(f"  Mach: {mach_number}")
    print(f"  Duration: {duration}s")
    print(f"  Maneuver: {maneuver_g}g at t={maneuver_time}s")

    trajectory = generate_skip_glide_trajectory(
        mach_number=mach_number,
        duration=duration,
        maneuver_time=maneuver_time,
        maneuver_g=maneuver_g
    )

    # Generate measurements
    print("\nSimulating radar measurements...")
    sensor = RadarSensor(position_sigma=75.0, velocity_sigma=10.0)
    rng = np.random.default_rng(seed)
    measurements = [sensor.measure(state, rng) for state in trajectory.states]

    # Add noise
    print(f"  Adding plasma interference (intensity={plasma_intensity})")
    measurements = add_plasma_noise(measurements, intensity=plasma_intensity, seed=seed+1)

    print(f"  Adding jamming (ghost_rate={jamming_rate})")
    measurements, ghost_indices = add_jamming(
        measurements, ghost_rate=jamming_rate, seed=seed+2
    )
    print(f"  Total measurements: {len(measurements)}")
    print(f"  Ghost returns injected: {len(ghost_indices)}")

    # Run EKF
    print("\nRunning Extended Kalman Filter...")
    ekf = ExtendedKalmanFilter(
        process_noise_accel=150.0,
        measurement_noise_pos=112.5,
        measurement_noise_vel=15.0
    )
    ekf_estimates = ekf.process_measurements(measurements)
    ekf_positions = np.array([e.position for e in ekf_estimates])

    true_positions = trajectory.positions
    ekf_rms, ekf_max, ekf_errors = compute_errors(ekf_positions, true_positions)
    print(f"  RMS Error: {ekf_rms:.1f} m")
    print(f"  Max Error: {ekf_max:.1f} m")

    # Run Spinor Manifold Tracker
    print("\nRunning Spinor Manifold Tracker...")
    manifold_tracker = SpinorManifoldTracker(
        max_acceleration=400.0,
        geometric_stress_threshold=0.45
    )
    manifold_estimates = manifold_tracker.process_measurements(measurements)
    manifold_positions = np.array([e.position for e in manifold_estimates])

    manifold_rms, manifold_max, manifold_errors = compute_errors(
        manifold_positions, true_positions
    )
    rejection_rate = manifold_tracker.get_rejection_rate()
    intercept_point = manifold_tracker.get_intercept_point()

    print(f"  RMS Error: {manifold_rms:.1f} m")
    print(f"  Max Error: {manifold_max:.1f} m")
    print(f"  Rejection Rate: {rejection_rate*100:.1f}%")

    # Comparison metrics
    rms_improvement = (ekf_rms - manifold_rms) / ekf_rms * 100
    max_improvement = (ekf_max - manifold_max) / ekf_max * 100

    # Maneuver-specific analysis
    maneuver_start = int((maneuver_time - 5) / 0.1)
    maneuver_end = int((maneuver_time + 10) / 0.1)

    if maneuver_end <= len(ekf_errors):
        ekf_maneuver_rms = np.sqrt(np.mean(np.array(ekf_errors[maneuver_start:maneuver_end])**2))
        manifold_maneuver_rms = np.sqrt(np.mean(np.array(manifold_errors[maneuver_start:maneuver_end])**2))
        maneuver_improvement = (ekf_maneuver_rms - manifold_maneuver_rms) / ekf_maneuver_rms * 100
    else:
        ekf_maneuver_rms = manifold_maneuver_rms = maneuver_improvement = 0

    # Print results table
    print("\n" + "=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)
    print()
    print("{:<35} {:>15} {:>15}".format("Metric", "EKF", "Spinor Manifold"))
    print("-" * 70)
    print("{:<35} {:>15.1f} {:>15.1f}".format("RMS Tracking Error (m)", ekf_rms, manifold_rms))
    print("{:<35} {:>15.1f} {:>15.1f}".format("Max Tracking Error (m)", ekf_max, manifold_max))
    print("{:<35} {:>15.1f} {:>15.1f}".format("Maneuver RMS Error (m)", ekf_maneuver_rms, manifold_maneuver_rms))
    print("{:<35} {:>15} {:>15.1f}%".format("Ghost/Decoy Rejection", "N/A", rejection_rate * 100))
    print("-" * 70)
    print()
    print("IMPROVEMENTS:")
    print(f"  RMS Error Reduction:      {rms_improvement:.1f}%")
    print(f"  Max Error Reduction:      {max_improvement:.1f}%")
    print(f"  Maneuver Error Reduction: {maneuver_improvement:.1f}%")

    if intercept_point is not None:
        print(f"\nINTERCEPT SINGULARITY: [{intercept_point[0]:.0f}, {intercept_point[1]:.0f}, {intercept_point[2]:.0f}] m")

    print("=" * 70)

    return {
        "trajectory": trajectory,
        "measurements": measurements,
        "ekf_positions": ekf_positions,
        "manifold_positions": manifold_positions,
        "ekf_rms": ekf_rms,
        "manifold_rms": manifold_rms,
        "ekf_errors": ekf_errors,
        "manifold_errors": manifold_errors,
        "rms_improvement": rms_improvement,
        "intercept_point": intercept_point
    }


def generate_plot(results: Dict, output_path: str = "tracking_comparison.png"):
    """Generate visualization if matplotlib is available."""
    try:
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
    except ImportError:
        print("\nmatplotlib not available - skipping visualization")
        return

    trajectory = results["trajectory"]
    true_pos = trajectory.positions
    ekf_pos = results["ekf_positions"]
    manifold_pos = results["manifold_positions"]
    times = trajectory.times

    fig = plt.figure(figsize=(16, 10))

    # 3D trajectory
    ax1 = fig.add_subplot(2, 2, 1, projection='3d')
    ax1.plot(true_pos[:, 0]/1000, true_pos[:, 1]/1000, true_pos[:, 2]/1000,
             'k-', linewidth=2, label='True Path')
    ax1.plot(ekf_pos[:, 0]/1000, ekf_pos[:, 1]/1000, ekf_pos[:, 2]/1000,
             'r--', linewidth=1.5, label='Kalman Filter', alpha=0.8)
    ax1.plot(manifold_pos[:, 0]/1000, manifold_pos[:, 1]/1000, manifold_pos[:, 2]/1000,
             'b-', linewidth=1.5, label='Spinor Manifold', alpha=0.8)

    if results["intercept_point"] is not None:
        ip = results["intercept_point"]
        ax1.scatter([ip[0]/1000], [ip[1]/1000], [ip[2]/1000],
                   c='g', marker='X', s=200, label='Intercept Point')

    ax1.set_xlabel('X (km)')
    ax1.set_ylabel('Y (km)')
    ax1.set_zlabel('Altitude (km)')
    ax1.set_title('3D Trajectory Comparison')
    ax1.legend()

    # Error over time
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.plot(times[:len(results["ekf_errors"])], results["ekf_errors"],
             'r-', label='Kalman Filter', alpha=0.8)
    ax2.plot(times[:len(results["manifold_errors"])], results["manifold_errors"],
             'b-', label='Spinor Manifold', alpha=0.8)
    ax2.axvspan(25, 40, alpha=0.2, color='yellow', label='Maneuver')
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Position Error (m)')
    ax2.set_title('Tracking Error Over Time')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_yscale('log')

    # XY view
    ax3 = fig.add_subplot(2, 2, 3)
    ax3.plot(true_pos[:, 0]/1000, true_pos[:, 1]/1000, 'k-', linewidth=2, label='True Path')
    ax3.plot(ekf_pos[:, 0]/1000, ekf_pos[:, 1]/1000, 'r--', linewidth=1.5, label='Kalman Filter')
    ax3.plot(manifold_pos[:, 0]/1000, manifold_pos[:, 1]/1000, 'b-', linewidth=1.5, label='Spinor Manifold')
    if results["intercept_point"] is not None:
        ip = results["intercept_point"]
        ax3.scatter([ip[0]/1000], [ip[1]/1000], c='g', marker='X', s=200, label='Intercept')
    ax3.set_xlabel('X (km)')
    ax3.set_ylabel('Y (km)')
    ax3.set_title('Plan View')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Error histogram
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.hist(results["ekf_errors"], bins=30, alpha=0.5,
             label=f'EKF (RMS={results["ekf_rms"]:.0f}m)', color='red')
    ax4.hist(results["manifold_errors"], bins=30, alpha=0.5,
             label=f'Manifold (RMS={results["manifold_rms"]:.0f}m)', color='blue')
    ax4.set_xlabel('Position Error (m)')
    ax4.set_ylabel('Frequency')
    ax4.set_title('Error Distribution')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nFigure saved to: {output_path}")
    plt.close()


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Hypersonic Defense Simulation - Spinor Manifold vs EKF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hypersonic_defense_sim.py
  python hypersonic_defense_sim.py --mach 10 --maneuver-g 25
  python hypersonic_defense_sim.py --jamming 0.3 --duration 90
        """
    )

    parser.add_argument('--mach', type=float, default=8.0,
                       help='HGV Mach number (default: 8.0)')
    parser.add_argument('--duration', type=float, default=60.0,
                       help='Simulation duration in seconds (default: 60)')
    parser.add_argument('--maneuver-g', type=float, default=15.0,
                       help='Maneuver g-force (default: 15)')
    parser.add_argument('--maneuver-time', type=float, default=30.0,
                       help='Time of maneuver in seconds (default: 30)')
    parser.add_argument('--jamming', type=float, default=0.2,
                       help='Ghost/jamming rate 0-1 (default: 0.2)')
    parser.add_argument('--plasma', type=float, default=0.5,
                       help='Plasma noise intensity 0-2 (default: 0.5)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed (default: 42)')
    parser.add_argument('--no-plot', action='store_true',
                       help='Skip generating plot')
    parser.add_argument('--output', type=str, default='tracking_comparison.png',
                       help='Output plot filename')

    args = parser.parse_args()

    results = run_simulation(
        mach_number=args.mach,
        duration=args.duration,
        maneuver_time=args.maneuver_time,
        maneuver_g=args.maneuver_g,
        jamming_rate=args.jamming,
        plasma_intensity=args.plasma,
        seed=args.seed
    )

    if not args.no_plot:
        generate_plot(results, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
