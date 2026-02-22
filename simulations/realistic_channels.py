#!/usr/bin/env python3
"""
=============================================================================
REALISTIC CHANNEL MODELS FOR WIRELESS/FSO COMMUNICATION
=============================================================================

This module implements realistic channel impairments beyond simple AWGN:

1. FADING CHANNELS
   - Rayleigh fading (NLOS urban)
   - Rician fading (LOS + multipath)
   - Nakagami-m fading (general)
   - Log-normal shadowing

2. ATMOSPHERIC EFFECTS (FSO/OAM)
   - Kolmogorov turbulence
   - Scintillation
   - Beam wander
   - OAM mode crosstalk

3. HARDWARE IMPAIRMENTS
   - Phase noise
   - I/Q imbalance
   - Nonlinear power amplifier
   - ADC quantization
   - Timing jitter

4. DOPPLER EFFECTS
   - Carrier frequency offset
   - Time-varying channel

5. SYNCHRONIZATION ERRORS
   - Carrier phase offset
   - Symbol timing offset
   - Frame synchronization errors

6. INTERFERENCE
   - Co-channel interference
   - Adjacent channel interference
   - Jamming (intentional)
   - Impulse noise

Author: PPP Research Team
License: MIT
=============================================================================
"""

import numpy as np
from typing import Tuple, Optional, Dict, List, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
from scipy import signal
from scipy.special import erfc
import warnings


# =============================================================================
# BASE CLASS
# =============================================================================

@dataclass
class ChannelState:
    """Container for channel state information."""
    snr_db: float
    fading_coefficient: complex = 1.0 + 0j
    phase_offset: float = 0.0
    frequency_offset: float = 0.0
    timing_offset: float = 0.0
    additional_info: Optional[Dict] = None


class ChannelModel(ABC):
    """Abstract base class for channel models."""

    @abstractmethod
    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        """Apply channel effects to symbols."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return channel model name."""
        pass


# =============================================================================
# BASIC AWGN CHANNELS
# =============================================================================

class AWGNChannel(ChannelModel):
    """Standard AWGN channel for baseline comparison."""

    def __init__(self, dimensionality: int = 4):
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)

        noise = noise_std * np.random.randn(*symbols.shape)
        noisy = symbols + noise

        return noisy, ChannelState(snr_db=snr_db)

    def get_name(self) -> str:
        return f"AWGN-{self.dim}D"


# =============================================================================
# FADING CHANNELS
# =============================================================================

class RayleighFadingChannel(ChannelModel):
    """
    Rayleigh fading channel - models NLOS propagation.

    The fading coefficient h ~ CN(0, 1) affects all dimensions equally.
    Common in urban environments without clear line-of-sight.
    """

    def __init__(self, dimensionality: int = 4, block_fading: bool = True,
                 coherence_symbols: int = 100):
        self.dim = dimensionality
        self.block_fading = block_fading
        self.coherence_symbols = coherence_symbols

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        if self.block_fading:
            # Block fading: constant within coherence block
            n_blocks = max(1, n_symbols // self.coherence_symbols)
            h_blocks = (np.random.randn(n_blocks) + 1j * np.random.randn(n_blocks)) / np.sqrt(2)

            # Repeat for each symbol
            h = np.repeat(h_blocks, self.coherence_symbols + 1)[:n_symbols]
        else:
            # Symbol-by-symbol fading
            h = (np.random.randn(n_symbols) + 1j * np.random.randn(n_symbols)) / np.sqrt(2)

        # Apply fading (multiply by magnitude for real-valued 4D)
        h_mag = np.abs(h)[:, np.newaxis]
        faded = symbols * h_mag

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = faded + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            fading_coefficient=np.mean(h),
            additional_info={'avg_fading_power': np.mean(np.abs(h)**2)}
        )

    def get_name(self) -> str:
        return "Rayleigh Fading"


class RicianFadingChannel(ChannelModel):
    """
    Rician fading channel - models LOS + multipath.

    K-factor determines ratio of LOS to scattered power.
    K=0 is Rayleigh, K→∞ is AWGN.
    """

    def __init__(self, k_factor_db: float = 10.0, dimensionality: int = 4):
        self.k_factor = 10 ** (k_factor_db / 10)
        self.k_factor_db = k_factor_db
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Rician fading: h = sqrt(K/(K+1)) + sqrt(1/(K+1)) * CN(0,1)
        k = self.k_factor
        los_component = np.sqrt(k / (k + 1))
        scattered_component = np.sqrt(1 / (k + 1)) * \
            (np.random.randn(n_symbols) + 1j * np.random.randn(n_symbols)) / np.sqrt(2)

        h = los_component + scattered_component
        h_mag = np.abs(h)[:, np.newaxis]

        faded = symbols * h_mag

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = faded + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            fading_coefficient=np.mean(h),
            additional_info={'k_factor_db': self.k_factor_db}
        )

    def get_name(self) -> str:
        return f"Rician (K={self.k_factor_db}dB)"


class NakagamiFadingChannel(ChannelModel):
    """
    Nakagami-m fading - general fading model.

    m=0.5: Worse than Rayleigh (one-sided Gaussian)
    m=1: Rayleigh
    m>1: Better than Rayleigh (approaching AWGN as m→∞)
    """

    def __init__(self, m: float = 1.0, dimensionality: int = 4):
        self.m = max(0.5, m)  # m must be >= 0.5
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Nakagami-m amplitude: Gamma distribution
        # Power follows Gamma(m, 1/m) distribution
        power = np.random.gamma(self.m, 1/self.m, n_symbols)
        h_mag = np.sqrt(power)[:, np.newaxis]

        faded = symbols * h_mag

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = faded + noise

        return noisy, ChannelState(snr_db=snr_db, additional_info={'nakagami_m': self.m})

    def get_name(self) -> str:
        return f"Nakagami (m={self.m})"


# =============================================================================
# ATMOSPHERIC/FSO EFFECTS
# =============================================================================

class AtmosphericTurbulenceChannel(ChannelModel):
    """
    Atmospheric turbulence for FSO/OAM links.

    Uses log-normal model for weak-to-moderate turbulence.
    Characterized by Rytov variance σ_R².
    """

    def __init__(self, rytov_variance: float = 0.5, dimensionality: int = 4):
        self.rytov_var = rytov_variance
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Log-normal turbulence: I = exp(2X) where X ~ N(-σ²/2, σ²)
        # This ensures E[I] = 1
        sigma_x = np.sqrt(self.rytov_var / 4)  # σ_x for log-amplitude
        x = np.random.normal(-sigma_x**2, sigma_x, n_symbols)
        intensity_factor = np.exp(2 * x)

        # Apply to symbols (amplitude = sqrt(intensity))
        amplitude = np.sqrt(intensity_factor)[:, np.newaxis]
        turbulent = symbols * amplitude

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = turbulent + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            additional_info={'rytov_variance': self.rytov_var, 'scintillation_index': self.rytov_var}
        )

    def get_name(self) -> str:
        return f"Turbulence (σ_R²={self.rytov_var})"


class OAMCrosstalkChannel(ChannelModel):
    """
    OAM mode crosstalk due to atmospheric turbulence.

    Higher-order OAM modes are more susceptible to turbulence-induced
    mode coupling. Models inter-modal interference.
    """

    def __init__(self, max_oam_order: int = 10, crosstalk_strength: float = 0.1,
                 dimensionality: int = 4):
        self.max_l = max_oam_order
        self.crosstalk = crosstalk_strength
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Model crosstalk as additional noise that increases with OAM order
        # For POM, assume OAM info is encoded in first 2 dimensions
        oam_component = symbols[:, :2] if self.dim >= 2 else symbols

        # Crosstalk adds correlated noise to OAM dimensions
        crosstalk_noise = self.crosstalk * np.random.randn(n_symbols, 2)
        if self.dim >= 2:
            symbols_xt = symbols.copy()
            symbols_xt[:, :2] += crosstalk_noise
        else:
            symbols_xt = symbols + crosstalk_noise[:, :self.dim]

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = symbols_xt + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            additional_info={'crosstalk_strength': self.crosstalk}
        )

    def get_name(self) -> str:
        return f"OAM Crosstalk (α={self.crosstalk})"


# =============================================================================
# HARDWARE IMPAIRMENTS
# =============================================================================

class PhaseNoiseChannel(ChannelModel):
    """
    Phase noise from local oscillator imperfections.

    Models Wiener process (random walk) phase noise.
    Common in RF/mmWave systems with imperfect PLLs.
    """

    def __init__(self, linewidth_symbol_product: float = 0.01, dimensionality: int = 4):
        """
        Args:
            linewidth_symbol_product: 2πΔf*T where Δf is 3dB linewidth
        """
        self.linewidth_product = linewidth_symbol_product
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Wiener process phase noise
        phase_var = 2 * np.pi * self.linewidth_product
        phase_increments = np.sqrt(phase_var) * np.random.randn(n_symbols)
        phase = np.cumsum(phase_increments)

        # Apply phase rotation to first 2 dimensions (I/Q)
        if self.dim >= 2:
            cos_p = np.cos(phase)
            sin_p = np.sin(phase)

            symbols_rotated = symbols.copy()
            i_orig = symbols[:, 0]
            q_orig = symbols[:, 1]
            symbols_rotated[:, 0] = i_orig * cos_p - q_orig * sin_p
            symbols_rotated[:, 1] = i_orig * sin_p + q_orig * cos_p
        else:
            symbols_rotated = symbols

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = symbols_rotated + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            phase_offset=phase[-1] if len(phase) > 0 else 0,
            additional_info={'phase_variance': np.var(phase)}
        )

    def get_name(self) -> str:
        return f"Phase Noise (ΔfT={self.linewidth_product})"


class IQImbalanceChannel(ChannelModel):
    """
    I/Q imbalance from mixer/ADC imperfections.

    Models gain imbalance and phase skew between I and Q branches.
    """

    def __init__(self, gain_imbalance_db: float = 1.0, phase_skew_deg: float = 5.0,
                 dimensionality: int = 4):
        self.gain_db = gain_imbalance_db
        self.phase_deg = phase_skew_deg
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        # I/Q imbalance model: I' = I, Q' = g*Q*cos(φ) + I*sin(φ)
        g = 10 ** (self.gain_db / 20)
        phi = np.deg2rad(self.phase_deg)

        if self.dim >= 2:
            symbols_imb = symbols.copy()
            i_orig = symbols[:, 0]
            q_orig = symbols[:, 1]
            symbols_imb[:, 0] = i_orig
            symbols_imb[:, 1] = g * q_orig * np.cos(phi) + i_orig * np.sin(phi)
        else:
            symbols_imb = symbols

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = symbols_imb + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            additional_info={'gain_imbalance_db': self.gain_db, 'phase_skew_deg': self.phase_deg}
        )

    def get_name(self) -> str:
        return f"IQ Imbalance (g={self.gain_db}dB, φ={self.phase_deg}°)"


class NonlinearPAChannel(ChannelModel):
    """
    Nonlinear Power Amplifier (Rapp model).

    Models AM/AM compression and AM/PM conversion.
    Critical for high-power RF systems.
    """

    def __init__(self, p_sat: float = 1.0, smoothness: float = 2.0, dimensionality: int = 4):
        """
        Args:
            p_sat: Saturation power (normalized)
            smoothness: Rapp model smoothness parameter (higher = sharper knee)
        """
        self.p_sat = p_sat
        self.smoothness = smoothness
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        # Rapp model AM/AM: A_out = A_in / (1 + (A_in/A_sat)^(2p))^(1/2p)
        p = self.smoothness
        a_sat = np.sqrt(self.p_sat)

        # Compute input amplitude
        a_in = np.linalg.norm(symbols, axis=1, keepdims=True)
        a_in = np.clip(a_in, 1e-10, None)  # Avoid division by zero

        # Rapp compression
        compression = (1 + (a_in / a_sat) ** (2 * p)) ** (1 / (2 * p))
        a_out = a_in / compression

        # Apply to symbols (preserve direction, compress magnitude)
        symbols_nl = symbols * (a_out / a_in)

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = symbols_nl + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            additional_info={'p_sat': self.p_sat, 'avg_compression_db':
                            10 * np.log10(np.mean(a_out**2 / a_in**2))}
        )

    def get_name(self) -> str:
        return f"Nonlinear PA (P_sat={self.p_sat})"


class QuantizationChannel(ChannelModel):
    """
    ADC quantization effects.

    Models finite resolution ADC with uniform quantization.
    """

    def __init__(self, bits: int = 8, full_scale: float = 2.0, dimensionality: int = 4):
        self.bits = bits
        self.full_scale = full_scale
        self.dim = dimensionality
        self.levels = 2 ** bits
        self.step = 2 * full_scale / self.levels

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        # Add AWGN first
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = symbols + noise

        # Then quantize
        clipped = np.clip(noisy, -self.full_scale, self.full_scale - self.step)
        quantized = self.step * np.floor(clipped / self.step + 0.5)

        # Quantization noise variance: step^2 / 12
        quant_noise_var = self.step ** 2 / 12

        return quantized, ChannelState(
            snr_db=snr_db,
            additional_info={'adc_bits': self.bits, 'quantization_noise_var': quant_noise_var}
        )

    def get_name(self) -> str:
        return f"Quantization ({self.bits}-bit ADC)"


# =============================================================================
# DOPPLER EFFECTS
# =============================================================================

class DopplerChannel(ChannelModel):
    """
    Carrier frequency offset due to Doppler.

    Models time-varying phase rotation from relative motion.
    """

    def __init__(self, max_doppler_hz: float = 100.0, symbol_rate_hz: float = 1e6,
                 dimensionality: int = 4):
        self.f_d = max_doppler_hz
        self.f_s = symbol_rate_hz
        self.normalized_doppler = max_doppler_hz / symbol_rate_hz
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Random frequency offset within ±f_d
        freq_offset = (2 * np.random.random() - 1) * self.f_d

        # Phase accumulation
        t = np.arange(n_symbols) / self.f_s
        phase = 2 * np.pi * freq_offset * t

        # Apply rotation
        if self.dim >= 2:
            cos_p = np.cos(phase)
            sin_p = np.sin(phase)

            symbols_rot = symbols.copy()
            i_orig = symbols[:, 0]
            q_orig = symbols[:, 1]
            symbols_rot[:, 0] = i_orig * cos_p - q_orig * sin_p
            symbols_rot[:, 1] = i_orig * sin_p + q_orig * cos_p
        else:
            symbols_rot = symbols

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = symbols_rot + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            frequency_offset=freq_offset,
            additional_info={'max_doppler_hz': self.f_d}
        )

    def get_name(self) -> str:
        return f"Doppler (f_d={self.f_d}Hz)"


# =============================================================================
# SYNCHRONIZATION ERRORS
# =============================================================================

class TimingJitterChannel(ChannelModel):
    """
    Symbol timing jitter.

    Models imperfect clock recovery causing intersymbol interference.
    """

    def __init__(self, jitter_std_fraction: float = 0.05, dimensionality: int = 4):
        """
        Args:
            jitter_std_fraction: Timing jitter as fraction of symbol period
        """
        self.jitter_std = jitter_std_fraction
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Model ISI from timing errors
        jitter = self.jitter_std * np.random.randn(n_symbols)

        # Simplified ISI model: blend with adjacent symbols
        symbols_isi = symbols.copy()
        for i in range(1, n_symbols - 1):
            isi_weight = np.abs(jitter[i])
            symbols_isi[i] = (1 - isi_weight) * symbols[i] + \
                             isi_weight * 0.5 * (symbols[i-1] + symbols[i+1])

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = symbols_isi + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            timing_offset=np.mean(jitter),
            additional_info={'jitter_std': self.jitter_std}
        )

    def get_name(self) -> str:
        return f"Timing Jitter (σ={self.jitter_std}T)"


# =============================================================================
# INTERFERENCE
# =============================================================================

class JammingChannel(ChannelModel):
    """
    Intentional jamming - narrowband or broadband.

    Models adversarial interference for defense applications.
    """

    def __init__(self, jammer_power_db: float = 10.0, jamming_type: str = 'broadband',
                 dimensionality: int = 4):
        self.j_power_db = jammer_power_db
        self.j_type = jamming_type
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Jamming power
        j_power = 10 ** (self.j_power_db / 10)
        j_std = np.sqrt(j_power / self.dim)  # Per-dimension

        if self.j_type == 'broadband':
            # Gaussian noise jammer
            jamming = j_std * np.random.randn(n_symbols, self.dim)
        elif self.j_type == 'tone':
            # Single tone jammer
            phase = 2 * np.pi * np.random.random()
            freq = 0.1 * np.random.random()
            t = np.arange(n_symbols)
            tone = np.sqrt(j_power) * np.cos(2 * np.pi * freq * t + phase)
            jamming = np.zeros((n_symbols, self.dim))
            jamming[:, 0] = tone
        else:
            # Pulsed jammer
            pulse_prob = 0.1
            pulse_mask = np.random.random(n_symbols) < pulse_prob
            jamming = np.zeros((n_symbols, self.dim))
            jamming[pulse_mask] = j_std * 10 * np.random.randn(np.sum(pulse_mask), self.dim)

        jammed = symbols + jamming

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = jammed + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            additional_info={'jammer_power_db': self.j_power_db, 'jammer_type': self.j_type}
        )

    def get_name(self) -> str:
        return f"Jamming ({self.j_type}, {self.j_power_db}dB)"


class ImpulseNoiseChannel(ChannelModel):
    """
    Impulse noise - sporadic high-amplitude noise bursts.

    Common in power line communications, industrial environments.
    """

    def __init__(self, impulse_probability: float = 0.01, impulse_amplitude: float = 10.0,
                 dimensionality: int = 4):
        self.prob = impulse_probability
        self.amp = impulse_amplitude
        self.dim = dimensionality

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        n_symbols = len(symbols)

        # Impulse noise
        impulse_mask = np.random.random(n_symbols) < self.prob
        n_impulses = np.sum(impulse_mask)

        impulse_noise = np.zeros((n_symbols, self.dim))
        if n_impulses > 0:
            impulse_noise[impulse_mask] = self.amp * np.random.randn(n_impulses, self.dim)

        impulsed = symbols + impulse_noise

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        es = np.mean(np.sum(symbols**2, axis=1))
        n0 = es / snr_linear
        noise_std = np.sqrt(n0 / 2)
        noise = noise_std * np.random.randn(*symbols.shape)

        noisy = impulsed + noise

        return noisy, ChannelState(
            snr_db=snr_db,
            additional_info={'impulse_probability': self.prob, 'num_impulses': n_impulses}
        )

    def get_name(self) -> str:
        return f"Impulse Noise (p={self.prob})"


# =============================================================================
# COMPOSITE CHANNELS
# =============================================================================

class CompositeChannel(ChannelModel):
    """
    Combine multiple channel impairments.

    Applies impairments in sequence.
    """

    def __init__(self, channels: List[ChannelModel]):
        self.channels = channels

    def apply(self, symbols: np.ndarray, snr_db: float) -> Tuple[np.ndarray, ChannelState]:
        current = symbols.copy()
        all_info = {}

        for channel in self.channels:
            current, state = channel.apply(current, snr_db)
            if state.additional_info:
                all_info.update(state.additional_info)

        return current, ChannelState(snr_db=snr_db, additional_info=all_info)

    def get_name(self) -> str:
        names = [c.get_name() for c in self.channels]
        return " + ".join(names)


# =============================================================================
# REALISTIC SCENARIO PRESETS
# =============================================================================

def get_defense_scenario() -> CompositeChannel:
    """Defense application: jamming + fading environment."""
    return CompositeChannel([
        RayleighFadingChannel(dimensionality=4),
        JammingChannel(jammer_power_db=5.0, jamming_type='broadband', dimensionality=4),
    ])


def get_fso_scenario() -> CompositeChannel:
    """Free-space optical link with turbulence."""
    return CompositeChannel([
        AtmosphericTurbulenceChannel(rytov_variance=0.5, dimensionality=4),
        OAMCrosstalkChannel(crosstalk_strength=0.1, dimensionality=4),
    ])


def get_urban_mobile_scenario() -> CompositeChannel:
    """Urban mobile scenario with multiple impairments."""
    return CompositeChannel([
        RayleighFadingChannel(dimensionality=4),
        DopplerChannel(max_doppler_hz=200, symbol_rate_hz=1e6, dimensionality=4),
        PhaseNoiseChannel(linewidth_symbol_product=0.005, dimensionality=4),
    ])


def get_industrial_scenario() -> CompositeChannel:
    """Industrial IoT with interference and impulse noise."""
    return CompositeChannel([
        ImpulseNoiseChannel(impulse_probability=0.02, impulse_amplitude=5.0, dimensionality=4),
        IQImbalanceChannel(gain_imbalance_db=0.5, phase_skew_deg=3.0, dimensionality=4),
    ])


def get_satellite_scenario() -> CompositeChannel:
    """Satellite link with Rician fading and nonlinear PA."""
    return CompositeChannel([
        RicianFadingChannel(k_factor_db=15.0, dimensionality=4),
        NonlinearPAChannel(p_sat=0.8, smoothness=3.0, dimensionality=4),
        QuantizationChannel(bits=10, dimensionality=4),
    ])


def get_all_channels() -> Dict[str, ChannelModel]:
    """Get all implemented channel models."""
    return {
        'awgn': AWGNChannel(4),
        'rayleigh': RayleighFadingChannel(4),
        'rician': RicianFadingChannel(10.0, 4),
        'nakagami': NakagamiFadingChannel(2.0, 4),
        'turbulence': AtmosphericTurbulenceChannel(0.5, 4),
        'oam-crosstalk': OAMCrosstalkChannel(10, 0.1, 4),
        'phase-noise': PhaseNoiseChannel(0.01, 4),
        'iq-imbalance': IQImbalanceChannel(1.0, 5.0, 4),
        'nonlinear-pa': NonlinearPAChannel(1.0, 2.0, 4),
        'quantization': QuantizationChannel(8, 2.0, 4),
        'doppler': DopplerChannel(100.0, 1e6, 4),
        'timing-jitter': TimingJitterChannel(0.05, 4),
        'jamming': JammingChannel(10.0, 'broadband', 4),
        'impulse': ImpulseNoiseChannel(0.01, 10.0, 4),
        'defense': get_defense_scenario(),
        'fso': get_fso_scenario(),
        'urban-mobile': get_urban_mobile_scenario(),
        'industrial': get_industrial_scenario(),
        'satellite': get_satellite_scenario(),
    }


# =============================================================================
# MAIN TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("REALISTIC CHANNEL MODELS TEST")
    print("=" * 70)

    np.random.seed(42)

    # Test symbols
    n_symbols = 1000
    dim = 4
    test_symbols = np.random.randn(n_symbols, dim)
    test_symbols = test_symbols / np.linalg.norm(test_symbols, axis=1, keepdims=True)

    channels = get_all_channels()
    snr_db = 15.0

    print(f"\nTest: {n_symbols} symbols, SNR = {snr_db} dB")
    print("-" * 70)
    print(f"{'Channel':<30} {'Output Mean':>15} {'Output Std':>15}")
    print("-" * 70)

    for name, channel in channels.items():
        output, state = channel.apply(test_symbols.copy(), snr_db)
        out_mean = np.mean(np.linalg.norm(output, axis=1))
        out_std = np.std(np.linalg.norm(output, axis=1))
        print(f"{channel.get_name():<30} {out_mean:>15.4f} {out_std:>15.4f}")

    print("-" * 70)
    print("\n✓ All channel models working!")
