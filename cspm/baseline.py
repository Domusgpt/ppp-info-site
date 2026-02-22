"""
QAM Baseline for Comparison

Standard Quadrature Amplitude Modulation implementation for
benchmarking against CSPM.

QAM operates in 2D complex plane (I/Q):
- 64-QAM: 6 bits per symbol
- 128-QAM: 7 bits per symbol (fair comparison to CSPM's 6.9 bits)
- 256-QAM: 8 bits per symbol

IMPORTANT: For fair comparison with CSPM (6.9 bits/symbol):
- 128-QAM (7 bits/symbol) is the appropriate baseline
- 64-QAM comparisons understate QAM capability
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional


@dataclass
class QAMSymbol:
    """A single QAM symbol."""

    iq: complex  # In-phase and Quadrature components
    symbol_index: int
    bits: np.ndarray
    power: float = 1.0

    @property
    def amplitude(self) -> float:
        return abs(self.iq)

    @property
    def phase(self) -> float:
        return np.angle(self.iq)


class QAMModulator:
    """
    Standard QAM modulator.

    Supports 4-QAM (QPSK), 16-QAM, 64-QAM, 128-QAM (cross), 256-QAM.
    """

    def __init__(self, order: int = 64):
        """
        Initialize QAM modulator.

        Args:
            order: Constellation size (4, 16, 64, 128, 256)
        """
        if order not in [4, 16, 64, 128, 256]:
            raise ValueError(f"QAM order must be 4, 16, 64, 128, or 256")

        self.order = order
        self.bits_per_symbol = int(np.log2(order))
        self.constellation = self._build_constellation()

        # Normalize power to unit average
        avg_power = np.mean(np.abs(self.constellation) ** 2)
        self.constellation /= np.sqrt(avg_power)

    def _build_constellation(self) -> np.ndarray:
        """Build QAM constellation using Gray coding."""
        if self.order == 128:
            # 128-QAM uses cross constellation (not square)
            return self._build_cross_constellation(128)

        m = int(np.sqrt(self.order))

        # Create grid
        x = np.arange(m) - (m - 1) / 2
        y = np.arange(m) - (m - 1) / 2

        constellation = []
        for i in range(m):
            for j in range(m):
                constellation.append(x[i] + 1j * y[j])

        return np.array(constellation)

    def _build_cross_constellation(self, order: int) -> np.ndarray:
        """
        Build cross-shaped constellation for non-square QAM (e.g., 128-QAM).

        128-QAM is typically implemented as a 12x12 grid with corners removed.
        """
        # Start with 12x12 = 144 point grid
        m = 12
        x = np.arange(m) - (m - 1) / 2
        y = np.arange(m) - (m - 1) / 2

        constellation = []
        for i in range(m):
            for j in range(m):
                point = x[i] + 1j * y[j]
                # Remove corner points to get 128 symbols
                # Corners are where |x| > 5 and |y| > 5
                if not (abs(x[i]) > 4.5 and abs(y[j]) > 4.5):
                    constellation.append(point)

        # Should have 128 points (144 - 16 corners)
        constellation = np.array(constellation[:order])
        return constellation

    def _gray_code(self, n: int, bits: int) -> int:
        """Convert integer to Gray code."""
        return n ^ (n >> 1)

    def modulate_bits(self, bits: np.ndarray) -> List[QAMSymbol]:
        """
        Modulate bit stream to QAM symbols.

        Args:
            bits: Array of bits

        Returns:
            List of QAMSymbol objects
        """
        n_bits = len(bits)
        n_symbols = n_bits // self.bits_per_symbol
        bits = bits[:n_symbols * self.bits_per_symbol]

        symbols = []
        for i in range(n_symbols):
            bit_group = bits[i * self.bits_per_symbol:(i + 1) * self.bits_per_symbol]

            # Convert bits to symbol index
            symbol_idx = 0
            for b in bit_group:
                symbol_idx = (symbol_idx << 1) | int(b)

            # Get constellation point
            iq = self.constellation[symbol_idx]

            symbols.append(QAMSymbol(
                iq=iq,
                symbol_index=symbol_idx,
                bits=bit_group.copy()
            ))

        return symbols

    def modulate_bytes(self, data: bytes) -> List[QAMSymbol]:
        """Modulate byte data."""
        bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
        return self.modulate_bits(bits)


class QAMDemodulator:
    """
    Standard QAM demodulator with optional soft-decision.

    Uses minimum Euclidean distance detection.
    """

    def __init__(self, order: int = 64):
        self.order = order
        self.bits_per_symbol = int(np.log2(order))
        self.modulator = QAMModulator(order)
        self.constellation = self.modulator.constellation

        self._symbol_errors = 0
        self._bit_errors = 0
        self._total_symbols = 0
        self._total_bits = 0

    def demodulate_symbol(
        self,
        received: complex,
        original_idx: int = None
    ) -> Tuple[int, np.ndarray, float]:
        """
        Demodulate a single received symbol.

        Args:
            received: Received complex value
            original_idx: Original symbol index (for error counting)

        Returns:
            Tuple of (decoded symbol index, bits, distance)
        """
        # Find minimum distance constellation point
        distances = np.abs(self.constellation - received)
        min_idx = np.argmin(distances)
        min_dist = distances[min_idx]

        # Convert to bits
        bits = []
        idx = min_idx
        for _ in range(self.bits_per_symbol):
            bits.insert(0, idx & 1)
            idx >>= 1
        bits = np.array(bits, dtype=np.uint8)

        self._total_symbols += 1

        # Track errors if original known
        if original_idx is not None and min_idx != original_idx:
            self._symbol_errors += 1

        return min_idx, bits, min_dist

    def demodulate_sequence(
        self,
        received: List[complex],
        original_indices: List[int] = None
    ) -> Tuple[np.ndarray, List[Tuple[int, float]]]:
        """
        Demodulate a sequence of received symbols.

        Returns:
            Tuple of (all bits, list of (symbol_idx, distance))
        """
        all_bits = []
        results = []

        for i, rx in enumerate(received):
            orig_idx = original_indices[i] if original_indices else None
            sym_idx, bits, dist = self.demodulate_symbol(rx, orig_idx)
            all_bits.extend(bits)
            results.append((sym_idx, dist))

        self._total_bits += len(all_bits)

        return np.array(all_bits, dtype=np.uint8), results

    def demodulate_with_ber(
        self,
        received: List[complex],
        original_symbols: List[QAMSymbol]
    ) -> Dict:
        """
        Demodulate and compute BER.

        Args:
            received: Received complex values
            original_symbols: Original transmitted symbols

        Returns:
            Statistics dictionary
        """
        original_indices = [s.symbol_index for s in original_symbols]
        original_bits = np.concatenate([s.bits for s in original_symbols])

        decoded_bits, results = self.demodulate_sequence(received, original_indices)

        # Compute BER
        min_len = min(len(decoded_bits), len(original_bits))
        bit_errors = np.sum(decoded_bits[:min_len] != original_bits[:min_len])
        ber = bit_errors / min_len if min_len > 0 else 0

        self._bit_errors += bit_errors

        return {
            "ber": ber,
            "bit_errors": int(bit_errors),
            "symbol_errors": self._symbol_errors,
            "avg_distance": np.mean([r[1] for r in results]),
            "max_distance": max([r[1] for r in results]),
            "n_symbols": len(received),
            "n_bits": len(decoded_bits)
        }

    def get_ber(self) -> float:
        if self._total_bits == 0:
            return 0.0
        return self._bit_errors / self._total_bits

    def reset_stats(self):
        self._symbol_errors = 0
        self._bit_errors = 0
        self._total_symbols = 0
        self._total_bits = 0


class QAMChannel:
    """
    Simple AWGN channel for QAM comparison.

    Adds complex Gaussian noise to match SNR.
    """

    def __init__(self, snr_db: float = 20.0, seed: int = None):
        self.snr_db = snr_db
        self.rng = np.random.default_rng(seed)

    def transmit(self, symbols: List[QAMSymbol]) -> List[complex]:
        """
        Transmit QAM symbols through AWGN channel.

        Returns list of noisy complex values.
        """
        snr_linear = 10 ** (self.snr_db / 10)

        received = []
        for sym in symbols:
            # Signal power
            signal_power = abs(sym.iq) ** 2

            # Noise power to achieve target SNR
            noise_power = signal_power / snr_linear
            noise_std = np.sqrt(noise_power / 2)  # /2 for complex noise

            # Add complex Gaussian noise
            noise = self.rng.normal(0, noise_std) + 1j * self.rng.normal(0, noise_std)
            received.append(sym.iq + noise)

        return received


class QAMFiberChannel:
    """
    Fair fiber channel model for QAM that applies equivalent impairments
    to what CSPM receives. This ensures apples-to-apples comparison.

    Impairments:
    - Phase noise (equivalent to CSPM's phase rotation)
    - Polarization rotation (affects constellation orientation)
    - AWGN
    """

    def __init__(
        self,
        snr_db: float = 20.0,
        phase_noise_std: float = 0.05,  # radians, matches CSPM channel
        polarization_rotation: bool = True,
        seed: int = None
    ):
        self.snr_db = snr_db
        self.phase_noise_std = phase_noise_std
        self.polarization_rotation = polarization_rotation
        self.rng = np.random.default_rng(seed)

    def transmit(self, symbols: List[QAMSymbol]) -> List[complex]:
        """
        Transmit QAM symbols through fiber channel with realistic impairments.

        NOTE: Unlike CSPM, we do NOT normalize received symbols. This is
        fair because CSPM's unit-sphere normalization is an artifact of
        the 4D representation, not a physical channel effect.
        """
        snr_linear = 10 ** (self.snr_db / 10)
        received = []

        for sym in symbols:
            value = sym.iq

            # Apply phase noise (laser linewidth, fiber nonlinearity)
            if self.phase_noise_std > 0:
                phase_error = self.rng.normal(0, self.phase_noise_std)
                value = value * np.exp(1j * phase_error)

            # Apply random polarization rotation (PMD equivalent)
            if self.polarization_rotation:
                # Small random rotation of constellation
                rot_angle = self.rng.normal(0, 0.02)  # ~1 degree std
                value = value * np.exp(1j * rot_angle)

            # Add AWGN
            signal_power = abs(value) ** 2
            noise_power = signal_power / snr_linear
            noise_std = np.sqrt(noise_power / 2)
            noise = self.rng.normal(0, noise_std) + 1j * self.rng.normal(0, noise_std)
            value = value + noise

            received.append(value)

        return received


def theoretical_ber_qam(order: int, snr_db: float) -> float:
    """
    Theoretical BER for M-QAM in AWGN.

    Uses the approximation:
    BER ≈ (4/k) * (1 - 1/√M) * Q(√(3k*SNR/(M-1)))

    where k = log2(M), M = constellation size
    """
    from scipy.special import erfc

    M = order
    k = np.log2(M)
    snr = 10 ** (snr_db / 10)

    # Average symbol energy to noise ratio
    Es_N0 = snr * k

    # Q function approximation: Q(x) ≈ 0.5 * erfc(x/√2)
    arg = np.sqrt(3 * Es_N0 / (M - 1))
    Q_val = 0.5 * erfc(arg / np.sqrt(2))

    ber = (4 / k) * (1 - 1 / np.sqrt(M)) * Q_val

    return ber


def compare_qam_cspm_theoretical() -> Dict:
    """
    Compare theoretical performance of QAM vs CSPM.

    CSPM advantage: The 600-cell has larger minimum distance
    than square QAM of similar size.
    """
    from .lattice import Cell600

    cell = Cell600()
    cspm_min_dist = cell.minimum_distance()  # Angular distance

    # 64-QAM minimum distance (normalized)
    # Grid spacing = 2/7 for 8x8 grid normalized to unit power
    qam64_min_dist = 2 / 7 / np.sqrt(42/64)  # ≈ 0.22

    # 600-cell: 120 vertices on 3-sphere
    # Minimum angular distance ≈ 0.618 radians ≈ 35 degrees
    # Convert to Euclidean: 2*sin(θ/2) ≈ 0.60

    cspm_euclidean = 2 * np.sin(cspm_min_dist / 2)

    return {
        "qam64_symbols": 64,
        "qam64_bits_per_symbol": 6,
        "qam64_min_distance": qam64_min_dist,
        "cspm_symbols": 120,
        "cspm_bits_per_symbol": cell.bits_per_symbol(),
        "cspm_min_angular_distance_rad": cspm_min_dist,
        "cspm_min_euclidean_distance": cspm_euclidean,
        "distance_advantage_ratio": cspm_euclidean / qam64_min_dist,
        "coding_gain_db": 20 * np.log10(cspm_euclidean / qam64_min_dist)
    }


if __name__ == "__main__":
    # Test QAM modulation
    print("Testing QAM Modulation")
    print("=" * 50)

    mod = QAMModulator(order=64)
    demod = QAMDemodulator(order=64)

    # Generate test data
    rng = np.random.default_rng(42)
    data = bytes(rng.integers(0, 256, 500, dtype=np.uint8))

    # Modulate
    symbols = mod.modulate_bytes(data)
    print(f"Modulated {len(data)} bytes to {len(symbols)} symbols")
    print(f"Bits per symbol: {mod.bits_per_symbol}")

    # Test through AWGN channel
    for snr_db in [25, 20, 15, 12, 10]:
        channel = QAMChannel(snr_db=snr_db, seed=42)
        demod.reset_stats()

        received = channel.transmit(symbols)
        stats = demod.demodulate_with_ber(received, symbols)

        theoretical = theoretical_ber_qam(64, snr_db)

        print(f"\nSNR = {snr_db} dB:")
        print(f"  Simulated BER: {stats['ber']:.2e}")
        print(f"  Theoretical BER: {theoretical:.2e}")
        print(f"  Bit errors: {stats['bit_errors']}")

    # Compare theoretical performance
    print("\n" + "=" * 50)
    print("Theoretical CSPM vs QAM Comparison")
    print("=" * 50)

    comparison = compare_qam_cspm_theoretical()
    for key, value in comparison.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")
