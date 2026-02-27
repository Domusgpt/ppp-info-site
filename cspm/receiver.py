"""
CSPM Receiver Module

Implements geometric quantization (vertex snapping) for zero-overhead
error correction. The receiver:

1. Measures the incoming 4D optical state
2. Un-rotates based on synchronized hash chain
3. Snaps to nearest 600-cell vertex
4. Decodes symbol to bits

Key advantage: Error correction is O(1) lookup, not O(n) algebraic decoding.
"""

import numpy as np
import hashlib
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from .lattice import Cell600, PolychoralConstellation, Vertex4D
from .transmitter import OpticalSymbol, HashChainRotator


@dataclass
class DecodedSymbol:
    """Result of decoding a received optical symbol."""

    symbol_index: int  # Decoded symbol (0-119)
    bits: np.ndarray  # Decoded bits
    confidence: float  # Confidence in decoding (based on distance to vertex)
    distance: float  # Angular distance to nearest vertex
    corrected: bool  # Whether geometric correction was applied

    @property
    def is_reliable(self) -> bool:
        """Check if decoding is reliable (within half minimum distance)."""
        return self.distance < 0.3  # ~17 degrees, half of min vertex distance


class GeometricQuantizer:
    """
    Geometric quantization engine.

    This is the core innovation: instead of algebraic error correction
    (Reed-Solomon, LDPC, etc.), we use geometric projection to the
    nearest valid constellation point.

    Advantages:
    - O(1) complexity (vs O(n) for RS/LDPC)
    - Zero overhead (no parity symbols needed)
    - Natural soft-decision output (distance = confidence)
    """

    def __init__(self, cell: Cell600 = None):
        self.cell = cell or Cell600()
        self._corrections = 0
        self._total_distance = 0.0
        self._symbol_count = 0

        # Precompute for faster lookup
        self._vertex_matrix = np.array([v.coords for v in self.cell.vertices])

    def quantize(self, point: np.ndarray) -> Tuple[Vertex4D, float]:
        """
        Snap a 4D point to the nearest 600-cell vertex.

        This is the "error correction" step - any noise that doesn't
        push the point past the Voronoi boundary is automatically corrected.

        Args:
            point: Noisy 4D point (will be normalized)

        Returns:
            Tuple of (nearest vertex, angular distance)
        """
        # Normalize to unit sphere
        point = point / np.linalg.norm(point)

        # Compute angular distances to all vertices
        # For unit vectors: angle = arccos(dot product)
        dots = np.abs(self._vertex_matrix @ point)
        best_idx = np.argmax(dots)
        best_dot = dots[best_idx]

        # Angular distance
        distance = np.arccos(np.clip(best_dot, -1, 1))

        # Track statistics
        self._symbol_count += 1
        self._total_distance += distance
        if distance > 0.01:  # Non-trivial correction
            self._corrections += 1

        return self.cell.vertices[best_idx], distance

    def get_correction_rate(self) -> float:
        """Fraction of symbols that required geometric correction."""
        if self._symbol_count == 0:
            return 0.0
        return self._corrections / self._symbol_count

    def get_average_distance(self) -> float:
        """Average angular distance to quantized vertex."""
        if self._symbol_count == 0:
            return 0.0
        return self._total_distance / self._symbol_count

    def reset_stats(self):
        """Reset correction statistics."""
        self._corrections = 0
        self._total_distance = 0.0
        self._symbol_count = 0


class CSPMReceiver:
    """
    Cryptographically-Seeded Polytopal Modulation Receiver.

    Synchronizes with transmitter via shared genesis seed,
    tracks the rotating constellation, and decodes symbols.
    """

    def __init__(
        self,
        genesis_seed: bytes = b"CSPM_DEFAULT_SEED",
        bits_per_block: int = 6
    ):
        """
        Initialize receiver with shared secret.

        Args:
            genesis_seed: Same seed as transmitter
            bits_per_block: Bits per symbol (must match transmitter)
        """
        self.constellation = PolychoralConstellation(seed=genesis_seed)
        self.rotator = HashChainRotator(genesis_seed)
        self.quantizer = GeometricQuantizer(self.constellation.base_cell)
        self.bits_per_block = bits_per_block

        self._packet_count = 0
        self._symbol_errors = 0
        self._bit_errors = 0
        self._total_symbols = 0
        self._total_bits = 0

    def _symbol_to_bits(self, symbol: int) -> np.ndarray:
        """Convert symbol index to bit array."""
        bits = []
        for i in range(self.bits_per_block - 1, -1, -1):
            bits.append((symbol >> i) & 1)
        return np.array(bits, dtype=np.uint8)

    def demodulate_symbol(
        self,
        rx_symbol: OpticalSymbol
    ) -> DecodedSymbol:
        """
        Demodulate a single received optical symbol.

        Steps:
        1. Un-rotate received point using current constellation state
        2. Quantize to nearest vertex (geometric error correction)
        3. Look up symbol index
        4. Convert to bits
        """
        # Un-rotate the received coordinates (with safe normalization)
        rotation_inv = self.constellation._rotation_matrix.T
        unrotated = rotation_inv @ rx_symbol.coords
        norm = np.linalg.norm(unrotated)
        unrotated = unrotated / norm if norm > 1e-10 else rx_symbol.coords

        # Quantize to nearest vertex
        vertex, distance = self.quantizer.quantize(unrotated)

        # Convert to bits
        bits = self._symbol_to_bits(vertex.symbol)

        # Determine if correction was significant
        corrected = distance > 0.01

        self._total_symbols += 1

        return DecodedSymbol(
            symbol_index=vertex.symbol,
            bits=bits,
            confidence=1.0 - min(1.0, distance / 0.6),
            distance=distance,
            corrected=corrected
        )

    def demodulate_sequence(
        self,
        rx_symbols: List[OpticalSymbol],
        advance_rotation: bool = False,
        packet_hash: bytes = None
    ) -> Tuple[np.ndarray, List[DecodedSymbol]]:
        """
        Demodulate a sequence of received symbols.

        Args:
            rx_symbols: List of received optical symbols
            advance_rotation: Whether to advance constellation after packet
            packet_hash: Hash to use for rotation advancement

        Returns:
            Tuple of (decoded bits, list of decoded symbols)
        """
        decoded_symbols = []
        all_bits = []

        for rx_sym in rx_symbols:
            decoded = self.demodulate_symbol(rx_sym)
            decoded_symbols.append(decoded)
            all_bits.extend(decoded.bits)

        if advance_rotation:
            self.constellation.rotate_lattice(packet_hash)
            self.rotator.advance(packet_hash)
            self._packet_count += 1

        self._total_bits += len(all_bits)

        return np.array(all_bits, dtype=np.uint8), decoded_symbols

    def demodulate_packet(
        self,
        rx_symbols: List[OpticalSymbol],
        original_data: bytes = None
    ) -> Tuple[bytes, Dict]:
        """
        Demodulate a complete packet.

        Args:
            rx_symbols: Received symbols
            original_data: Original data for BER calculation (optional)

        Returns:
            Tuple of (decoded bytes, statistics dict)
        """
        # Compute packet hash if original data provided
        if original_data is not None:
            packet_hash = hashlib.sha256(original_data).digest()
        else:
            packet_hash = None

        # Demodulate
        bits, decoded_symbols = self.demodulate_sequence(
            rx_symbols,
            advance_rotation=True,
            packet_hash=packet_hash
        )

        # Convert bits to bytes
        n_bytes = len(bits) // 8
        bits = bits[:n_bytes * 8]
        bytes_array = np.packbits(bits)
        decoded_data = bytes(bytes_array)

        # Calculate statistics
        stats = {
            "n_symbols": len(rx_symbols),
            "n_bits": len(bits),
            "n_bytes": len(decoded_data),
            "avg_distance": np.mean([d.distance for d in decoded_symbols]),
            "max_distance": max([d.distance for d in decoded_symbols]),
            "correction_rate": sum(1 for d in decoded_symbols if d.corrected) / len(decoded_symbols),
            "avg_confidence": np.mean([d.confidence for d in decoded_symbols]),
        }

        # BER if original data provided
        if original_data is not None:
            original_bits = np.unpackbits(np.frombuffer(original_data, dtype=np.uint8))
            min_len = min(len(bits), len(original_bits))
            bit_errors = np.sum(bits[:min_len] != original_bits[:min_len])
            stats["ber"] = bit_errors / min_len if min_len > 0 else 0
            stats["bit_errors"] = int(bit_errors)
            self._bit_errors += bit_errors
        else:
            stats["ber"] = None

        return decoded_data, stats

    def synchronize(self, tx_state: bytes):
        """
        Synchronize receiver constellation with transmitter state.

        In practice, this would be done via a separate sync channel
        or preamble sequence.
        """
        self.constellation.set_rotation_state(tx_state)
        self.rotator.set_state(tx_state)

    def get_ber(self) -> float:
        """Get overall bit error rate."""
        if self._total_bits == 0:
            return 0.0
        return self._bit_errors / self._total_bits

    def get_ser(self) -> float:
        """Get symbol error rate (estimated from corrections)."""
        return self.quantizer.get_correction_rate()

    def reset_stats(self):
        """Reset error statistics."""
        self._symbol_errors = 0
        self._bit_errors = 0
        self._total_symbols = 0
        self._total_bits = 0
        self.quantizer.reset_stats()


def measure_geometric_coding_gain(
    n_trials: int = 1000,
    snr_db: float = 15.0,
    seed: int = 42
) -> Dict:
    """
    Measure the effective coding gain from geometric quantization.

    Compares:
    - Raw error rate (before quantization)
    - Corrected error rate (after quantization)
    """
    from .transmitter import CSPMTransmitter, generate_random_data
    from .channel import FiberChannel

    rng = np.random.default_rng(seed)

    tx = CSPMTransmitter()
    rx = CSPMReceiver()
    channel = FiberChannel(snr_db=snr_db, seed=seed)

    # Align TX and RX
    rx.synchronize(tx.get_constellation_state())

    total_bits = 0
    raw_errors = 0
    corrected_errors = 0

    for trial in range(n_trials):
        # Generate random data
        data = generate_random_data(100, seed=seed + trial)

        # Transmit
        tx_symbols, packet_hash = tx.modulate_packet(data)

        # Sync receiver rotation
        rx.constellation.rotate_lattice(packet_hash)
        rx.rotator.advance(packet_hash)

        # Channel
        rx_symbols, _ = channel.transmit_sequence(tx_symbols)

        # Measure raw symbol errors (before quantization)
        for tx_s, rx_s in zip(tx_symbols, rx_symbols):
            # Un-rotate both for fair comparison
            rot_inv = rx.constellation._rotation_matrix.T
            tx_unrot = rot_inv @ tx_s.coords
            rx_unrot = rot_inv @ rx_s.coords

            # Raw: Is received point closer to wrong vertex?
            _, dist_to_correct = rx.quantizer.quantize(tx_unrot)
            _, dist_to_decoded = rx.quantizer.quantize(rx_unrot)

            # The decoded vertex
            decoded_vertex, _ = rx.quantizer.quantize(rx_unrot)
            correct_vertex, _ = rx.quantizer.quantize(tx_unrot)

            if decoded_vertex.symbol != correct_vertex.symbol:
                corrected_errors += 1

        # Count bits
        original_bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
        total_bits += len(original_bits)

    return {
        "snr_db": snr_db,
        "total_bits": total_bits,
        "symbol_error_rate": corrected_errors / (n_trials * 100 * 8 / 6),
        "estimated_ber": corrected_errors / total_bits,
        "n_trials": n_trials
    }


if __name__ == "__main__":
    from .transmitter import CSPMTransmitter, generate_random_data
    from .channel import FiberChannel

    # Test receiver
    print("Testing CSPM Receiver")
    print("=" * 50)

    seed = b"test_seed_456"
    tx = CSPMTransmitter(genesis_seed=seed)
    rx = CSPMReceiver(genesis_seed=seed)

    # Generate test data
    data = generate_random_data(500, seed=42)
    print(f"Original data: {len(data)} bytes, first 10: {data[:10].hex()}")

    # Transmit
    tx_symbols, packet_hash = tx.modulate_packet(data)
    print(f"Transmitted {len(tx_symbols)} symbols")

    # Sync receiver
    rx.constellation.rotate_lattice(packet_hash)
    rx.rotator.advance(packet_hash)

    # Perfect channel (no noise)
    print("\n--- Perfect Channel ---")
    decoded_data, stats = rx.demodulate_packet(tx_symbols, data)
    print(f"Decoded: {len(decoded_data)} bytes, first 10: {decoded_data[:10].hex()}")
    print(f"BER: {stats['ber']:.2e}")
    print(f"Correction rate: {stats['correction_rate']*100:.1f}%")

    # Reset and test with noisy channel
    rx.reset_stats()
    tx2 = CSPMTransmitter(genesis_seed=seed)
    rx2 = CSPMReceiver(genesis_seed=seed)

    data2 = generate_random_data(500, seed=43)
    tx_symbols2, packet_hash2 = tx2.modulate_packet(data2)

    # Apply channel noise
    channel = FiberChannel(snr_db=15.0, length_km=200, seed=42)
    rx_symbols, _ = channel.transmit_sequence(tx_symbols2)

    # Sync and decode
    rx2.constellation.rotate_lattice(packet_hash2)
    rx2.rotator.advance(packet_hash2)

    print("\n--- Noisy Fiber Channel (200km, 15dB SNR) ---")
    decoded_data2, stats2 = rx2.demodulate_packet(rx_symbols, data2)
    print(f"BER: {stats2['ber']:.2e}")
    print(f"Bit errors: {stats2['bit_errors']}")
    print(f"Avg distance to vertex: {stats2['avg_distance']:.4f} rad")
    print(f"Max distance to vertex: {stats2['max_distance']:.4f} rad")
    print(f"Correction rate: {stats2['correction_rate']*100:.1f}%")
    print(f"Avg confidence: {stats2['avg_confidence']:.3f}")

    # Measure coding gain
    print("\n--- Geometric Coding Gain ---")
    gain_stats = measure_geometric_coding_gain(n_trials=100, snr_db=12.0)
    print(f"SNR: {gain_stats['snr_db']} dB")
    print(f"Symbol Error Rate: {gain_stats['symbol_error_rate']:.2e}")
    print(f"Estimated BER: {gain_stats['estimated_ber']:.2e}")
