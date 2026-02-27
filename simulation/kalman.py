"""
Extended Kalman Filter (EKF) for Target Tracking

Standard EKF implementation using Constant Velocity (CV) or
Constant Acceleration (CA) motion models.

This represents the "legacy" tracking approach that struggles with:
- High-g maneuvers (model mismatch)
- Non-Gaussian noise (plasma bursts, jamming)
- Ghost returns (outliers that corrupt the filter)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from .sensor import RadarMeasurement


@dataclass
class EKFState:
    """State estimate from the Extended Kalman Filter."""

    position: np.ndarray  # [x, y, z] estimated position
    velocity: np.ndarray  # [vx, vy, vz] estimated velocity
    covariance: np.ndarray  # 6x6 state covariance matrix
    time: float
    innovation: np.ndarray = field(default_factory=lambda: np.zeros(3))
    innovation_covariance: np.ndarray = field(default_factory=lambda: np.eye(3))

    @property
    def position_uncertainty(self) -> float:
        """1-sigma position uncertainty (meters)."""
        return np.sqrt(np.trace(self.covariance[:3, :3]))

    @property
    def velocity_uncertainty(self) -> float:
        """1-sigma velocity uncertainty (m/s)."""
        return np.sqrt(np.trace(self.covariance[3:6, 3:6]))

    def copy(self) -> 'EKFState':
        return EKFState(
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            covariance=self.covariance.copy(),
            time=self.time,
            innovation=self.innovation.copy(),
            innovation_covariance=self.innovation_covariance.copy()
        )


class ExtendedKalmanFilter:
    """
    Extended Kalman Filter for 3D target tracking.

    Uses a Constant Velocity (CV) motion model:
        x(k+1) = F * x(k) + w(k)

    where:
        x = [px, py, pz, vx, vy, vz]^T
        F = state transition matrix
        w = process noise (acceleration uncertainty)

    The filter assumes:
    1. Gaussian measurement noise
    2. Smooth, predictable motion
    3. No outliers/ghost returns

    These assumptions FAIL catastrophically for maneuvering HGVs
    in contested electromagnetic environments.
    """

    def __init__(
        self,
        process_noise_accel: float = 50.0,
        measurement_noise_pos: float = 100.0,
        measurement_noise_vel: float = 20.0
    ):
        """
        Initialize the EKF.

        Args:
            process_noise_accel: Process noise (m/s^2) - represents
                                 unmodeled acceleration
            measurement_noise_pos: Position measurement noise (meters)
            measurement_noise_vel: Velocity measurement noise (m/s)
        """
        self.process_noise_accel = process_noise_accel
        self.measurement_noise_pos = measurement_noise_pos
        self.measurement_noise_vel = measurement_noise_vel

        # State vector: [x, y, z, vx, vy, vz]
        self.state_dim = 6
        self.meas_dim = 6  # We measure position and velocity

        # Measurement matrix (we directly observe position and velocity)
        self.H = np.eye(6)

        # Initialize state
        self._state: Optional[EKFState] = None
        self._initialized = False

        # Track history
        self.history: List[EKFState] = []

    def _build_transition_matrix(self, dt: float) -> np.ndarray:
        """Build state transition matrix F for time step dt."""
        F = np.eye(6)
        F[0, 3] = dt  # x += vx * dt
        F[1, 4] = dt  # y += vy * dt
        F[2, 5] = dt  # z += vz * dt
        return F

    def _build_process_noise(self, dt: float) -> np.ndarray:
        """
        Build process noise covariance matrix Q.

        Uses the discrete white noise acceleration model.
        """
        sigma_a = self.process_noise_accel

        # Standard discrete white noise acceleration model
        Q = np.zeros((6, 6))

        # Position-position covariance
        Q[0, 0] = (dt**4) / 4
        Q[1, 1] = (dt**4) / 4
        Q[2, 2] = (dt**4) / 4

        # Position-velocity covariance
        Q[0, 3] = (dt**3) / 2
        Q[1, 4] = (dt**3) / 2
        Q[2, 5] = (dt**3) / 2
        Q[3, 0] = (dt**3) / 2
        Q[4, 1] = (dt**3) / 2
        Q[5, 2] = (dt**3) / 2

        # Velocity-velocity covariance
        Q[3, 3] = dt**2
        Q[4, 4] = dt**2
        Q[5, 5] = dt**2

        return Q * sigma_a**2

    def _build_measurement_noise(self) -> np.ndarray:
        """Build measurement noise covariance matrix R."""
        R = np.diag([
            self.measurement_noise_pos**2,  # x
            self.measurement_noise_pos**2,  # y
            self.measurement_noise_pos**2,  # z
            self.measurement_noise_vel**2,  # vx
            self.measurement_noise_vel**2,  # vy
            self.measurement_noise_vel**2,  # vz
        ])
        return R

    def initialize(self, measurement: RadarMeasurement) -> EKFState:
        """
        Initialize filter with first measurement.

        Args:
            measurement: First radar measurement

        Returns:
            Initial state estimate
        """
        # Initial state from measurement
        x = np.concatenate([measurement.position, measurement.velocity])

        # Initial covariance - large uncertainty
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
        """
        Prediction step: propagate state forward in time.

        This is where the CV model FAILS for maneuvering targets.
        Linear extrapolation cannot predict turns.

        Args:
            dt: Time step in seconds

        Returns:
            Predicted state
        """
        if not self._initialized:
            raise RuntimeError("Filter not initialized")

        # State transition
        F = self._build_transition_matrix(dt)
        Q = self._build_process_noise(dt)

        # Current state vector
        x = np.concatenate([self._state.position, self._state.velocity])

        # Predict state (LINEAR EXTRAPOLATION - this is the problem!)
        x_pred = F @ x

        # Predict covariance
        P_pred = F @ self._state.covariance @ F.T + Q

        self._state = EKFState(
            position=x_pred[:3],
            velocity=x_pred[3:6],
            covariance=P_pred,
            time=self._state.time + dt
        )

        return self._state.copy()

    def update(self, measurement: RadarMeasurement) -> EKFState:
        """
        Update step: incorporate new measurement.

        Standard Kalman update - vulnerable to outliers.

        Args:
            measurement: New radar measurement

        Returns:
            Updated state estimate
        """
        if not self._initialized:
            return self.initialize(measurement)

        # Predict to measurement time
        dt = measurement.time - self._state.time
        if dt > 0:
            self.predict(dt)

        # Measurement vector
        z = np.concatenate([measurement.position, measurement.velocity])

        # Predicted measurement
        x = np.concatenate([self._state.position, self._state.velocity])
        z_pred = self.H @ x

        # Innovation (measurement residual)
        y = z - z_pred

        # Measurement noise (scaled by confidence)
        R = self._build_measurement_noise()
        R = R / max(0.1, measurement.confidence)

        # Innovation covariance
        S = self.H @ self._state.covariance @ self.H.T + R

        # Kalman gain
        K = self._state.covariance @ self.H.T @ np.linalg.inv(S)

        # State update
        x_new = x + K @ y

        # Covariance update (Joseph form for numerical stability)
        I_KH = np.eye(6) - K @ self.H
        P_new = I_KH @ self._state.covariance @ I_KH.T + K @ R @ K.T

        self._state = EKFState(
            position=x_new[:3],
            velocity=x_new[3:6],
            covariance=P_new,
            time=measurement.time,
            innovation=y[:3],
            innovation_covariance=S[:3, :3]
        )

        self.history.append(self._state.copy())
        return self._state.copy()

    def process_measurements(
        self,
        measurements: List[RadarMeasurement]
    ) -> List[EKFState]:
        """
        Process a sequence of measurements.

        Args:
            measurements: List of radar measurements

        Returns:
            List of state estimates
        """
        self._initialized = False
        self._state = None
        self.history = []

        estimates = []
        for meas in measurements:
            state = self.update(meas)
            estimates.append(state)

        return estimates

    def get_current_state(self) -> Optional[EKFState]:
        """Get current state estimate."""
        return self._state.copy() if self._state else None

    def reset(self):
        """Reset the filter."""
        self._initialized = False
        self._state = None
        self.history = []


class AdaptiveEKF(ExtendedKalmanFilter):
    """
    Adaptive EKF that attempts to handle maneuvers.

    Uses innovation-based adaptation to increase process noise
    during detected maneuvers. This is a common approach but
    still fundamentally limited by the linear motion model.
    """

    def __init__(
        self,
        process_noise_accel: float = 50.0,
        measurement_noise_pos: float = 100.0,
        measurement_noise_vel: float = 20.0,
        adaptation_rate: float = 0.1,
        maneuver_threshold: float = 3.0
    ):
        super().__init__(
            process_noise_accel,
            measurement_noise_pos,
            measurement_noise_vel
        )
        self.adaptation_rate = adaptation_rate
        self.maneuver_threshold = maneuver_threshold
        self._adapted_process_noise = process_noise_accel

    def update(self, measurement: RadarMeasurement) -> EKFState:
        """Update with adaptive process noise."""
        if not self._initialized:
            return self.initialize(measurement)

        # Standard update first
        state = super().update(measurement)

        # Check innovation magnitude for maneuver detection
        innovation_norm = np.linalg.norm(state.innovation)
        expected_innovation = np.sqrt(np.trace(state.innovation_covariance))

        normalized_innovation = innovation_norm / max(1.0, expected_innovation)

        # Adapt process noise if maneuver detected
        if normalized_innovation > self.maneuver_threshold:
            # Increase process noise to handle maneuver
            self._adapted_process_noise = min(
                500.0,  # Cap at reasonable maximum
                self._adapted_process_noise * (1 + self.adaptation_rate)
            )
        else:
            # Decay back toward nominal
            self._adapted_process_noise = max(
                self.process_noise_accel,
                self._adapted_process_noise * (1 - self.adaptation_rate * 0.5)
            )

        # Override process noise for next prediction
        self.process_noise_accel = self._adapted_process_noise

        return state


def compute_tracking_error(
    estimates: List[EKFState],
    truth: List[np.ndarray]
) -> Tuple[float, float, List[float]]:
    """
    Compute tracking error metrics.

    Args:
        estimates: List of state estimates
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
    # Test EKF with synthetic data
    from .trajectory import generate_skip_glide_trajectory
    from .sensor import RadarSensor, add_plasma_noise, add_jamming

    # Generate trajectory
    traj = generate_skip_glide_trajectory(duration=30.0)

    # Generate measurements
    sensor = RadarSensor()
    measurements = sensor.measure_trajectory(traj, seed=42)
    measurements = add_plasma_noise(measurements, intensity=0.3, seed=43)
    measurements, _ = add_jamming(measurements, ghost_rate=0.1, seed=44)

    # Track with EKF
    ekf = ExtendedKalmanFilter(process_noise_accel=100.0)
    estimates = ekf.process_measurements(measurements)

    # Compute error
    true_positions = [s.position for s in traj.states]
    rms, max_err, errors = compute_tracking_error(estimates, true_positions)

    print(f"EKF Tracking Results:")
    print(f"  RMS Error: {rms:.1f} m")
    print(f"  Max Error: {max_err:.1f} m")
    print(f"  States processed: {len(estimates)}")
