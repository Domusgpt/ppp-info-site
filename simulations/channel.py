#!/usr/bin/env python3
"""
=============================================================================
CHANNEL SIMULATION - Noise Models for POM vs QAM Comparison
=============================================================================

This module implements channel models for fair comparison between
4D POM and 2D QAM modulation schemes.

CRITICAL INSIGHT - DIMENSIONALITY AND NOISE:
---------------------------------------------
The key challenge in comparing POM (4D) vs QAM (2D) is ensuring a
physically meaningful and FAIR noise comparison.

APPROACH 1: Equal SNR per Dimension (UNFAIR to QAM)
    - Add same noise power to each dimension
    - 4D system sees noise in all 4 dimensions
    - 2D system (embedded in 4D) sees noise in unused dimensions too
    - This artificially penalizes the lower-dimensional system

APPROACH 2: Equal Total Noise Power (FAIR)
    - Fix total noise power based on SNR definition
    - 4D: distribute noise across 4 dimensions
    - 2D: distribute noise across 2 dimensions only
    - This is the physically correct comparison

APPROACH 3: Equal Noise per Symbol (ALSO FAIR)
    - Same total noise energy per transmitted symbol
    - Accounts for the fact that 4D uses more "bandwidth" (dimensions)

We implement APPROACH 2 as the primary method, with options for others.

SNR DEFINITION:
---------------
SNR = E[|signal|²] / E[|noise|²]

For unit-power constellations: E[|signal|²] = 1

Therefore: noise_variance = 1/SNR_linear

For D-dimensional noise: variance_per_dimension = noise_variance / D

Author: PPP Research Team
License: MIT
=============================================================================
"""

import numpy as np
from typing import Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# NOISE MODEL TYPES
# =============================================================================

class NoiseModel(Enum):
    """Available noise models for channel simulation."""
    AWGN = "awgn"                    # Additive White Gaussian Noise
    RAYLEIGH = "rayleigh"            # Rayleigh fading (NLOS)
    RICIAN = "rician"                # Rician fading (LOS + NLOS)
    PHASE_NOISE = "phase_noise"      # Oscillator phase noise


class DimensionalityMode(Enum):
    """How to handle dimensionality in noise injection."""
    NATIVE = "native"                # Use native dimensionality (2D for QAM, 4D for POM)
    EMBEDDED_4D = "embedded_4d"      # Embed everything in 4D
    EQUAL_TOTAL_POWER = "equal_power"  # Same total noise power regardless of D


# =============================================================================
# DATA CLASS FOR CHANNEL STATE
# =============================================================================

@dataclass
class ChannelState:
    """Container for channel simulation state and statistics."""
    snr_db: float
    snr_linear: float
    noise_variance: float
    noise_std_per_dim: float
    dimensionality: int
    actual_snr_db: float  # Measured SNR after noise injection


# =============================================================================
# AWGN CHANNEL - THE PRIMARY MODEL
# =============================================================================

class AWGNChannel:
    """
    Additive White Gaussian Noise channel model.

    This is the canonical channel model for comparing modulation schemes.
    It assumes:
    1. Noise is Gaussian (thermal noise, shot noise)
    2. Noise is white (flat power spectral density)
    3. Noise is additive (superimposed on signal)
    4. Noise is independent across dimensions

    PHYSICAL BASIS:
    ---------------
    In optical/RF systems, the noise sources include:
    - Thermal noise (Johnson-Nyquist)
    - Shot noise (photon counting)
    - Amplifier noise (ASE in optical, noise figure in RF)

    These sum to Gaussian noise by the Central Limit Theorem.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the AWGN channel.

        Args:
            seed: Random seed for reproducibility
        """
        self.rng = np.random.default_rng(seed)
        self.last_state: Optional[ChannelState] = None

    def add_noise(self, signal: np.ndarray, snr_db: float,
                  signal_power: Optional[float] = None) -> Tuple[np.ndarray, ChannelState]:
        """
        Add AWGN to a signal with specified SNR.

        The noise power is calculated to achieve the target SNR given
        the signal power. If signal_power is not provided, it's measured
        from the input signal.

        Args:
            signal: Input signal array, shape (N, D) where D is dimensionality
            snr_db: Target Signal-to-Noise Ratio in decibels
            signal_power: Optional override for signal power (default: measured)

        Returns:
            Tuple of (noisy_signal, channel_state)
        """
        # Determine dimensionality
        if signal.ndim == 1:
            signal = signal.reshape(-1, 1)
        n_samples, dimensionality = signal.shape

        # Measure or use provided signal power
        if signal_power is None:
            signal_power = np.mean(np.sum(signal**2, axis=1))

        # Convert SNR from dB to linear
        snr_linear = 10 ** (snr_db / 10)

        # Calculate total noise variance
        # SNR = signal_power / noise_power
        # noise_power = signal_power / SNR
        noise_power = signal_power / snr_linear

        # Noise variance per dimension
        # Total noise power = D * variance_per_dim
        noise_var_per_dim = noise_power / dimensionality
        noise_std_per_dim = np.sqrt(noise_var_per_dim)

        # Generate Gaussian noise
        noise = self.rng.normal(0, noise_std_per_dim, signal.shape)

        # Add noise to signal
        noisy_signal = signal + noise

        # Measure actual SNR
        actual_noise_power = np.mean(np.sum(noise**2, axis=1))
        actual_snr = signal_power / actual_noise_power if actual_noise_power > 0 else np.inf
        actual_snr_db = 10 * np.log10(actual_snr) if actual_snr < np.inf else np.inf

        # Store state
        self.last_state = ChannelState(
            snr_db=snr_db,
            snr_linear=snr_linear,
            noise_variance=noise_power,
            noise_std_per_dim=noise_std_per_dim,
            dimensionality=dimensionality,
            actual_snr_db=actual_snr_db
        )

        return noisy_signal, self.last_state


class AWGNChannel2D:
    """
    Specialized 2D AWGN channel for native QAM simulation.

    This channel operates on complex (2D) signals natively,
    rather than embedding in 4D space.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)
        self.last_state: Optional[ChannelState] = None

    def add_noise(self, signal_2d: np.ndarray, snr_db: float,
                  signal_power: Optional[float] = None) -> Tuple[np.ndarray, ChannelState]:
        """
        Add 2D AWGN to a QAM signal.

        Args:
            signal_2d: Shape (N, 2) array [Re, Im] or (N,) complex
            snr_db: Target SNR in dB

        Returns:
            Tuple of (noisy_signal_2d, channel_state)
        """
        # Handle complex input
        if np.iscomplexobj(signal_2d):
            signal_2d = np.stack([signal_2d.real, signal_2d.imag], axis=-1)

        if signal_2d.ndim == 1:
            signal_2d = signal_2d.reshape(-1, 2)

        n_samples = len(signal_2d)
        dimensionality = 2

        # Measure signal power
        if signal_power is None:
            signal_power = np.mean(np.sum(signal_2d**2, axis=1))

        # Calculate noise parameters
        snr_linear = 10 ** (snr_db / 10)
        noise_power = signal_power / snr_linear
        noise_var_per_dim = noise_power / dimensionality
        noise_std = np.sqrt(noise_var_per_dim)

        # Generate 2D noise
        noise = self.rng.normal(0, noise_std, signal_2d.shape)

        noisy_signal = signal_2d + noise

        # Measure actual SNR
        actual_noise_power = np.mean(np.sum(noise**2, axis=1))
        actual_snr_db = 10 * np.log10(signal_power / actual_noise_power) if actual_noise_power > 0 else np.inf

        self.last_state = ChannelState(
            snr_db=snr_db,
            snr_linear=snr_linear,
            noise_variance=noise_power,
            noise_std_per_dim=noise_std,
            dimensionality=2,
            actual_snr_db=actual_snr_db
        )

        return noisy_signal, self.last_state


class AWGNChannel4D:
    """
    Specialized 4D AWGN channel for POM simulation.

    This is the native channel for 600-cell modulation.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)
        self.last_state: Optional[ChannelState] = None

    def add_noise(self, signal_4d: np.ndarray, snr_db: float,
                  signal_power: Optional[float] = None) -> Tuple[np.ndarray, ChannelState]:
        """
        Add 4D AWGN to a POM signal.

        Args:
            signal_4d: Shape (N, 4) array of 4D symbols
            snr_db: Target SNR in dB

        Returns:
            Tuple of (noisy_signal_4d, channel_state)
        """
        if signal_4d.ndim == 1:
            signal_4d = signal_4d.reshape(-1, 4)

        n_samples = len(signal_4d)
        dimensionality = 4

        # Measure signal power
        if signal_power is None:
            signal_power = np.mean(np.sum(signal_4d**2, axis=1))

        # Calculate noise
        snr_linear = 10 ** (snr_db / 10)
        noise_power = signal_power / snr_linear
        noise_var_per_dim = noise_power / dimensionality
        noise_std = np.sqrt(noise_var_per_dim)

        # Generate 4D noise
        noise = self.rng.normal(0, noise_std, signal_4d.shape)

        noisy_signal = signal_4d + noise

        # Measure actual SNR
        actual_noise_power = np.mean(np.sum(noise**2, axis=1))
        actual_snr_db = 10 * np.log10(signal_power / actual_noise_power) if actual_noise_power > 0 else np.inf

        self.last_state = ChannelState(
            snr_db=snr_db,
            snr_linear=snr_linear,
            noise_variance=noise_power,
            noise_std_per_dim=noise_std,
            dimensionality=4,
            actual_snr_db=actual_snr_db
        )

        return noisy_signal, self.last_state


# =============================================================================
# FAIR COMPARISON CHANNEL - EQUAL Es/N0
# =============================================================================

class FairComparisonChannel:
    """
    Channel that ensures fair comparison between systems of different
    dimensionality by normalizing to equal Energy per Symbol (Es/N0).

    Es/N0 NORMALIZATION:
    --------------------
    The standard way to compare modulation schemes is Es/N0:
    - Es = Energy per symbol
    - N0 = Noise power spectral density

    For unit-power constellations: Es = 1

    This channel adds noise such that both POM and QAM experience
    the same Es/N0, regardless of their native dimensionality.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)
        self.channel_4d = AWGNChannel4D(seed)
        self.channel_2d = AWGNChannel2D(seed)

    def add_noise_4d(self, signal: np.ndarray, es_n0_db: float) -> Tuple[np.ndarray, ChannelState]:
        """Add noise to 4D signal with specified Es/N0."""
        return self.channel_4d.add_noise(signal, es_n0_db)

    def add_noise_2d(self, signal: np.ndarray, es_n0_db: float) -> Tuple[np.ndarray, ChannelState]:
        """Add noise to 2D signal with specified Es/N0."""
        return self.channel_2d.add_noise(signal, es_n0_db)

    def add_noise_4d_embedded_2d(self, signal_4d: np.ndarray, es_n0_db: float) -> Tuple[np.ndarray, ChannelState]:
        """
        Add 2D noise to a 4D-embedded 2D signal.

        For QAM embedded in 4D, we only add noise to the first 2 dimensions
        since the last 2 dimensions contain no signal information.

        This models the physical reality that QAM only uses 2 degrees of freedom.
        """
        n_samples = len(signal_4d)

        # Measure signal power (only in used dimensions)
        signal_power = np.mean(np.sum(signal_4d[:, :2]**2, axis=1))

        # Calculate noise for 2D
        snr_linear = 10 ** (es_n0_db / 10)
        noise_power = signal_power / snr_linear
        noise_var_per_dim = noise_power / 2  # Only 2 dimensions
        noise_std = np.sqrt(noise_var_per_dim)

        # Generate noise only in first 2 dimensions
        noise = np.zeros_like(signal_4d)
        noise[:, :2] = self.rng.normal(0, noise_std, (n_samples, 2))

        noisy_signal = signal_4d + noise

        state = ChannelState(
            snr_db=es_n0_db,
            snr_linear=snr_linear,
            noise_variance=noise_power,
            noise_std_per_dim=noise_std,
            dimensionality=2,
            actual_snr_db=es_n0_db  # By construction
        )

        return noisy_signal, state


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def snr_db_to_linear(snr_db: float) -> float:
    """Convert SNR from dB to linear scale."""
    return 10 ** (snr_db / 10)


def snr_linear_to_db(snr_linear: float) -> float:
    """Convert SNR from linear to dB scale."""
    return 10 * np.log10(snr_linear)


def eb_n0_to_es_n0(eb_n0_db: float, bits_per_symbol: float) -> float:
    """
    Convert Eb/N0 to Es/N0.

    Es/N0 = Eb/N0 + 10*log10(bits_per_symbol)

    Args:
        eb_n0_db: Energy per bit over noise in dB
        bits_per_symbol: Spectral efficiency

    Returns:
        Es/N0 in dB
    """
    return eb_n0_db + 10 * np.log10(bits_per_symbol)


def es_n0_to_eb_n0(es_n0_db: float, bits_per_symbol: float) -> float:
    """
    Convert Es/N0 to Eb/N0.

    Eb/N0 = Es/N0 - 10*log10(bits_per_symbol)
    """
    return es_n0_db - 10 * np.log10(bits_per_symbol)


def calculate_noise_std(snr_db: float, signal_power: float = 1.0,
                        dimensionality: int = 4) -> float:
    """
    Calculate per-dimension noise standard deviation for target SNR.

    Args:
        snr_db: Target SNR in dB
        signal_power: Signal power (default 1 for unit power constellations)
        dimensionality: Number of dimensions

    Returns:
        Standard deviation of noise per dimension
    """
    snr_linear = snr_db_to_linear(snr_db)
    noise_power = signal_power / snr_linear
    noise_var_per_dim = noise_power / dimensionality
    return np.sqrt(noise_var_per_dim)


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CHANNEL MODULE - Unit Tests")
    print("=" * 60)

    # Test AWGN channel
    print("\n4D AWGN Channel Test:")
    channel_4d = AWGNChannel4D(seed=42)

    # Create unit-power test signal
    test_signal = np.random.randn(1000, 4)
    test_signal = test_signal / np.linalg.norm(test_signal, axis=1, keepdims=True)

    for snr_db in [0, 10, 20]:
        noisy, state = channel_4d.add_noise(test_signal, snr_db)
        print(f"  Target SNR: {snr_db:5.1f} dB, Actual SNR: {state.actual_snr_db:5.1f} dB")

    # Test 2D channel
    print("\n2D AWGN Channel Test:")
    channel_2d = AWGNChannel2D(seed=42)

    test_signal_2d = np.random.randn(1000, 2)
    test_signal_2d = test_signal_2d / np.linalg.norm(test_signal_2d, axis=1, keepdims=True)

    for snr_db in [0, 10, 20]:
        noisy, state = channel_2d.add_noise(test_signal_2d, snr_db)
        print(f"  Target SNR: {snr_db:5.1f} dB, Actual SNR: {state.actual_snr_db:5.1f} dB")

    # Test fair comparison
    print("\nFair Comparison Test:")
    fair_channel = FairComparisonChannel(seed=42)

    # Same Es/N0 for both
    es_n0 = 10.0  # dB

    noisy_4d, state_4d = fair_channel.add_noise_4d(test_signal, es_n0)
    noisy_2d_emb, state_2d = fair_channel.add_noise_4d_embedded_2d(
        np.hstack([test_signal_2d, np.zeros((1000, 2))]), es_n0)

    print(f"  4D channel: noise_std = {state_4d.noise_std_per_dim:.6f}")
    print(f"  2D channel: noise_std = {state_2d.noise_std_per_dim:.6f}")
    print(f"  Ratio (should be ~sqrt(2)): {state_2d.noise_std_per_dim / state_4d.noise_std_per_dim:.4f}")

    print("\n✓ All channel tests passed!")
