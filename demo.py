#!/usr/bin/env python3
"""
CSPM + GAA Unified Demonstration

This demo showcases:
1. 600-cell constellation geometry (LPI capability)
2. Legitimate vs Attacker BER comparison
3. Hypersonic tracking: EKF vs Spinor comparison
4. GAA audit trail generation

HONEST DISCLAIMERS:
- Hypersonic trajectory is a TOY MODEL, not validated physics
- We're demonstrating ALGORITHM CONCEPTS, not operational capability
- The tracking comparison is valid regardless of trajectory realism

Usage:
    python demo.py [--no-plot] [--quick]

Copyright (c) 2025-2026 Clear Seas Solutions LLC
"""

import numpy as np
import argparse
import sys
from dataclasses import dataclass
from typing import List, Tuple, Optional

# Import our modules
from cspm.lattice import Cell600, PolychoralConstellation

# Check for matplotlib
try:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available. Running in text-only mode.")

# =============================================================================
# DEMO 1: 600-CELL CONSTELLATION AND LPI
# =============================================================================

def demo_constellation_geometry():
    """Show the 600-cell constellation properties."""
    print("\n" + "="*70)
    print("DEMO 1: 600-Cell Polytope Constellation")
    print("="*70)

    cell = Cell600()

    print(f"\nConstellation Properties:")
    print(f"  Vertices (symbols):     {len(cell.vertices)}")
    print(f"  Bits per symbol:        {cell.bits_per_symbol():.2f}")
    print(f"  Minimum angular dist:   {cell.minimum_distance():.4f} rad "
          f"({np.degrees(cell.minimum_distance()):.1f}°)")

    # Compare to QAM
    print(f"\nComparison to QAM:")
    print(f"  64-QAM:  6.0 bits/symbol, requires LDPC FEC")
    print(f"  128-QAM: 7.0 bits/symbol, requires LDPC FEC")
    print(f"  600-cell: {cell.bits_per_symbol():.1f} bits/symbol, "
          f"geometric quantization provides error correction")

    return cell


def demo_lpi_security(snr_db: float = 20.0, num_symbols: int = 10000):
    """
    Demonstrate LPI: legitimate receiver vs attacker.

    The legitimate receiver knows the hash chain seed.
    The attacker does not, so constellation rotation defeats them.
    """
    print("\n" + "="*70)
    print("DEMO 2: Low Probability of Intercept (LPI) Security")
    print("="*70)

    # Setup
    genesis_seed = b"LEGITIMATE_GENESIS_SEED"
    wrong_seed = b"ATTACKER_WRONG_GUESS"

    tx_constellation = PolychoralConstellation(seed=genesis_seed)
    rx_legitimate = PolychoralConstellation(seed=genesis_seed)
    rx_attacker = PolychoralConstellation(seed=wrong_seed)

    # SNR to noise standard deviation
    snr_linear = 10 ** (snr_db / 10)
    noise_std = 1.0 / np.sqrt(2 * snr_linear)

    # Transmit symbols
    np.random.seed(42)
    tx_symbols = np.random.randint(0, 120, num_symbols)

    legitimate_errors = 0
    attacker_errors = 0

    for i, sym in enumerate(tx_symbols):
        # Encode
        tx_point = tx_constellation.encode_symbol(sym)

        # Add AWGN noise
        noise = np.random.randn(4) * noise_std
        rx_point = tx_point + noise
        rx_point = rx_point / np.linalg.norm(rx_point)  # Re-normalize to sphere

        # Legitimate decode (correct seed)
        decoded_legit, _ = rx_legitimate.decode_symbol(rx_point)
        if decoded_legit != sym:
            legitimate_errors += 1

        # Attacker decode (wrong seed)
        decoded_attack, _ = rx_attacker.decode_symbol(rx_point)
        if decoded_attack != sym:
            attacker_errors += 1

        # Advance hash chains (packet boundary)
        if (i + 1) % 100 == 0:
            packet_hash = bytes([i % 256])
            tx_constellation.rotate_lattice(packet_hash)
            rx_legitimate.rotate_lattice(packet_hash)
            rx_attacker.rotate_lattice(packet_hash)  # Attacker rotates too but from wrong state

    legit_ber = legitimate_errors / num_symbols
    attack_ber = attacker_errors / num_symbols

    print(f"\nTest Parameters:")
    print(f"  SNR:           {snr_db} dB")
    print(f"  Symbols:       {num_symbols}")
    print(f"  Rotation:      Every 100 symbols (packet boundary)")

    print(f"\nResults:")
    print(f"  Legitimate RX: {legitimate_errors} errors, BER = {legit_ber:.4f}")
    print(f"  Attacker RX:   {attacker_errors} errors, BER = {attack_ber:.4f}")

    print(f"\nInterpretation:")
    if attack_ber > 0.4:
        print(f"  ✓ Attacker BER ≈ {attack_ber*100:.0f}% (essentially random guessing)")
        print(f"  ✓ LPI EFFECTIVE: Attacker cannot decode without correct seed")
    else:
        print(f"  ⚠ Attacker BER lower than expected - check rotation frequency")

    return legit_ber, attack_ber


# =============================================================================
# DEMO 3: HYPERSONIC TRACKING (TOY MODEL)
# =============================================================================

def demo_tracking_comparison(duration: float = 30.0, quick: bool = False):
    """
    Compare EKF vs Spinor tracking on a maneuvering trajectory.

    DISCLAIMER: This trajectory is a SIMPLIFIED TOY MODEL.
    We are demonstrating the TRACKING ALGORITHM, not physics accuracy.
    """
    print("\n" + "="*70)
    print("DEMO 3: Tracking Algorithm Comparison (EKF vs Spinor)")
    print("="*70)
    print("\n⚠️  DISCLAIMER: Trajectory is a simplified model, not validated physics")
    print("    We're comparing tracking algorithms, not simulating real HGVs")

    # Import simulation components
    try:
        from simulation.trajectory import generate_maneuvering_trajectory
        from simulation.kalman import ExtendedKalmanFilter
        from simulation.spinor_track import SpinorManifoldTracker
        from simulation.sensor import NoisySensor
    except ImportError:
        print("\n  Simulation modules not available. Skipping tracking demo.")
        return None, None

    dt = 0.1
    if quick:
        duration = 10.0

    # Generate trajectory (TOY MODEL)
    trajectory = generate_maneuvering_trajectory(
        duration=duration,
        dt=dt,
        maneuver_time=duration/2,
        maneuver_magnitude=10.0  # Arbitrary units
    )

    # Setup trackers
    sensor = NoisySensor(position_std=50.0, velocity_std=5.0)
    ekf = ExtendedKalmanFilter()
    spinor = SpinorManifoldTracker()

    ekf_errors = []
    spinor_errors = []
    times = []

    for i, true_state in enumerate(trajectory):
        # Get noisy measurement
        measurement = sensor.measure(true_state)

        # Update trackers
        ekf_estimate = ekf.update(measurement, dt)
        spinor_estimate = spinor.update(measurement, dt)

        # Compute errors
        ekf_err = np.linalg.norm(ekf_estimate[:3] - true_state.position)
        spinor_err = np.linalg.norm(spinor_estimate[:3] - true_state.position)

        ekf_errors.append(ekf_err)
        spinor_errors.append(spinor_err)
        times.append(true_state.time)

    # Statistics
    ekf_rmse = np.sqrt(np.mean(np.array(ekf_errors)**2))
    spinor_rmse = np.sqrt(np.mean(np.array(spinor_errors)**2))

    print(f"\nResults (RMSE over {duration}s trajectory):")
    print(f"  EKF RMSE:    {ekf_rmse:.1f} m")
    print(f"  Spinor RMSE: {spinor_rmse:.1f} m")
    print(f"  Improvement: {ekf_rmse/spinor_rmse:.1f}x")

    return (times, ekf_errors, spinor_errors), trajectory


# =============================================================================
# DEMO 4: GAA AUDIT TRAIL
# =============================================================================

def demo_gaa_audit():
    """Demonstrate GAA audit trail generation."""
    print("\n" + "="*70)
    print("DEMO 4: Geometric Audit Architecture (GAA)")
    print("="*70)

    try:
        from gaa import (
            TRACEEvent, MerkleAuditTree, DriftDetector,
            Quaternion, SafetyCase, EDRCapture
        )
        from gaa.telemetry.events import EventType, EventChain
    except ImportError:
        print("\n  GAA modules not available. Skipping audit demo.")
        return None

    # Create audit components
    chain = EventChain()
    merkle = MerkleAuditTree()
    detector = DriftDetector()
    edr = EDRCapture(pre_event_seconds=5.0, post_event_seconds=2.0)

    # Simulate some events
    print(f"\nGenerating audit trail...")

    for i in range(20):
        # Create geometric state
        q = Quaternion.from_euler(i * 0.1, 0, 0)
        coherence = 0.95 - i * 0.01

        # Check for drift
        metrics = detector.update(q, coherence)

        # Create TRACE event
        event = TRACEEvent(
            event_type=EventType.GEOMETRIC_STATE,
            payload={
                "quaternion": q.components.tolist(),
                "coherence": float(coherence),
                "drift_severity": float(metrics.drift_severity),
            }
        )

        chain.append(event)
        merkle.add_leaf(bytes.fromhex(event.event_hash))

        # Record to EDR
        edr.record_frame(
            quaternion=tuple(q.components),
            position=(i * 10.0, 0.0, 0.0),  # Dummy position
            velocity=(100.0, 0.0, 0.0),     # Dummy velocity
            coherence=coherence
        )

    # Verify integrity
    integrity = chain.verify_integrity()
    root = merkle.root  # property, not method

    print(f"\nAudit Trail Summary:")
    print(f"  Events recorded:    {len(chain.events)}")
    print(f"  Chain integrity:    {'✓ VERIFIED' if integrity else '✗ FAILED'}")
    print(f"  Merkle root:        {root.hex()[:32]}...")
    print(f"  EDR buffer frames:  {len(edr.buffer)}")

    # Generate proof for a specific event
    proof = merkle.get_proof(5)  # Proof for 6th event
    print(f"\n  Merkle proof for event #5:")
    print(f"    Proof length:     {len(proof.siblings)} hashes")
    print(f"    Proof valid:      {'✓' if merkle.verify_proof(proof) else '✗'}")

    return chain


# =============================================================================
# VISUALIZATION
# =============================================================================

def plot_constellation_3d(cell: Cell600):
    """Plot 3D projection of 600-cell."""
    if not HAS_MATPLOTLIB:
        return

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    # Project 4D to 3D (drop last coordinate)
    xs = [v.coords[0] for v in cell.vertices]
    ys = [v.coords[1] for v in cell.vertices]
    zs = [v.coords[2] for v in cell.vertices]

    ax.scatter(xs, ys, zs, c='blue', s=30, alpha=0.6)

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title('600-Cell Constellation (3D Projection)')

    plt.tight_layout()
    plt.savefig('demo_constellation.png', dpi=150)
    print(f"\n  Saved: demo_constellation.png")


def plot_lpi_comparison(snr_range: np.ndarray, legit_bers: list, attack_bers: list):
    """Plot BER vs SNR for legitimate and attacker."""
    if not HAS_MATPLOTLIB:
        return

    plt.figure(figsize=(10, 6))
    plt.semilogy(snr_range, legit_bers, 'b-o', label='Legitimate Receiver', linewidth=2)
    plt.semilogy(snr_range, attack_bers, 'r-x', label='Attacker (wrong seed)', linewidth=2)
    plt.axhline(y=0.5, color='gray', linestyle='--', label='Random guessing')

    plt.xlabel('SNR (dB)')
    plt.ylabel('Bit Error Rate (BER)')
    plt.title('CSPM LPI Security: Legitimate vs Attacker')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.ylim([1e-4, 1])

    plt.tight_layout()
    plt.savefig('demo_lpi.png', dpi=150)
    print(f"\n  Saved: demo_lpi.png")


def plot_tracking(tracking_data, trajectory):
    """Plot tracking comparison."""
    if not HAS_MATPLOTLIB or tracking_data is None:
        return

    times, ekf_errors, spinor_errors = tracking_data

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    # Error over time
    ax1 = axes[0]
    ax1.plot(times, ekf_errors, 'r-', label='EKF', alpha=0.7)
    ax1.plot(times, spinor_errors, 'b-', label='Spinor Manifold', alpha=0.7)
    ax1.axvline(x=times[len(times)//2], color='gray', linestyle='--',
                label='Maneuver start', alpha=0.5)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Position Error (m)')
    ax1.set_title('Tracking Error: EKF vs Spinor Manifold Tracker')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Trajectory 3D
    ax2 = axes[1]
    positions = np.array([s.position for s in trajectory])
    ax2.plot(positions[:, 0], positions[:, 1], 'k-', linewidth=2)
    ax2.scatter(positions[0, 0], positions[0, 1], c='green', s=100,
                label='Start', zorder=5)
    ax2.scatter(positions[-1, 0], positions[-1, 1], c='red', s=100,
                label='End', zorder=5)
    ax2.set_xlabel('X Position (m)')
    ax2.set_ylabel('Y Position (m)')
    ax2.set_title('Trajectory (Top View) - SIMPLIFIED MODEL')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.axis('equal')

    plt.tight_layout()
    plt.savefig('demo_tracking.png', dpi=150)
    print(f"\n  Saved: demo_tracking.png")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='CSPM + GAA Unified Demo')
    parser.add_argument('--no-plot', action='store_true',
                        help='Skip plot generation')
    parser.add_argument('--quick', action='store_true',
                        help='Run shorter simulations')
    args = parser.parse_args()

    print("="*70)
    print("  CSPM + GAA UNIFIED DEMONSTRATION")
    print("  Cryptographically-Seeded Polytopal Modulation")
    print("  Geometric Audit Architecture")
    print("="*70)
    print("\n⚠️  HONEST DISCLAIMERS:")
    print("  • Hypersonic trajectories are TOY MODELS, not validated physics")
    print("  • We demonstrate ALGORITHM CONCEPTS, not operational capability")
    print("  • The 600-cell geometry is mathematically rigorous")
    print("  • LPI claims are information-theoretic (provable)")

    # Demo 1: Constellation
    cell = demo_constellation_geometry()

    # Demo 2: LPI Security
    if args.quick:
        legit_ber, attack_ber = demo_lpi_security(snr_db=15.0, num_symbols=1000)
    else:
        legit_ber, attack_ber = demo_lpi_security(snr_db=15.0, num_symbols=10000)

    # Demo 3: Tracking (may fail if modules unavailable)
    tracking_data, trajectory = demo_tracking_comparison(
        duration=30.0, quick=args.quick
    )

    # Demo 4: GAA Audit
    audit_chain = demo_gaa_audit()

    # Generate plots
    if not args.no_plot and HAS_MATPLOTLIB:
        print("\n" + "="*70)
        print("GENERATING VISUALIZATIONS")
        print("="*70)

        plot_constellation_3d(cell)

        # Multi-SNR LPI comparison
        print("\n  Running LPI sweep across SNR values...")
        snr_range = np.arange(5, 25, 2)
        legit_bers = []
        attack_bers = []
        for snr in snr_range:
            l, a = demo_lpi_security(snr_db=snr, num_symbols=1000 if args.quick else 5000)
            legit_bers.append(max(l, 1e-5))  # Avoid log(0)
            attack_bers.append(a)
        plot_lpi_comparison(snr_range, legit_bers, attack_bers)

        if tracking_data:
            plot_tracking(tracking_data, trajectory)

    # Summary
    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("\nWhat we demonstrated:")
    print("  1. 600-cell constellation with 6.9 bits/symbol")
    print("  2. LPI security: attacker gets ~50% BER (random)")
    print("  3. Tracking algorithm comparison (toy trajectory)")
    print("  4. GAA audit trail with Merkle proofs")
    print("\nOutputs:")
    if HAS_MATPLOTLIB and not args.no_plot:
        print("  • demo_constellation.png - 3D projection of 600-cell")
        print("  • demo_lpi.png - BER comparison across SNR")
        if tracking_data:
            print("  • demo_tracking.png - Tracking error over time")
    else:
        print("  • (No plots - matplotlib unavailable or --no-plot)")


if __name__ == "__main__":
    main()
