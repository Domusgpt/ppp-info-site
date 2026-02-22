"""
Radar Sensor Simulation

Simulates radar measurements of an HGV including:
- Gaussian measurement noise (range, angle, velocity)
- Plasma sheath attenuation during high-speed flight
- Ghost returns from jamming/decoys
- Glint effects from vehicle rotation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from .trajectory import HGVState, HGVTrajectory


@dataclass
class RadarMeasurement:
    """Single radar measurement with noise characteristics."""

    position: np.ndarray  # Measured [x, y, z] position
    velocity: np.ndarray  # Measured velocity (Doppler-derived)
    time: float
    snr: float  # Signal-to-noise ratio in dB
    is_valid: bool = True  # False if this is a ghost/decoy return
    confidence: float = 1.0  # Measurement confidence [0, 1]

    @property
    def range(self) -> float:
        return np.linalg.norm(self.position)


@dataclass
class RadarSensor:
    """
    Simulates a ground-based or ship-based tracking radar.

    Models realistic noise sources including:
    - Thermal noise (Gaussian)
    - Plasma sheath interference
    - Electronic jamming
    - Multipath effects
    """

    # Radar performance parameters
    position_sigma: float = 50.0  # Position uncertainty (meters) at nominal SNR
    velocity_sigma: float = 5.0  # Velocity uncertainty (m/s)
    angular_sigma: float = 0.001  # Angular uncertainty (radians)
    update_rate: float = 10.0  # Updates per second

    # Environmental effects
    plasma_threshold_mach: float = 6.0  # Mach number where plasma effects begin
    plasma_max_attenuation: float = 0.8  # Maximum signal loss fraction

    # Jamming parameters
    jamming_active: bool = False
    jamming_power: float = 0.0  # Relative jamming power
    ghost_rate: float = 0.3  # Probability of ghost return per measurement

    # Sensor position (for range-dependent effects)
    sensor_position: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def compute_plasma_attenuation(self, mach: float) -> float:
        """
        Compute signal attenuation due to plasma sheath.

        At hypersonic speeds, the vehicle is surrounded by ionized plasma
        that attenuates radar returns.
        """
        if mach < self.plasma_threshold_mach:
            return 0.0

        # Linear ramp from threshold to max attenuation at Mach 12+
        excess_mach = mach - self.plasma_threshold_mach
        attenuation = min(self.plasma_max_attenuation, excess_mach * 0.13)
        return attenuation

    def compute_range_dependent_noise(self, range_km: float) -> float:
        """
        Compute noise scaling factor based on range.

        Radar SNR decreases with R^4, so noise increases with R^2.
        """
        reference_range = 100.0  # km
        range_factor = (range_km / reference_range) ** 2
        return max(1.0, range_factor)

    def measure(
        self,
        true_state: HGVState,
        rng: np.random.Generator = None
    ) -> RadarMeasurement:
        """
        Generate a noisy radar measurement of the target.

        Args:
            true_state: True target state
            rng: Random number generator (for reproducibility)

        Returns:
            RadarMeasurement with realistic noise
        """
        if rng is None:
            rng = np.random.default_rng()

        # Compute range to target
        relative_pos = true_state.position - self.sensor_position
        range_m = np.linalg.norm(relative_pos)
        range_km = range_m / 1000.0

        # Base noise scaling
        range_noise_factor = self.compute_range_dependent_noise(range_km)

        # Plasma attenuation
        plasma_loss = self.compute_plasma_attenuation(true_state.mach)
        plasma_noise_factor = 1.0 / (1.0 - plasma_loss + 0.01)

        # Combined noise factor
        total_noise_factor = range_noise_factor * plasma_noise_factor

        # Position noise (Gaussian)
        pos_sigma = self.position_sigma * total_noise_factor
        position_noise = rng.normal(0, pos_sigma, size=3)
        measured_position = true_state.position + position_noise

        # Velocity noise (Doppler measurement)
        vel_sigma = self.velocity_sigma * total_noise_factor
        velocity_noise = rng.normal(0, vel_sigma, size=3)
        measured_velocity = true_state.velocity + velocity_noise

        # Compute effective SNR
        base_snr = 25.0  # dB at reference range
        snr = base_snr - 10 * np.log10(range_noise_factor) - 10 * np.log10(plasma_noise_factor)

        # Confidence based on SNR
        confidence = min(1.0, max(0.1, (snr + 10) / 40))

        return RadarMeasurement(
            position=measured_position,
            velocity=measured_velocity,
            time=true_state.time,
            snr=snr,
            is_valid=True,
            confidence=confidence
        )

    def measure_trajectory(
        self,
        trajectory: HGVTrajectory,
        seed: int = None
    ) -> List[RadarMeasurement]:
        """
        Generate measurements for an entire trajectory.

        Args:
            trajectory: True trajectory to measure
            seed: Random seed for reproducibility

        Returns:
            List of radar measurements
        """
        rng = np.random.default_rng(seed)
        measurements = []

        for state in trajectory.states:
            meas = self.measure(state, rng)
            measurements.append(meas)

        return measurements


def add_plasma_noise(
    measurements: List[RadarMeasurement],
    intensity: float = 1.0,
    seed: int = None
) -> List[RadarMeasurement]:
    """
    Add additional plasma-sheath noise to measurements.

    Simulates the intermittent signal loss and distortion caused by
    ionized plasma around hypersonic vehicles.

    Args:
        measurements: Original measurements
        intensity: Noise intensity multiplier (0-2 typical)
        seed: Random seed

    Returns:
        Modified measurements with plasma noise
    """
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

        # Plasma noise is bursty - occasional large spikes
        if rng.random() < 0.15 * intensity:
            # Plasma burst - large position error
            burst_magnitude = 200 * intensity * rng.exponential(1.0)
            burst_direction = rng.standard_normal(3)
            burst_direction /= np.linalg.norm(burst_direction)
            new_meas.position += burst_direction * burst_magnitude
            new_meas.confidence *= 0.5

        # Continuous low-level plasma interference
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
    """
    Add electronic jamming effects including ghost returns.

    Ghost returns are false targets that do not follow physical laws -
    they lack consistent rotational momentum and violate energy conservation.
    This is the key characteristic that the Spinor Manifold Tracker exploits.

    Args:
        measurements: Original measurements
        ghost_rate: Probability of ghost return per measurement
        ghost_amplitude: Maximum ghost offset in meters
        seed: Random seed

    Returns:
        Tuple of (modified measurements, indices of ghost returns)
    """
    rng = np.random.default_rng(seed)
    modified = []
    ghost_indices = []

    # Track the "center of mass" for generating physically-impossible ghosts
    running_centroid = np.zeros(3)
    running_velocity = np.zeros(3)

    for i, meas in enumerate(measurements):
        # Update running averages
        alpha = 0.1
        running_centroid = (1 - alpha) * running_centroid + alpha * meas.position
        running_velocity = (1 - alpha) * running_velocity + alpha * meas.velocity

        if rng.random() < ghost_rate:
            # Generate a ghost return
            # Key insight: Ghosts violate angular momentum conservation
            # They appear as discontinuous jumps in position space

            # Random offset direction (no physical constraint)
            offset_direction = rng.standard_normal(3)
            offset_direction /= np.linalg.norm(offset_direction)

            # Offset magnitude - larger than physically possible for the vehicle
            offset_magnitude = ghost_amplitude * (0.5 + rng.random())

            ghost_position = meas.position + offset_direction * offset_magnitude

            # Ghost velocity is also random (not derived from trajectory)
            ghost_velocity = running_velocity + rng.standard_normal(3) * 500

            ghost_meas = RadarMeasurement(
                position=ghost_position,
                velocity=ghost_velocity,
                time=meas.time,
                snr=meas.snr - 3,  # Slightly weaker signal
                is_valid=False,  # This is a ghost
                confidence=0.8  # Looks like a real return
            )
            modified.append(ghost_meas)
            ghost_indices.append(i)
        else:
            # Normal measurement (possibly with some jamming degradation)
            new_meas = RadarMeasurement(
                position=meas.position.copy(),
                velocity=meas.velocity.copy(),
                time=meas.time,
                snr=meas.snr,
                is_valid=True,
                confidence=meas.confidence
            )

            # Add some jamming-induced noise even to valid returns
            jamming_noise = rng.normal(0, 30, size=3)
            new_meas.position += jamming_noise

            modified.append(new_meas)

    return modified, ghost_indices


def simulate_decoys(
    trajectory: HGVTrajectory,
    num_decoys: int = 3,
    seed: int = None
) -> List[List[RadarMeasurement]]:
    """
    Simulate decoy trajectories alongside the real HGV.

    Decoys are lightweight and lack the rotational inertia of a real warhead.
    Their trajectories show higher geometric stress when analyzed on the
    4D spinor manifold.

    Args:
        trajectory: True HGV trajectory
        num_decoys: Number of decoys to generate
        seed: Random seed

    Returns:
        List of decoy measurement sequences
    """
    rng = np.random.default_rng(seed)
    decoy_tracks = []

    for d in range(num_decoys):
        # Decoys deploy from the HGV at some point
        deploy_idx = int(len(trajectory) * (0.2 + 0.3 * rng.random()))
        deploy_state = trajectory[deploy_idx]

        decoy_measurements = []

        # Initial offset from real vehicle
        offset = rng.standard_normal(3) * 500

        for i, state in enumerate(trajectory.states[deploy_idx:], deploy_idx):
            # Decoy drifts relative to real vehicle
            # Low mass = high susceptibility to atmospheric perturbations
            drift_rate = 50 + 100 * rng.random()  # m/s
            drift = offset + drift_rate * (state.time - deploy_state.time) * rng.standard_normal(3) * 0.1

            # Decoy position with unrealistic jitter (low inertia)
            jitter = rng.standard_normal(3) * (100 + 50 * rng.random())
            decoy_pos = state.position + drift + jitter

            # Decoy velocity - erratic, not following geodesic
            velocity_noise = rng.standard_normal(3) * 200
            decoy_vel = state.velocity + velocity_noise

            decoy_meas = RadarMeasurement(
                position=decoy_pos,
                velocity=decoy_vel,
                time=state.time,
                snr=15 + rng.random() * 5,  # Lower RCS than real warhead
                is_valid=False,  # Mark as decoy for ground truth
                confidence=0.7 + 0.2 * rng.random()
            )
            decoy_measurements.append(decoy_meas)

        decoy_tracks.append(decoy_measurements)

    return decoy_tracks


if __name__ == "__main__":
    from .trajectory import generate_skip_glide_trajectory

    # Generate test trajectory
    traj = generate_skip_glide_trajectory(duration=30.0)

    # Create sensor and measure
    sensor = RadarSensor()
    measurements = sensor.measure_trajectory(traj, seed=42)

    # Add noise effects
    plasma_measurements = add_plasma_noise(measurements, intensity=0.5, seed=43)
    jammed_measurements, ghost_idx = add_jamming(plasma_measurements, ghost_rate=0.15, seed=44)

    print(f"Generated {len(measurements)} measurements")
    print(f"Ghost returns: {len(ghost_idx)}")
    print(f"First measurement SNR: {measurements[0].snr:.1f} dB")
    print(f"Measurement at maneuver SNR: {measurements[250].snr:.1f} dB")
