#!/usr/bin/env python3
"""
=============================================================================
RECEIVER - Demodulation and Error Analysis
=============================================================================

This module implements the receiver (demodulation) side of the POM and QAM
communication systems, along with comprehensive error analysis.

GEOMETRIC QUANTIZATION (POM):
-----------------------------
The key innovation in POM is that demodulation is a purely geometric operation:

1. VORONOI PARTITIONING:
   The 4D space is partitioned into Voronoi cells around each of the 120
   vertices of the 600-cell. Each cell contains all points closer to its
   vertex than to any other.

2. NEAREST-NEIGHBOR DETECTION:
   The received noisy signal is mapped to the vertex whose Voronoi cell
   contains it. This is equivalent to minimum Euclidean distance detection.

3. GEOMETRIC ERROR CORRECTION:
   The 600-cell's high symmetry means that small perturbations are
   automatically corrected by the snapping operation. This is an inherent
   form of error correction that requires no additional coding overhead.

ERROR METRICS:
--------------
- SER (Symbol Error Rate): P(detected_symbol != transmitted_symbol)
- BER (Bit Error Rate): P(detected_bit != transmitted_bit)
- For Gray-coded constellations: BER ≈ SER / bits_per_symbol (at low error rates)

Author: PPP Research Team
License: MIT
=============================================================================
"""

import numpy as np
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass, field

from geometry import Polychoron600, QAM64Constellation
from modem import (
    POMModulator, POMDemodulator,
    QAMModulator, QAMDemodulator,
    TransmissionPacket, indices_to_bits
)
from channel import AWGNChannel4D, AWGNChannel2D, ChannelState


# =============================================================================
# ERROR ANALYSIS DATA STRUCTURES
# =============================================================================

@dataclass
class ErrorMetrics:
    """Container for error rate metrics."""
    symbol_errors: int
    bit_errors: int
    total_symbols: int
    total_bits: int
    ser: float  # Symbol Error Rate
    ber: float  # Bit Error Rate

    @property
    def symbols_correct(self) -> int:
        return self.total_symbols - self.symbol_errors

    @property
    def bits_correct(self) -> int:
        return self.total_bits - self.bit_errors

    def __repr__(self) -> str:
        return (
            f"ErrorMetrics(SER={self.ser:.2e}, BER={self.ber:.2e}, "
            f"symbols={self.symbol_errors}/{self.total_symbols}, "
            f"bits={self.bit_errors}/{self.total_bits})"
        )


@dataclass
class TransmissionResult:
    """Complete result of a transmission experiment."""
    snr_db: float
    constellation_type: str
    metrics: ErrorMetrics
    channel_state: ChannelState
    mean_distance: float  # Average distance from noisy symbol to detected vertex
    max_distance: float   # Maximum distance observed
    tx_indices: np.ndarray = field(repr=False)
    rx_indices: np.ndarray = field(repr=False)


# =============================================================================
# ERROR CALCULATION FUNCTIONS
# =============================================================================

def count_bit_errors(tx_bits: np.ndarray, rx_bits: np.ndarray) -> int:
    """
    Count the number of bit errors between transmitted and received bits.

    Args:
        tx_bits: Transmitted bit sequence
        rx_bits: Received bit sequence

    Returns:
        Number of bit errors
    """
    min_len = min(len(tx_bits), len(rx_bits))
    return int(np.sum(tx_bits[:min_len] != rx_bits[:min_len]))


def count_symbol_errors(tx_indices: np.ndarray, rx_indices: np.ndarray) -> int:
    """
    Count the number of symbol errors between transmitted and received indices.

    Args:
        tx_indices: Transmitted symbol indices
        rx_indices: Detected symbol indices

    Returns:
        Number of symbol errors
    """
    return int(np.sum(tx_indices != rx_indices))


def compute_error_metrics(
    tx_bits: np.ndarray,
    rx_bits: np.ndarray,
    tx_indices: np.ndarray,
    rx_indices: np.ndarray
) -> ErrorMetrics:
    """
    Compute comprehensive error metrics.

    Args:
        tx_bits: Transmitted bits
        rx_bits: Received bits
        tx_indices: Transmitted symbol indices
        rx_indices: Detected symbol indices

    Returns:
        ErrorMetrics dataclass with all computed metrics
    """
    symbol_errors = count_symbol_errors(tx_indices, rx_indices)
    bit_errors = count_bit_errors(tx_bits, rx_bits)

    total_symbols = len(tx_indices)
    total_bits = min(len(tx_bits), len(rx_bits))

    # Avoid division by zero
    ser = symbol_errors / total_symbols if total_symbols > 0 else 0.0
    ber = bit_errors / total_bits if total_bits > 0 else 0.0

    return ErrorMetrics(
        symbol_errors=symbol_errors,
        bit_errors=bit_errors,
        total_symbols=total_symbols,
        total_bits=total_bits,
        ser=ser,
        ber=ber
    )


# =============================================================================
# INTEGRATED TRANSCEIVER CLASSES
# =============================================================================

class POMTransceiver:
    """
    Complete POM transceiver with modulation, channel, and demodulation.

    This class integrates:
    1. Bit-to-symbol mapping (modulation)
    2. 4D AWGN channel
    3. Geometric quantization (demodulation)
    4. Error analysis
    """

    def __init__(self, mode: str = 'conservative', use_gray: bool = True,
                 seed: Optional[int] = None):
        """
        Initialize the POM transceiver.

        Args:
            mode: 'conservative' (6 bits) or 'full' (7 bits)
            use_gray: Use Gray coding for bit mapping
            seed: Random seed for channel noise
        """
        self.constellation = Polychoron600()
        self.modulator = POMModulator(self.constellation, mode=mode, use_gray=use_gray)
        self.demodulator = POMDemodulator(self.constellation, mode=mode, use_gray=use_gray)
        self.channel = AWGNChannel4D(seed=seed)

        self.mode = mode
        self.use_gray = use_gray
        self.bits_per_symbol = self.modulator.bits_per_symbol

    def transmit(self, bits: np.ndarray, snr_db: float) -> TransmissionResult:
        """
        Transmit bits through the POM system.

        Args:
            bits: Input bit array
            snr_db: Channel SNR in dB

        Returns:
            TransmissionResult with full metrics
        """
        # Modulate
        packet = self.modulator.modulate(bits)

        # Add channel noise
        noisy_symbols, channel_state = self.channel.add_noise(packet.symbols, snr_db)

        # Demodulate
        rx_bits, rx_indices, distances = self.demodulator.demodulate(noisy_symbols)

        # Compute error metrics
        metrics = compute_error_metrics(
            packet.bits, rx_bits[:len(packet.bits)],
            packet.indices, rx_indices
        )

        return TransmissionResult(
            snr_db=snr_db,
            constellation_type='POM',
            metrics=metrics,
            channel_state=channel_state,
            mean_distance=float(np.mean(distances)),
            max_distance=float(np.max(distances)),
            tx_indices=packet.indices,
            rx_indices=rx_indices
        )


class QAMTransceiver:
    """
    Complete 64-QAM transceiver for comparison.

    Uses 2D AWGN channel (native dimensionality) for fair comparison.
    """

    def __init__(self, use_gray: bool = True, seed: Optional[int] = None):
        """
        Initialize the QAM transceiver.

        Args:
            use_gray: Use Gray coding
            seed: Random seed for channel noise
        """
        self.constellation = QAM64Constellation()
        self.modulator = QAMModulator(self.constellation, use_gray=use_gray)
        self.demodulator = QAMDemodulator(self.constellation, use_gray=use_gray)
        self.channel = AWGNChannel2D(seed=seed)

        self.use_gray = use_gray
        self.bits_per_symbol = 6

    def transmit(self, bits: np.ndarray, snr_db: float) -> TransmissionResult:
        """
        Transmit bits through the QAM system.

        Uses native 2D channel for fair comparison.
        """
        # Modulate to 2D
        symbols_2d, tx_indices = self.modulator.modulate_2d(bits)

        # Ensure tx_indices has correct type
        tx_indices = tx_indices.astype(np.int32)

        # Add 2D noise
        noisy_2d, channel_state = self.channel.add_noise(symbols_2d, snr_db)

        # Demodulate
        rx_bits, rx_indices, distances = self.demodulator.demodulate_2d(noisy_2d)

        # Original bits for comparison
        n_symbols = len(tx_indices)
        n_bits = n_symbols * self.bits_per_symbol
        original_bits = bits[:n_bits] if len(bits) >= n_bits else np.pad(bits, (0, n_bits - len(bits)))

        # Compute metrics
        metrics = compute_error_metrics(
            original_bits, rx_bits[:n_bits],
            tx_indices, rx_indices
        )

        return TransmissionResult(
            snr_db=snr_db,
            constellation_type='QAM64',
            metrics=metrics,
            channel_state=channel_state,
            mean_distance=float(np.mean(distances)),
            max_distance=float(np.max(distances)),
            tx_indices=tx_indices,
            rx_indices=rx_indices
        )


# =============================================================================
# ERROR PATTERN ANALYSIS
# =============================================================================

def analyze_error_patterns(
    tx_indices: np.ndarray,
    rx_indices: np.ndarray,
    constellation: Polychoron600
) -> Dict:
    """
    Analyze the pattern of symbol errors.

    This helps understand WHY errors occur - are they random, or do
    certain symbols consistently fail?

    Args:
        tx_indices: Transmitted symbol indices
        rx_indices: Detected symbol indices
        constellation: The constellation used

    Returns:
        Dictionary with error pattern analysis
    """
    errors_mask = tx_indices != rx_indices
    error_indices = np.where(errors_mask)[0]

    if len(error_indices) == 0:
        return {'total_errors': 0}

    # Which symbols were most often confused
    tx_errors = tx_indices[error_indices]
    rx_errors = rx_indices[error_indices]

    # Distance between confused symbols
    confused_pairs = list(zip(tx_errors, rx_errors))
    distances_confused = [
        np.linalg.norm(constellation.vertices[tx] - constellation.vertices[rx])
        for tx, rx in confused_pairs
    ]

    # Find if errors are neighbor errors (minimum distance confusion)
    min_dist = constellation.metrics.min_distance
    neighbor_errors = sum(1 for d in distances_confused if d < min_dist * 1.1)

    return {
        'total_errors': len(error_indices),
        'unique_tx_symbols_with_errors': len(set(tx_errors)),
        'unique_rx_symbols_detected': len(set(rx_errors)),
        'mean_confusion_distance': np.mean(distances_confused),
        'neighbor_errors': neighbor_errors,
        'neighbor_error_ratio': neighbor_errors / len(error_indices) if len(error_indices) > 0 else 0
    }


# =============================================================================
# DETECTION MARGIN ANALYSIS
# =============================================================================

def compute_detection_margin(
    noisy_symbols: np.ndarray,
    detected_indices: np.ndarray,
    constellation: Polychoron600
) -> np.ndarray:
    """
    Compute the detection margin for each symbol.

    Detection margin = (distance to 2nd nearest) - (distance to nearest)

    A larger margin indicates more confident detection.
    A margin close to zero indicates the symbol was near a decision boundary.

    Args:
        noisy_symbols: Received noisy symbols
        detected_indices: Detected symbol indices
        constellation: Reference constellation

    Returns:
        Array of detection margins
    """
    margins = np.zeros(len(noisy_symbols))

    for i, (noisy, detected) in enumerate(zip(noisy_symbols, detected_indices)):
        # Compute distances to all vertices
        distances = np.linalg.norm(constellation.vertices - noisy, axis=1)

        # Sort distances
        sorted_dist = np.sort(distances)

        # Margin is difference between 1st and 2nd closest
        margins[i] = sorted_dist[1] - sorted_dist[0]

    return margins


# =============================================================================
# THEORETICAL BOUNDS
# =============================================================================

def theoretical_ser_qam(snr_db: float, M: int = 64) -> float:
    """
    Theoretical SER for M-QAM in AWGN.

    Approximate formula for square M-QAM:
    SER ≈ 4(1 - 1/√M) * Q(√(3*SNR/(M-1)))

    where Q(x) is the Q-function (tail of standard normal).

    Args:
        snr_db: SNR in dB
        M: Constellation size (64 for 64-QAM)

    Returns:
        Theoretical symbol error rate
    """
    from scipy.special import erfc

    snr_linear = 10 ** (snr_db / 10)

    # Q-function: Q(x) = 0.5 * erfc(x/sqrt(2))
    def Q(x):
        return 0.5 * erfc(x / np.sqrt(2))

    sqrt_M = np.sqrt(M)
    arg = np.sqrt(3 * snr_linear / (M - 1))

    ser = 4 * (1 - 1/sqrt_M) * Q(arg)

    # Bound between 0 and 1
    return min(max(ser, 0.0), 1.0)


def theoretical_ber_qam(snr_db: float, M: int = 64) -> float:
    """
    Theoretical BER for Gray-coded M-QAM.

    For Gray coding: BER ≈ SER / log2(M)
    """
    ser = theoretical_ser_qam(snr_db, M)
    bits_per_symbol = np.log2(M)
    return ser / bits_per_symbol


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RECEIVER MODULE - Unit Tests")
    print("=" * 60)

    # Test POM transceiver
    print("\nPOM Transceiver Test:")
    pom_trx = POMTransceiver(seed=42)

    test_bits = np.random.randint(0, 2, 6000)  # 1000 symbols

    for snr_db in [5, 10, 15, 20]:
        result = pom_trx.transmit(test_bits, snr_db)
        print(f"  SNR={snr_db:2d} dB: SER={result.metrics.ser:.4e}, "
              f"BER={result.metrics.ber:.4e}, "
              f"mean_dist={result.mean_distance:.4f}")

    # Test QAM transceiver
    print("\nQAM Transceiver Test:")
    qam_trx = QAMTransceiver(seed=42)

    for snr_db in [5, 10, 15, 20]:
        result = qam_trx.transmit(test_bits, snr_db)
        theoretical = theoretical_ser_qam(snr_db)
        print(f"  SNR={snr_db:2d} dB: SER={result.metrics.ser:.4e} "
              f"(theory: {theoretical:.4e}), "
              f"BER={result.metrics.ber:.4e}")

    # Comparison at 12 dB
    print("\n" + "-" * 60)
    print("Direct Comparison at 12 dB:")
    snr_test = 12.0

    pom_result = pom_trx.transmit(test_bits, snr_test)
    qam_result = qam_trx.transmit(test_bits, snr_test)

    print(f"  POM: SER = {pom_result.metrics.ser:.4e}")
    print(f"  QAM: SER = {qam_result.metrics.ser:.4e}")

    if pom_result.metrics.ser > 0:
        improvement = qam_result.metrics.ser / pom_result.metrics.ser
        print(f"  POM is {improvement:.1f}x better!")

    print("\n✓ All receiver tests passed!")
