"""
Hypersonic Defense Simulation - Main Runner

Demonstrates the superiority of Spinor Manifold Tracking over
standard Extended Kalman Filters when tracking maneuvering HGVs.

Generates:
1. 3D trajectory comparison plot
2. Error analysis over time
3. Performance metrics table
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from .trajectory import (
    HGVTrajectory,
    generate_skip_glide_trajectory,
    generate_evasive_trajectory
)
from .sensor import (
    RadarSensor,
    RadarMeasurement,
    add_plasma_noise,
    add_jamming,
    simulate_decoys
)
from .kalman import (
    ExtendedKalmanFilter,
    AdaptiveEKF,
    EKFState,
    compute_tracking_error
)
from .spinor_track import (
    SpinorManifoldTracker,
    ManifoldState,
    compute_manifold_tracking_error
)


@dataclass
class SimulationConfig:
    """Configuration for the hypersonic defense simulation."""

    # Trajectory parameters
    mach_number: float = 8.0
    initial_altitude: float = 50000.0  # meters
    duration: float = 60.0  # seconds
    dt: float = 0.1  # time step

    # Maneuver parameters
    maneuver_time: float = 30.0  # seconds
    maneuver_g: float = 15.0  # g-force
    maneuver_duration: float = 5.0  # seconds

    # Sensor parameters
    position_noise: float = 75.0  # meters
    velocity_noise: float = 10.0  # m/s

    # Environmental effects
    plasma_intensity: float = 0.5
    jamming_ghost_rate: float = 0.2
    jamming_amplitude: float = 3000.0  # meters

    # Random seed
    seed: int = 42


@dataclass
class SimulationResults:
    """Results from running the simulation."""

    # Trajectories
    true_trajectory: HGVTrajectory
    measurements: List[RadarMeasurement]
    ghost_indices: List[int]

    # Tracker estimates
    ekf_estimates: List[EKFState]
    manifold_estimates: List[ManifoldState]

    # Metrics
    ekf_rms_error: float
    ekf_max_error: float
    ekf_errors: List[float]

    manifold_rms_error: float
    manifold_max_error: float
    manifold_errors: List[float]
    manifold_rejection_rate: float

    # Intercept point
    intercept_point: Optional[np.ndarray]


def run_simulation(config: SimulationConfig = None) -> SimulationResults:
    """
    Run the complete hypersonic defense simulation.

    Args:
        config: Simulation configuration (uses defaults if None)

    Returns:
        SimulationResults with all trajectories and metrics
    """
    if config is None:
        config = SimulationConfig()

    # Generate true HGV trajectory
    print("Generating HGV trajectory...")
    trajectory = generate_skip_glide_trajectory(
        mach_number=config.mach_number,
        initial_altitude=config.initial_altitude,
        duration=config.duration,
        dt=config.dt,
        maneuver_time=config.maneuver_time,
        maneuver_g=config.maneuver_g,
        maneuver_duration=config.maneuver_duration
    )

    # Generate radar measurements
    print("Simulating radar measurements...")
    sensor = RadarSensor(
        position_sigma=config.position_noise,
        velocity_sigma=config.velocity_noise
    )
    measurements = sensor.measure_trajectory(trajectory, seed=config.seed)

    # Add environmental effects
    print("Adding plasma noise and jamming...")
    measurements = add_plasma_noise(
        measurements,
        intensity=config.plasma_intensity,
        seed=config.seed + 1
    )
    measurements, ghost_indices = add_jamming(
        measurements,
        ghost_rate=config.jamming_ghost_rate,
        ghost_amplitude=config.jamming_amplitude,
        seed=config.seed + 2
    )

    print(f"  Total measurements: {len(measurements)}")
    print(f"  Ghost returns: {len(ghost_indices)}")

    # Run Extended Kalman Filter
    print("Running Extended Kalman Filter...")
    ekf = ExtendedKalmanFilter(
        process_noise_accel=150.0,  # Tuned for HGV
        measurement_noise_pos=config.position_noise * 1.5,
        measurement_noise_vel=config.velocity_noise * 1.5
    )
    ekf_estimates = ekf.process_measurements(measurements)

    # Compute EKF errors
    true_positions = [s.position for s in trajectory.states]
    ekf_rms, ekf_max, ekf_errors = compute_tracking_error(
        ekf_estimates, true_positions
    )
    print(f"  EKF RMS Error: {ekf_rms:.1f} m")
    print(f"  EKF Max Error: {ekf_max:.1f} m")

    # Run Spinor Manifold Tracker
    print("Running Spinor Manifold Tracker...")
    manifold_tracker = SpinorManifoldTracker(
        max_acceleration=400.0,  # ~40g
        geometric_stress_threshold=0.45
    )
    manifold_estimates = manifold_tracker.process_measurements(measurements)

    # Compute manifold tracker errors
    manifold_rms, manifold_max, manifold_errors = compute_manifold_tracking_error(
        manifold_estimates, true_positions
    )
    rejection_rate = manifold_tracker.get_rejection_rate()
    intercept_point = manifold_tracker.get_intercept_point()

    print(f"  Manifold RMS Error: {manifold_rms:.1f} m")
    print(f"  Manifold Max Error: {manifold_max:.1f} m")
    print(f"  Rejection Rate: {rejection_rate*100:.1f}%")

    return SimulationResults(
        true_trajectory=trajectory,
        measurements=measurements,
        ghost_indices=ghost_indices,
        ekf_estimates=ekf_estimates,
        manifold_estimates=manifold_estimates,
        ekf_rms_error=ekf_rms,
        ekf_max_error=ekf_max,
        ekf_errors=ekf_errors,
        manifold_rms_error=manifold_rms,
        manifold_max_error=manifold_max,
        manifold_errors=manifold_errors,
        manifold_rejection_rate=rejection_rate,
        intercept_point=intercept_point
    )


def compare_trackers(results: SimulationResults) -> Dict:
    """
    Generate comparison metrics between trackers.

    Args:
        results: Simulation results

    Returns:
        Dictionary of comparison metrics
    """
    # RMS improvement
    rms_improvement = (results.ekf_rms_error - results.manifold_rms_error) / results.ekf_rms_error * 100

    # Max error improvement
    max_improvement = (results.ekf_max_error - results.manifold_max_error) / results.ekf_max_error * 100

    # Error during maneuver (around maneuver time)
    maneuver_start_idx = int(25 / 0.1)  # ~25 seconds
    maneuver_end_idx = int(35 / 0.1)    # ~35 seconds

    if maneuver_end_idx <= len(results.ekf_errors):
        ekf_maneuver_errors = results.ekf_errors[maneuver_start_idx:maneuver_end_idx]
        manifold_maneuver_errors = results.manifold_errors[maneuver_start_idx:maneuver_end_idx]

        ekf_maneuver_rms = np.sqrt(np.mean(np.array(ekf_maneuver_errors)**2))
        manifold_maneuver_rms = np.sqrt(np.mean(np.array(manifold_maneuver_errors)**2))
        maneuver_improvement = (ekf_maneuver_rms - manifold_maneuver_rms) / ekf_maneuver_rms * 100
    else:
        ekf_maneuver_rms = 0
        manifold_maneuver_rms = 0
        maneuver_improvement = 0

    # Tracking lag estimation (time to recover after maneuver)
    # Find when error drops back below threshold after maneuver
    threshold = 200  # meters

    ekf_recovery_time = None
    for i in range(maneuver_end_idx, len(results.ekf_errors)):
        if results.ekf_errors[i] < threshold:
            ekf_recovery_time = (i - maneuver_end_idx) * 0.1
            break

    manifold_recovery_time = None
    for i in range(maneuver_end_idx, len(results.manifold_errors)):
        if results.manifold_errors[i] < threshold:
            manifold_recovery_time = (i - maneuver_end_idx) * 0.1
            break

    return {
        "ekf_rms_error": results.ekf_rms_error,
        "manifold_rms_error": results.manifold_rms_error,
        "rms_improvement_percent": rms_improvement,
        "ekf_max_error": results.ekf_max_error,
        "manifold_max_error": results.manifold_max_error,
        "max_improvement_percent": max_improvement,
        "ekf_maneuver_rms": ekf_maneuver_rms,
        "manifold_maneuver_rms": manifold_maneuver_rms,
        "maneuver_improvement_percent": maneuver_improvement,
        "ekf_recovery_time": ekf_recovery_time,
        "manifold_recovery_time": manifold_recovery_time,
        "ghost_rejection_rate": results.manifold_rejection_rate,
        "intercept_point": results.intercept_point
    }


def print_results_table(comparison: Dict):
    """Print formatted comparison table."""
    print("\n" + "="*70)
    print("HYPERSONIC DEFENSE SIMULATION RESULTS")
    print("="*70)
    print("\n{:<35} {:>15} {:>15}".format(
        "Metric", "EKF", "Spinor Manifold"
    ))
    print("-"*70)

    print("{:<35} {:>15.1f} {:>15.1f}".format(
        "RMS Tracking Error (m)",
        comparison["ekf_rms_error"],
        comparison["manifold_rms_error"]
    ))

    print("{:<35} {:>15.1f} {:>15.1f}".format(
        "Max Tracking Error (m)",
        comparison["ekf_max_error"],
        comparison["manifold_max_error"]
    ))

    print("{:<35} {:>15.1f} {:>15.1f}".format(
        "Maneuver RMS Error (m)",
        comparison["ekf_maneuver_rms"],
        comparison["manifold_maneuver_rms"]
    ))

    if comparison["ekf_recovery_time"] is not None:
        ekf_rec = f"{comparison['ekf_recovery_time']:.2f}s"
    else:
        ekf_rec = "> 10s"

    if comparison["manifold_recovery_time"] is not None:
        man_rec = f"{comparison['manifold_recovery_time']:.2f}s"
    else:
        man_rec = "> 10s"

    print("{:<35} {:>15} {:>15}".format(
        "Recovery Time After Maneuver",
        ekf_rec,
        man_rec
    ))

    print("{:<35} {:>15} {:>15.1f}%".format(
        "Ghost/Decoy Rejection Rate",
        "N/A",
        comparison["ghost_rejection_rate"] * 100
    ))

    print("-"*70)
    print("\nIMPROVEMENTS:")
    print(f"  RMS Error Reduction:      {comparison['rms_improvement_percent']:.1f}%")
    print(f"  Max Error Reduction:      {comparison['max_improvement_percent']:.1f}%")
    print(f"  Maneuver Error Reduction: {comparison['maneuver_improvement_percent']:.1f}%")

    if comparison["intercept_point"] is not None:
        ip = comparison["intercept_point"]
        print(f"\nINTERCEPT SINGULARITY: [{ip[0]:.0f}, {ip[1]:.0f}, {ip[2]:.0f}] m")

    print("="*70)


def generate_visualization(
    results: SimulationResults,
    output_path: str = None,
    show_plot: bool = True
):
    """
    Generate 3D visualization of tracking comparison.

    Args:
        results: Simulation results
        output_path: Path to save figure (optional)
        show_plot: Whether to display the plot
    """
    try:
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
    except ImportError:
        print("matplotlib not available - skipping visualization")
        return

    # Extract data
    true_pos = results.true_trajectory.positions
    ekf_pos = np.array([e.position for e in results.ekf_estimates])
    manifold_pos = np.array([e.position for e in results.manifold_estimates])
    times = results.true_trajectory.times

    # Create figure with subplots
    fig = plt.figure(figsize=(16, 10))

    # 3D trajectory plot
    ax1 = fig.add_subplot(2, 2, 1, projection='3d')

    # True trajectory (black)
    ax1.plot(
        true_pos[:, 0] / 1000,
        true_pos[:, 1] / 1000,
        true_pos[:, 2] / 1000,
        'k-', linewidth=2, label='True Path'
    )

    # EKF estimate (red dashed)
    ax1.plot(
        ekf_pos[:, 0] / 1000,
        ekf_pos[:, 1] / 1000,
        ekf_pos[:, 2] / 1000,
        'r--', linewidth=1.5, label='Kalman Filter', alpha=0.8
    )

    # Manifold estimate (blue solid)
    ax1.plot(
        manifold_pos[:, 0] / 1000,
        manifold_pos[:, 1] / 1000,
        manifold_pos[:, 2] / 1000,
        'b-', linewidth=1.5, label='Spinor Manifold', alpha=0.8
    )

    # Intercept point (green X)
    if results.intercept_point is not None:
        ip = results.intercept_point
        ax1.scatter(
            [ip[0] / 1000], [ip[1] / 1000], [ip[2] / 1000],
            c='g', marker='X', s=200, label='Intercept Point'
        )

    ax1.set_xlabel('X (km)')
    ax1.set_ylabel('Y (km)')
    ax1.set_zlabel('Altitude (km)')
    ax1.set_title('3D Trajectory Comparison')
    ax1.legend()

    # Error over time
    ax2 = fig.add_subplot(2, 2, 2)

    ax2.plot(times[:len(results.ekf_errors)], results.ekf_errors,
             'r-', label='Kalman Filter', alpha=0.8)
    ax2.plot(times[:len(results.manifold_errors)], results.manifold_errors,
             'b-', label='Spinor Manifold', alpha=0.8)

    # Mark maneuver region
    ax2.axvspan(25, 35, alpha=0.2, color='yellow', label='Maneuver')

    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Position Error (m)')
    ax2.set_title('Tracking Error Over Time')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_yscale('log')

    # XY plane view
    ax3 = fig.add_subplot(2, 2, 3)

    ax3.plot(true_pos[:, 0] / 1000, true_pos[:, 1] / 1000,
             'k-', linewidth=2, label='True Path')
    ax3.plot(ekf_pos[:, 0] / 1000, ekf_pos[:, 1] / 1000,
             'r--', linewidth=1.5, label='Kalman Filter', alpha=0.8)
    ax3.plot(manifold_pos[:, 0] / 1000, manifold_pos[:, 1] / 1000,
             'b-', linewidth=1.5, label='Spinor Manifold', alpha=0.8)

    if results.intercept_point is not None:
        ip = results.intercept_point
        ax3.scatter([ip[0] / 1000], [ip[1] / 1000],
                   c='g', marker='X', s=200, label='Intercept Point')

    ax3.set_xlabel('X (km)')
    ax3.set_ylabel('Y (km)')
    ax3.set_title('Plan View (XY Plane)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_aspect('equal')

    # Error histogram
    ax4 = fig.add_subplot(2, 2, 4)

    ax4.hist(results.ekf_errors, bins=30, alpha=0.5,
             label=f'EKF (RMS={results.ekf_rms_error:.0f}m)', color='red')
    ax4.hist(results.manifold_errors, bins=30, alpha=0.5,
             label=f'Manifold (RMS={results.manifold_rms_error:.0f}m)', color='blue')

    ax4.set_xlabel('Position Error (m)')
    ax4.set_ylabel('Frequency')
    ax4.set_title('Error Distribution')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Figure saved to: {output_path}")

    if show_plot:
        plt.show()

    plt.close()


if __name__ == "__main__":
    # Run simulation with default configuration
    print("="*70)
    print("HYPERSONIC DEFENSE SIMULATION")
    print("Spinor Manifold Tracking vs Extended Kalman Filter")
    print("="*70 + "\n")

    config = SimulationConfig(
        mach_number=8.0,
        duration=60.0,
        maneuver_time=30.0,
        maneuver_g=20.0,
        plasma_intensity=0.5,
        jamming_ghost_rate=0.2,
        seed=42
    )

    results = run_simulation(config)
    comparison = compare_trackers(results)
    print_results_table(comparison)

    # Generate visualization
    generate_visualization(
        results,
        output_path="tracking_comparison.png",
        show_plot=False
    )
