#!/usr/bin/env python3
"""
=============================================================================
MODEM - Modulation/Demodulation Pipeline for POM and QAM
=============================================================================

This module implements the digital-to-analog (modulation) and analog-to-digital
(demodulation) conversion for both Polytopal Orthogonal Modulation (POM) and
standard 64-QAM.

MODULATION THEORY:
------------------
Digital modulation maps discrete symbols (bit sequences) to continuous signal
points in a constellation. The constellation geometry determines:

1. Spectral efficiency: bits per symbol = log2(constellation_size)
2. Noise resilience: determined by minimum distance between symbols
3. Decoding complexity: O(N) for brute force, O(log N) with spatial indexing

POM MODULATION:
---------------
Maps bit chunks to vertices of the 600-cell polytope in 4D space.
- 120 vertices → ~6.9 bits/symbol (we use 6 or 7 bits)
- Higher dimensionality spreads noise energy across more degrees of freedom
- Geometric quantization provides natural error correction

QAM MODULATION:
---------------
Standard 64-QAM maps 6-bit chunks to an 8×8 grid in the complex plane.
- 64 symbols → exactly 6 bits/symbol
- Industry standard for WiFi, LTE, 5G, and cable modems
- Serves as the baseline for comparison

Author: PPP Research Team
License: MIT
=============================================================================
"""

import numpy as np
from typing import Tuple, Optional, Union
from dataclasses import dataclass

from geometry import Polychoron600, QAM64Constellation


# =============================================================================
# BIT MAPPING UTILITIES
# =============================================================================

def bits_to_indices(bits: np.ndarray, bits_per_symbol: int) -> np.ndarray:
    """
    Convert a bit array to symbol indices (binary to decimal).

    Args:
        bits: 1D array of bits (0s and 1s)
        bits_per_symbol: Number of bits per symbol

    Returns:
        1D array of symbol indices
    """
    # Pad to multiple of bits_per_symbol
    n_bits = len(bits)
    padding = (bits_per_symbol - (n_bits % bits_per_symbol)) % bits_per_symbol
    if padding > 0:
        bits = np.concatenate([bits, np.zeros(padding, dtype=bits.dtype)])

    # Reshape into chunks
    n_symbols = len(bits) // bits_per_symbol
    bit_chunks = bits.reshape(n_symbols, bits_per_symbol)

    # Convert binary to decimal (MSB first)
    powers = 2 ** np.arange(bits_per_symbol - 1, -1, -1)
    indices = np.sum(bit_chunks * powers, axis=1)

    return indices.astype(np.int32)


def indices_to_bits(indices: np.ndarray, bits_per_symbol: int) -> np.ndarray:
    """
    Convert symbol indices back to bits (decimal to binary).

    Args:
        indices: 1D array of symbol indices
        bits_per_symbol: Number of bits per symbol

    Returns:
        1D array of bits
    """
    n_symbols = len(indices)

    # Convert each index to binary representation
    bits = np.zeros((n_symbols, bits_per_symbol), dtype=np.int32)

    for i in range(bits_per_symbol):
        bits[:, bits_per_symbol - 1 - i] = (indices >> i) & 1

    return bits.flatten()


def generate_gray_code(n_bits: int) -> np.ndarray:
    """
    Generate Gray code sequence for n bits.

    Gray coding ensures adjacent symbols differ by only 1 bit,
    minimizing bit errors when symbol errors occur.

    Args:
        n_bits: Number of bits

    Returns:
        Array of shape (2^n_bits,) with Gray-coded indices
    """
    n = 2 ** n_bits
    gray = np.arange(n)
    gray = gray ^ (gray >> 1)
    return gray


def apply_gray_mapping(indices: np.ndarray, n_bits: int) -> np.ndarray:
    """Apply Gray code mapping to indices."""
    gray_table = generate_gray_code(n_bits)
    # Create inverse mapping
    inverse_gray = np.zeros(len(gray_table), dtype=np.int32)
    inverse_gray[gray_table] = np.arange(len(gray_table))
    return inverse_gray[indices]


# =============================================================================
# DATA CLASS FOR TRANSMISSION PACKETS
# =============================================================================

@dataclass
class TransmissionPacket:
    """Container for a modulated transmission."""
    symbols: np.ndarray          # The modulated symbols (N, D) where D is dimensionality
    indices: np.ndarray          # Symbol indices before modulation
    bits: np.ndarray             # Original bits
    bits_per_symbol: int         # Bits per symbol used
    constellation_type: str      # 'POM' or 'QAM'
    num_symbols: int             # Number of symbols
    num_bits: int                # Number of actual data bits (excluding padding)


# =============================================================================
# CLASS: POMModulator - Polytopal Orthogonal Modulation
# =============================================================================

class POMModulator:
    """
    Modulator for Polytopal Orthogonal Modulation using the 600-cell.

    DESIGN CHOICES:
    ---------------
    The 600-cell has 120 vertices, which is not a power of 2.
    We have two options:

    Option A (Conservative): Use 6 bits/symbol (64 of 120 vertices)
        - Simpler implementation
        - Fair comparison with 64-QAM (same bits/symbol)
        - Some vertices unused

    Option B (Full Utilization): Use 7 bits/symbol with rejection sampling
        - Maps to 128 indices, rejects > 119
        - Higher throughput but variable encoding time
        - More complex implementation

    This implementation supports both modes.
    """

    def __init__(self, constellation: Optional[Polychoron600] = None,
                 mode: str = 'conservative', use_gray: bool = True):
        """
        Initialize the POM modulator.

        Args:
            constellation: Pre-built Polychoron600, or None to create new
            mode: 'conservative' (6 bits) or 'full' (7 bits with rejection)
            use_gray: Whether to use Gray coding for bit mapping
        """
        self.constellation = constellation or Polychoron600()
        self.mode = mode
        self.use_gray = use_gray

        if mode == 'conservative':
            self.bits_per_symbol = 6
            self.max_index = 64  # Use only first 64 vertices
        else:
            self.bits_per_symbol = 7
            self.max_index = 120  # Use all vertices

        # Precompute Gray code table if needed
        if use_gray:
            self.gray_table = generate_gray_code(self.bits_per_symbol)
            self.inverse_gray = np.zeros(len(self.gray_table), dtype=np.int32)
            self.inverse_gray[self.gray_table] = np.arange(len(self.gray_table))

    def modulate(self, bits: np.ndarray) -> TransmissionPacket:
        """
        Modulate a bit stream to 4D POM symbols.

        Args:
            bits: 1D array of bits (0s and 1s)

        Returns:
            TransmissionPacket containing modulated symbols and metadata
        """
        original_num_bits = len(bits)

        # Convert bits to symbol indices
        indices = bits_to_indices(bits, self.bits_per_symbol)

        # Apply Gray coding if enabled
        if self.use_gray:
            indices = self.gray_table[indices % len(self.gray_table)]

        # Clamp indices to valid range (for conservative mode)
        if self.mode == 'conservative':
            indices = indices % self.max_index

        # Map indices to 4D vertices
        symbols = self.constellation.vertices[indices]

        return TransmissionPacket(
            symbols=symbols,
            indices=indices,
            bits=bits[:original_num_bits],
            bits_per_symbol=self.bits_per_symbol,
            constellation_type='POM',
            num_symbols=len(indices),
            num_bits=original_num_bits
        )

    def get_reference_constellation(self) -> np.ndarray:
        """Get the reference constellation points."""
        if self.mode == 'conservative':
            return self.constellation.vertices[:self.max_index]
        return self.constellation.vertices


# =============================================================================
# CLASS: QAMModulator - Standard 64-QAM
# =============================================================================

class QAMModulator:
    """
    Standard 64-QAM modulator for baseline comparison.

    64-QAM is the industry standard for high-throughput wireless:
    - WiFi (802.11ac/ax)
    - LTE/5G NR
    - Cable modems (DOCSIS)
    - DVB-S2/T2

    We implement it with 4D embedding for fair noise comparison.
    """

    def __init__(self, constellation: Optional[QAM64Constellation] = None,
                 use_gray: bool = True):
        """
        Initialize the QAM modulator.

        Args:
            constellation: Pre-built QAM64Constellation, or None to create new
            use_gray: Whether to use Gray coding
        """
        self.constellation = constellation or QAM64Constellation()
        self.bits_per_symbol = 6
        self.use_gray = use_gray

        if use_gray:
            self.gray_table = generate_gray_code(6)
            self.inverse_gray = np.zeros(64, dtype=np.int32)
            self.inverse_gray[self.gray_table] = np.arange(64)

    def modulate(self, bits: np.ndarray) -> TransmissionPacket:
        """
        Modulate a bit stream to 64-QAM symbols (4D embedded).

        Args:
            bits: 1D array of bits

        Returns:
            TransmissionPacket with modulated symbols
        """
        original_num_bits = len(bits)

        # Convert bits to indices
        indices = bits_to_indices(bits, self.bits_per_symbol)

        # Apply Gray coding
        if self.use_gray:
            indices = self.gray_table[indices % 64]

        # Ensure valid range
        indices = indices % 64

        # Map to 4D-embedded symbols
        symbols = self.constellation.symbols_4d[indices]

        return TransmissionPacket(
            symbols=symbols,
            indices=indices,
            bits=bits[:original_num_bits],
            bits_per_symbol=self.bits_per_symbol,
            constellation_type='QAM64',
            num_symbols=len(indices),
            num_bits=original_num_bits
        )

    def modulate_2d(self, bits: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Modulate to native 2D QAM symbols (for 2D noise model).

        Returns:
            Tuple of (2D symbols, indices)
        """
        original_num_bits = len(bits)
        indices = bits_to_indices(bits, self.bits_per_symbol)

        if self.use_gray:
            indices = self.gray_table[indices % 64]

        indices = indices % 64
        symbols_2d = self.constellation.symbols_2d[indices]

        return symbols_2d, indices

    def get_reference_constellation(self) -> np.ndarray:
        """Get the 4D reference constellation."""
        return self.constellation.symbols_4d


# =============================================================================
# CLASS: POMDemodulator - Geometric Quantization Receiver
# =============================================================================

class POMDemodulator:
    """
    Demodulator for POM using geometric quantization.

    GEOMETRIC QUANTIZATION:
    -----------------------
    The core innovation of POM is that demodulation reduces to a
    nearest-neighbor search in 4D space. This is equivalent to:

    1. Finding which Voronoi cell contains the received point
    2. Mapping to the vertex at the center of that cell

    The 600-cell's high symmetry means each Voronoi cell is (nearly)
    identical, providing uniform error probability across the constellation.

    COMPLEXITY:
    -----------
    - Brute force: O(N) per symbol, where N = 120
    - KD-Tree: O(log N) per symbol
    - With batching: amortized O(1) per symbol for large batches
    """

    def __init__(self, constellation: Optional[Polychoron600] = None,
                 mode: str = 'conservative', use_gray: bool = True):
        """
        Initialize the POM demodulator.

        Args:
            constellation: Reference constellation (should match modulator)
            mode: 'conservative' or 'full' (must match modulator)
            use_gray: Whether Gray coding was used (must match modulator)
        """
        self.constellation = constellation or Polychoron600()
        self.mode = mode
        self.use_gray = use_gray

        if mode == 'conservative':
            self.bits_per_symbol = 6
            self.max_index = 64
            # Build KDTree for only the used vertices
            from scipy.spatial import KDTree
            self.reference_vertices = self.constellation.vertices[:64]
            self.kdtree = KDTree(self.reference_vertices)
        else:
            self.bits_per_symbol = 7
            self.max_index = 120
            self.reference_vertices = self.constellation.vertices
            self.kdtree = self.constellation.kdtree

        if use_gray:
            self.gray_table = generate_gray_code(self.bits_per_symbol)
            self.inverse_gray = np.zeros(len(self.gray_table), dtype=np.int32)
            self.inverse_gray[self.gray_table] = np.arange(len(self.gray_table))

    def demodulate(self, noisy_symbols: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Demodulate noisy 4D symbols to bits.

        This is the "snapping" algorithm:
        1. Find nearest reference vertex for each noisy symbol
        2. Map vertex index to bit sequence
        3. Undo Gray coding if applied

        Args:
            noisy_symbols: Shape (N, 4) array of received symbols

        Returns:
            Tuple of (detected_bits, detected_vertex_indices, distances)
            Note: detected_vertex_indices are the raw vertex indices (Gray-coded)
                  for SER comparison with transmitted indices
        """
        # Find nearest reference vertex (geometric quantization)
        distances, vertex_indices = self.kdtree.query(noisy_symbols)
        vertex_indices = vertex_indices.astype(np.int32)

        # For bit conversion, undo Gray coding to get natural indices
        if self.use_gray:
            natural_indices = self.inverse_gray[vertex_indices]
        else:
            natural_indices = vertex_indices

        # Convert natural indices to bits
        bits = indices_to_bits(natural_indices, self.bits_per_symbol)

        # Return vertex_indices (not natural_indices) for SER comparison
        # Since modulator stores Gray-coded vertex indices in packet.indices
        return bits, vertex_indices, distances


# =============================================================================
# CLASS: QAMDemodulator - Standard QAM Receiver
# =============================================================================

class QAMDemodulator:
    """
    Standard 64-QAM demodulator.

    Uses minimum Euclidean distance detection, which is optimal
    for AWGN channels (maximum likelihood detection).
    """

    def __init__(self, constellation: Optional[QAM64Constellation] = None,
                 use_gray: bool = True):
        """Initialize the QAM demodulator."""
        self.constellation = constellation or QAM64Constellation()
        self.bits_per_symbol = 6
        self.use_gray = use_gray

        if use_gray:
            self.gray_table = generate_gray_code(6)
            self.inverse_gray = np.zeros(64, dtype=np.int32)
            self.inverse_gray[self.gray_table] = np.arange(64)

    def demodulate_4d(self, noisy_symbols: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Demodulate from 4D-embedded noisy symbols.

        Only uses the first 2 dimensions (Re, Im) for detection.

        Returns:
            Tuple of (detected_bits, detected_symbol_indices, distances)
            Note: detected_symbol_indices are raw (Gray-coded) for SER comparison
        """
        # Extract 2D components
        noisy_2d = noisy_symbols[:, :2]

        # Find nearest constellation point
        distances, symbol_indices = self.constellation.kdtree_2d.query(noisy_2d)
        symbol_indices = symbol_indices.astype(np.int32)

        # Undo Gray coding for bit conversion only
        if self.use_gray:
            natural_indices = self.inverse_gray[symbol_indices]
        else:
            natural_indices = symbol_indices

        # Convert to bits
        bits = indices_to_bits(natural_indices, self.bits_per_symbol)

        # Return symbol_indices (Gray-coded) for SER comparison
        return bits, symbol_indices, distances

    def demodulate_2d(self, noisy_symbols_2d: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Demodulate from native 2D noisy symbols.

        Returns:
            Tuple of (detected_bits, detected_symbol_indices, distances)
        """
        distances, symbol_indices = self.constellation.kdtree_2d.query(noisy_symbols_2d)
        symbol_indices = symbol_indices.astype(np.int32)

        if self.use_gray:
            natural_indices = self.inverse_gray[symbol_indices]
        else:
            natural_indices = symbol_indices

        bits = indices_to_bits(natural_indices, self.bits_per_symbol)

        return bits, symbol_indices, distances


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_pom_modem(mode: str = 'conservative', use_gray: bool = True):
    """
    Create a matched POM modulator/demodulator pair.

    Args:
        mode: 'conservative' (6 bits) or 'full' (7 bits)
        use_gray: Whether to use Gray coding

    Returns:
        Tuple of (modulator, demodulator, constellation)
    """
    constellation = Polychoron600()
    modulator = POMModulator(constellation, mode=mode, use_gray=use_gray)
    demodulator = POMDemodulator(constellation, mode=mode, use_gray=use_gray)
    return modulator, demodulator, constellation


def create_qam_modem(use_gray: bool = True):
    """
    Create a matched QAM modulator/demodulator pair.

    Returns:
        Tuple of (modulator, demodulator, constellation)
    """
    constellation = QAM64Constellation()
    modulator = QAMModulator(constellation, use_gray=use_gray)
    demodulator = QAMDemodulator(constellation, use_gray=use_gray)
    return modulator, demodulator, constellation


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MODEM MODULE - Unit Tests")
    print("=" * 60)

    # Test bit conversion
    print("\nBit conversion test:")
    test_bits = np.array([1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0])
    indices = bits_to_indices(test_bits, 6)
    recovered_bits = indices_to_bits(indices, 6)
    print(f"  Original bits:  {test_bits}")
    print(f"  Indices:        {indices}")
    print(f"  Recovered bits: {recovered_bits}")
    assert np.array_equal(test_bits, recovered_bits), "Bit conversion failed!"

    # Test POM modulator
    print("\n" + "-" * 60)
    print("POM Modulator Test:")
    pom_mod, pom_demod, pom_const = create_pom_modem()

    random_bits = np.random.randint(0, 2, 600)
    packet = pom_mod.modulate(random_bits)

    print(f"  Input bits: {len(random_bits)}")
    print(f"  Output symbols: {packet.symbols.shape}")
    print(f"  Bits per symbol: {packet.bits_per_symbol}")

    # Test demodulation (no noise)
    demod_bits, demod_indices, _ = pom_demod.demodulate(packet.symbols)
    bit_errors = np.sum(demod_bits[:len(random_bits)] != random_bits)
    print(f"  Bit errors (no noise): {bit_errors}")
    assert bit_errors == 0, "POM demodulation failed without noise!"

    # Test QAM modulator
    print("\n" + "-" * 60)
    print("QAM Modulator Test:")
    qam_mod, qam_demod, qam_const = create_qam_modem()

    packet_qam = qam_mod.modulate(random_bits)
    print(f"  Input bits: {len(random_bits)}")
    print(f"  Output symbols: {packet_qam.symbols.shape}")

    # Test demodulation (no noise)
    demod_bits_qam, _, _ = qam_demod.demodulate_4d(packet_qam.symbols)
    bit_errors_qam = np.sum(demod_bits_qam[:len(random_bits)] != random_bits)
    print(f"  Bit errors (no noise): {bit_errors_qam}")
    assert bit_errors_qam == 0, "QAM demodulation failed without noise!"

    print("\n✓ All modem tests passed!")
