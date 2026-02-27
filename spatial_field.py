#!/usr/bin/env python3
"""
Spatial Field CSPM - Multi-Transmitter Geometric Encoding

Demonstrates distributed CSPM where multiple transmitters create
a "geometric field" that receivers can sample for:
1. Data decoding from each transmitter
2. Position estimation via triangulation
3. Orientation recovery from quaternion constellation

This is EXPERIMENTAL - proving the concept, not operational code.

Usage:
    python spatial_field.py [--num-tx N] [--snr DB]

Copyright (c) 2025-2026 Clear Seas Solutions LLC
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import argparse

from cspm.lattice import Cell600, PolychoralConstellation


@dataclass
class SpatialNode:
    """A node in the spatial CSPM network (TX or RX)."""
    position: np.ndarray  # [x, y, z] in meters
    node_id: str
    seed: bytes = b"DEFAULT_SEED"
    constellation: Optional[PolychoralConstellation] = None

    def __post_init__(self):
        if self.constellation is None:
            self.constellation = PolychoralConstellation(seed=self.seed)


@dataclass
class SpatialObservation:
    """What a receiver observes from the spatial field."""
    combined_signal: np.ndarray  # 4D superposition
    individual_contributions: Dict[str, np.ndarray]  # Per-TX signals
    attenuations: Dict[str, float]  # Path loss per TX
    noise: np.ndarray  # Added noise


class SpatialCSPMField:
    """
    Multi-transmitter CSPM spatial field.

    Multiple TXs each transmit symbols from the 600-cell.
    The field is the superposition of all transmissions,
    attenuated by distance (inverse square law).
    """

    def __init__(self, tx_nodes: List[SpatialNode], shared_seed: bytes = b"NETWORK_SEED"):
        """
        Initialize spatial field with transmitter nodes.

        Args:
            tx_nodes: List of transmitter nodes with positions
            shared_seed: Base seed for hash chain synchronization
        """
        self.tx_nodes = tx_nodes
        self.shared_seed = shared_seed

        # Initialize each TX with derived seed
        for i, node in enumerate(self.tx_nodes):
            node.seed = shared_seed + f"_TX{i}".encode()
            node.constellation = PolychoralConstellation(seed=node.seed)

    def transmit(self, symbols: Dict[str, int]) -> None:
        """
        Set symbols to transmit from each TX.

        Args:
            symbols: Dict mapping node_id to symbol (0-119)
        """
        self._current_symbols = symbols

    def observe(
        self,
        rx_position: np.ndarray,
        snr_db: float = 20.0
    ) -> SpatialObservation:
        """
        Compute what a receiver at given position observes.

        Args:
            rx_position: [x, y, z] receiver position
            snr_db: Signal-to-noise ratio in dB

        Returns:
            SpatialObservation with combined signal and metadata
        """
        combined = np.zeros(4)
        contributions = {}
        attenuations = {}

        total_power = 0.0

        for node in self.tx_nodes:
            # Compute distance and attenuation
            distance = np.linalg.norm(rx_position - node.position)
            distance = max(distance, 1.0)  # Avoid divide by zero
            attenuation = 1.0 / (distance ** 2)

            # Get transmitted symbol
            symbol = self._current_symbols.get(node.node_id, 0)

            # Encode to 4D point
            encoded = node.constellation.encode_symbol(symbol)

            # Attenuate and add to combined signal
            contribution = attenuation * encoded
            combined += contribution

            contributions[node.node_id] = contribution
            attenuations[node.node_id] = attenuation
            total_power += attenuation

        # Normalize combined signal to unit sphere
        norm = np.linalg.norm(combined)
        if norm > 1e-10:
            combined = combined / norm

        # Add noise
        snr_linear = 10 ** (snr_db / 10)
        noise_std = 1.0 / np.sqrt(2 * snr_linear)
        noise = np.random.randn(4) * noise_std

        noisy_signal = combined + noise
        noisy_signal = noisy_signal / np.linalg.norm(noisy_signal)

        return SpatialObservation(
            combined_signal=noisy_signal,
            individual_contributions=contributions,
            attenuations=attenuations,
            noise=noise
        )

    def rotate_all(self, packet_data: bytes) -> None:
        """Advance hash chains on all TXs (synchronized rotation)."""
        for node in self.tx_nodes:
            node.constellation.rotate_lattice(packet_data)


class SpatialReceiver:
    """
    Receiver that can decode from spatial CSPM field.

    With multiple observations (from different positions or times),
    can perform:
    1. Symbol decoding per TX
    2. Position estimation
    3. Orientation recovery
    """

    def __init__(self, tx_nodes: List[SpatialNode], shared_seed: bytes = b"NETWORK_SEED"):
        """
        Initialize receiver with knowledge of TX positions and seeds.

        Args:
            tx_nodes: List of known transmitter nodes
            shared_seed: Base seed for hash chain synchronization
        """
        # Create local copies of constellations (synchronized)
        self.tx_refs = []
        for i, node in enumerate(tx_nodes):
            ref = SpatialNode(
                position=node.position.copy(),
                node_id=node.node_id,
                seed=shared_seed + f"_TX{i}".encode()
            )
            self.tx_refs.append(ref)

    def decode_single_dominant(
        self,
        observation: SpatialObservation,
        rx_position: np.ndarray
    ) -> Dict[str, Tuple[int, float]]:
        """
        Decode assuming one TX dominates (closest).

        This is the simple case - works when TXs are well-separated.

        Returns:
            Dict mapping node_id to (decoded_symbol, confidence)
        """
        results = {}

        # Find which TX should dominate based on geometry
        distances = {}
        for ref in self.tx_refs:
            dist = np.linalg.norm(rx_position - ref.position)
            distances[ref.node_id] = dist

        # Decode using dominant TX's constellation
        dominant_id = min(distances, key=distances.get)
        dominant_ref = next(r for r in self.tx_refs if r.node_id == dominant_id)

        decoded, dist = dominant_ref.constellation.decode_symbol(
            observation.combined_signal
        )

        # Confidence based on how much this TX dominates
        total_inv_dist = sum(1/d**2 for d in distances.values())
        dominant_power = (1/distances[dominant_id]**2) / total_inv_dist

        results[dominant_id] = (decoded, dominant_power)

        return results

    def estimate_position(
        self,
        observations: List[Tuple[np.ndarray, SpatialObservation]],
        initial_guess: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """
        Estimate RX position from multiple observations.

        Uses signal strengths (attenuations) to triangulate.

        Args:
            observations: List of (rx_position, observation) tuples
            initial_guess: Starting position estimate

        Returns:
            (estimated_position, residual_error)
        """
        if len(observations) < 3:
            return initial_guess, float('inf')

        # Simple weighted centroid based on observed attenuations
        # (Real implementation would use proper triangulation)

        position_sum = np.zeros(3)
        weight_sum = 0.0

        for rx_pos, obs in observations:
            for node_id, atten in obs.attenuations.items():
                ref = next(r for r in self.tx_refs if r.node_id == node_id)
                # Weight by attenuation (higher = closer to this TX)
                weight = atten
                position_sum += weight * ref.position
                weight_sum += weight

        estimated = position_sum / weight_sum if weight_sum > 0 else initial_guess

        # Compute residual
        residual = np.linalg.norm(estimated - initial_guess)

        return estimated, residual

    def rotate_all(self, packet_data: bytes) -> None:
        """Advance hash chains on all reference constellations."""
        for ref in self.tx_refs:
            ref.constellation.rotate_lattice(packet_data)


def demo_spatial_field():
    """Demonstrate spatial CSPM field with 3 transmitters."""
    print("="*70)
    print("SPATIAL CSPM FIELD DEMONSTRATION")
    print("="*70)
    print("\n⚠️  EXPERIMENTAL: Proving concept, not operational code")

    # Create 3 transmitters in a triangle
    tx_positions = [
        np.array([0.0, 0.0, 0.0]),      # Origin
        np.array([100.0, 0.0, 0.0]),    # 100m along X
        np.array([50.0, 86.6, 0.0]),    # Equilateral triangle
    ]

    tx_nodes = [
        SpatialNode(position=pos, node_id=f"TX{i}")
        for i, pos in enumerate(tx_positions)
    ]

    print(f"\nTransmitter Positions:")
    for node in tx_nodes:
        print(f"  {node.node_id}: {node.position}")

    # Create spatial field
    field = SpatialCSPMField(tx_nodes, shared_seed=b"DEMO_NETWORK")

    # Create receiver
    receiver = SpatialReceiver(tx_nodes, shared_seed=b"DEMO_NETWORK")

    # Test receiver at known position
    rx_position = np.array([50.0, 30.0, 0.0])  # Inside the triangle
    print(f"\nReceiver Position: {rx_position}")

    # Transmit different symbols from each TX
    symbols = {"TX0": 42, "TX1": 77, "TX2": 13}
    field.transmit(symbols)

    print(f"\nTransmitted Symbols: {symbols}")

    # Observe at receiver position
    obs = field.observe(rx_position, snr_db=25.0)

    print(f"\nObservation:")
    print(f"  Combined signal: {obs.combined_signal[:2]}...")
    print(f"  Attenuations:")
    for node_id, atten in obs.attenuations.items():
        print(f"    {node_id}: {atten:.4f}")

    # Decode (simple dominant TX method)
    decoded = receiver.decode_single_dominant(obs, rx_position)
    print(f"\nDecoded (dominant TX method):")
    for node_id, (symbol, confidence) in decoded.items():
        correct = symbols.get(node_id, -1) == symbol
        print(f"  {node_id}: symbol={symbol}, confidence={confidence:.2f}, "
              f"correct={'✓' if correct else '✗'}")

    # Test LPI: attacker without correct seed
    print("\n" + "-"*70)
    print("LPI TEST: Attacker vs Legitimate Receiver")
    print("-"*70)

    # Run multiple packets with rotation
    legit_correct = 0
    attack_correct = 0
    num_packets = 100

    # Create attacker receiver with wrong seed
    attacker = SpatialReceiver(tx_nodes, shared_seed=b"WRONG_SEED")

    for packet in range(num_packets):
        # Random symbols
        symbols = {f"TX{i}": np.random.randint(0, 120) for i in range(3)}
        field.transmit(symbols)

        # Observe
        obs = field.observe(rx_position, snr_db=20.0)

        # Legitimate decode
        legit_decoded = receiver.decode_single_dominant(obs, rx_position)
        for node_id, (symbol, _) in legit_decoded.items():
            if symbols.get(node_id) == symbol:
                legit_correct += 1

        # Attacker decode
        attack_decoded = attacker.decode_single_dominant(obs, rx_position)
        for node_id, (symbol, _) in attack_decoded.items():
            if symbols.get(node_id) == symbol:
                attack_correct += 1

        # Rotate (synchronized for legit, desync for attacker)
        packet_data = f"packet_{packet}".encode()
        field.rotate_all(packet_data)
        receiver.rotate_all(packet_data)
        attacker.rotate_all(packet_data)  # Attacker rotates but from wrong state

    legit_acc = legit_correct / num_packets
    attack_acc = attack_correct / num_packets

    print(f"\nResults over {num_packets} packets:")
    print(f"  Legitimate accuracy: {legit_acc*100:.1f}%")
    print(f"  Attacker accuracy:   {attack_acc*100:.1f}%")
    print(f"  Random baseline:     {100/120:.1f}%")

    if attack_acc < 0.1:
        print(f"\n✓ LPI EFFECTIVE in spatial field configuration")
    else:
        print(f"\n⚠ Check rotation synchronization")

    # Position estimation demo
    print("\n" + "-"*70)
    print("POSITION ESTIMATION TEST")
    print("-"*70)

    # Collect observations from multiple positions (simulating movement)
    observations = []
    true_positions = [
        np.array([50.0, 30.0, 0.0]),
        np.array([45.0, 35.0, 0.0]),
        np.array([55.0, 25.0, 0.0]),
    ]

    for pos in true_positions:
        obs = field.observe(pos, snr_db=30.0)
        observations.append((pos, obs))

    # Estimate position
    initial_guess = np.array([50.0, 30.0, 0.0])
    estimated, residual = receiver.estimate_position(observations, initial_guess)

    print(f"\nTrue centroid: {np.mean(true_positions, axis=0)}")
    print(f"Estimated:     {estimated}")
    print(f"Residual:      {residual:.2f}m")

    print("\n" + "="*70)
    print("SPATIAL FIELD DEMO COMPLETE")
    print("="*70)


def main():
    parser = argparse.ArgumentParser(description='Spatial CSPM Field Demo')
    parser.add_argument('--num-tx', type=int, default=3,
                        help='Number of transmitters')
    parser.add_argument('--snr', type=float, default=20.0,
                        help='SNR in dB')
    args = parser.parse_args()

    np.random.seed(42)
    demo_spatial_field()


if __name__ == "__main__":
    main()
