"""
Optical Channel Models for CSPM Simulation

Models realistic impairments for:
1. Fiber channels (SMF, MMF)
2. Free-space optical (FSO) channels
3. Subsea cables

Impairments modeled:
- Additive Gaussian noise (ASE from amplifiers)
- Polarization Mode Dispersion (PMD)
- OAM mode crosstalk
- Atmospheric turbulence (FSO)
- Phase noise

IMPORTANT NOTE ON FAIRNESS:
The channel does NOT normalize signals to unit sphere after adding noise.
Such normalization would unfairly benefit CSPM by removing the noise
magnitude component. The receiver handles normalization as part of decoding.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from abc import ABC, abstractmethod
from .transmitter import OpticalSymbol


@dataclass
class ChannelState:
    """Represents the state of the optical channel."""

    snr_db: float  # Signal-to-noise ratio in dB
    ber_raw: float  # Raw bit error rate before correction
    pmd_ps: float  # Polarization mode dispersion (picoseconds)
    oam_crosstalk_db: float  # OAM inter-mode crosstalk
    phase_noise_rad: float  # RMS phase noise

    @property
    def snr_linear(self) -> float:
        return 10 ** (self.snr_db / 10)


class OpticalChannel(ABC):
    """Abstract base class for optical channels."""

    def __init__(
        self,
        snr_db: float = 20.0,
        seed: int = None
    ):
        self.snr_db = snr_db
        self.rng = np.random.default_rng(seed)
        self._symbol_count = 0

    @abstractmethod
    def transmit(self, symbol: OpticalSymbol) -> OpticalSymbol:
        """Transmit a single symbol through the channel."""
        pass

    def transmit_sequence(
        self,
        symbols: List[OpticalSymbol]
    ) -> Tuple[List[OpticalSymbol], ChannelState]:
        """Transmit a sequence of symbols."""
        received = []
        for sym in symbols:
            rx_sym = self.transmit(sym)
            received.append(rx_sym)

        state = self.get_channel_state()
        return received, state

    @abstractmethod
    def get_channel_state(self) -> ChannelState:
        """Get current channel state metrics."""
        pass

    def _add_awgn(self, coords: np.ndarray, snr_db: float) -> np.ndarray:
        """Add Additive White Gaussian Noise."""
        snr_linear = 10 ** (snr_db / 10)
        signal_power = np.sum(coords ** 2)
        noise_power = signal_power / snr_linear
        noise_std = np.sqrt(noise_power / len(coords))

        noise = self.rng.normal(0, noise_std, size=coords.shape)
        return coords + noise


class FiberChannel(OpticalChannel):
    """
    Single-mode fiber channel model.

    Models:
    - ASE noise from EDFAs
    - Polarization Mode Dispersion (PMD)
    - Polarization Dependent Loss (PDL)
    - OAM mode coupling
    - Chromatic dispersion (phase only for narrowband)
    """

    def __init__(
        self,
        length_km: float = 100.0,
        snr_db: float = 20.0,
        pmd_coefficient: float = 0.1,  # ps/sqrt(km)
        oam_crosstalk_db: float = -20.0,  # dB per mode
        n_amplifiers: int = 0,  # Number of inline EDFAs
        seed: int = None
    ):
        super().__init__(snr_db, seed)
        self.length_km = length_km
        self.pmd_coefficient = pmd_coefficient
        self.oam_crosstalk_db = oam_crosstalk_db
        self.n_amplifiers = n_amplifiers

        # Compute derived parameters
        self.pmd_ps = pmd_coefficient * np.sqrt(length_km)
        self.oam_coupling = 10 ** (oam_crosstalk_db / 10)

        # State tracking
        self._total_phase_noise = 0.0
        self._errors_detected = 0

    def _apply_pmd(self, coords: np.ndarray) -> np.ndarray:
        """
        Apply Polarization Mode Dispersion.

        PMD causes random rotation of the polarization state.

        Physical model: PMD (in ps) causes differential group delay between
        polarization modes. For narrowband signals, this manifests as a
        random rotation on the Poincaré sphere proportional to the DGD.

        Conversion: angle (rad) = 2π × DGD × symbol_rate
        For ~10 Gbaud and typical PMD, this gives small rotations.
        We use: angle_std ≈ PMD_ps × 0.001 rad/ps (empirical for 10 Gbaud)
        """
        # Random rotation in the Stokes subspace (coords[1:4])
        # Physical basis: DGD causes SOP rotation on Poincaré sphere
        angle = self.rng.normal(0, self.pmd_ps * 0.001)  # ~0.1° per ps of PMD

        # Random rotation axis on the Poincare sphere
        axis = self.rng.standard_normal(3)
        axis = axis / np.linalg.norm(axis)

        # Rodrigues rotation formula
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)

        stokes = coords[1:4]
        rotated = (
            stokes * cos_a +
            np.cross(axis, stokes) * sin_a +
            axis * np.dot(axis, stokes) * (1 - cos_a)
        )

        result = coords.copy()
        result[1:4] = rotated
        return result

    def _apply_oam_crosstalk(self, coords: np.ndarray) -> np.ndarray:
        """
        Apply OAM mode crosstalk.

        Adjacent OAM modes couple into each other due to fiber imperfections.
        """
        # Model as noise on the OAM component
        oam_noise = self.rng.normal(0, np.sqrt(self.oam_coupling))

        result = coords.copy()
        result[0] += oam_noise

        return result

    def _apply_phase_noise(self, coords: np.ndarray) -> np.ndarray:
        """Apply laser phase noise (affects all components equally)."""
        # Phase noise manifests as rotation in 4D
        phase = self.rng.normal(0, 0.05)  # ~3 degrees RMS
        self._total_phase_noise += abs(phase)

        # Simple phase rotation in the OAM dimension
        result = coords.copy()
        result[0] = coords[0] * np.cos(phase) - coords[1] * np.sin(phase)
        result[1] = coords[0] * np.sin(phase) + coords[1] * np.cos(phase)

        return result

    def transmit(self, symbol: OpticalSymbol) -> OpticalSymbol:
        """
        Transmit symbol through fiber channel.

        NOTE: We do NOT normalize to unit sphere here. That would unfairly
        benefit CSPM by removing the noise magnitude component. The receiver
        is responsible for normalization during geometric quantization.
        This ensures fair comparison with QAM which also receives unnormalized
        noisy symbols.
        """
        coords = symbol.coords.copy()

        # Apply impairments in order
        coords = self._apply_pmd(coords)
        coords = self._apply_oam_crosstalk(coords)
        coords = self._apply_phase_noise(coords)
        coords = self._add_awgn(coords, self.snr_db)

        # DO NOT normalize here - let receiver handle it
        # This is crucial for fair comparison

        self._symbol_count += 1

        return OpticalSymbol(
            coords=coords,
            symbol_index=symbol.symbol_index,
            packet_id=symbol.packet_id,
            timestamp=symbol.timestamp,
            power=symbol.power * 0.9,  # Some loss
            wavelength=symbol.wavelength
        )

    def get_channel_state(self) -> ChannelState:
        return ChannelState(
            snr_db=self.snr_db,
            ber_raw=0.0,  # Computed by receiver
            pmd_ps=self.pmd_ps,
            oam_crosstalk_db=self.oam_crosstalk_db,
            phase_noise_rad=self._total_phase_noise / max(1, self._symbol_count)
        )


class FreespaceChannel(OpticalChannel):
    """
    Free-space optical (FSO) channel model.

    Models:
    - Atmospheric turbulence (scintillation)
    - Pointing jitter
    - Background light interference
    - Weather attenuation
    """

    def __init__(
        self,
        distance_km: float = 1.0,
        snr_db: float = 15.0,
        turbulence_cn2: float = 1e-14,  # Refractive index structure
        pointing_jitter_urad: float = 10.0,  # Pointing error
        weather: str = "clear",  # clear, haze, rain
        seed: int = None
    ):
        super().__init__(snr_db, seed)
        self.distance_km = distance_km
        self.turbulence_cn2 = turbulence_cn2
        self.pointing_jitter = pointing_jitter_urad * 1e-6  # Convert to radians

        # Weather attenuation (dB/km)
        self.weather_atten = {
            "clear": 0.2,
            "haze": 4.0,
            "rain": 20.0,
            "fog": 100.0
        }.get(weather, 0.2)

        # Compute Rytov variance (scintillation strength)
        self.rytov_variance = self._compute_rytov()

    def _compute_rytov(self) -> float:
        """Compute Rytov variance for turbulence strength."""
        k = 2 * np.pi / 1550e-9  # Wavenumber
        L = self.distance_km * 1000  # Path length in meters
        sigma_r2 = 1.23 * self.turbulence_cn2 * k**(7/6) * L**(11/6)
        return sigma_r2

    def _apply_scintillation(self, coords: np.ndarray) -> np.ndarray:
        """
        Apply atmospheric scintillation.

        Turbulence causes random intensity fluctuations and phase distortion.
        OAM modes are affected by azimuthal phase patterns.
        """
        # Log-normal intensity fluctuation
        sigma_I = np.sqrt(self.rytov_variance)
        intensity_factor = np.exp(self.rng.normal(0, sigma_I) - sigma_I**2 / 2)

        # Phase distortion (affects OAM strongly)
        phase_distortion = self.rng.normal(0, np.sqrt(self.rytov_variance))

        result = coords.copy()
        # OAM is particularly sensitive to turbulence
        result[0] += phase_distortion * 0.1

        # Intensity affects all components
        result *= np.sqrt(intensity_factor)

        return result

    def _apply_pointing_error(self, coords: np.ndarray) -> np.ndarray:
        """Apply beam pointing/tracking error."""
        # Pointing error causes coupling loss and mode mixing
        error = self.rng.normal(0, self.pointing_jitter)

        # Primarily affects OAM mode purity
        result = coords.copy()
        result[0] += error * 10  # OAM sensitive to misalignment

        return result

    def _apply_weather_attenuation(self, coords: np.ndarray) -> np.ndarray:
        """Apply weather-dependent attenuation."""
        total_atten_db = self.weather_atten * self.distance_km
        atten_linear = 10 ** (-total_atten_db / 20)

        return coords * atten_linear

    def transmit(self, symbol: OpticalSymbol) -> OpticalSymbol:
        """
        Transmit symbol through free-space channel.

        NOTE: We do NOT normalize to unit sphere here for fair comparison.
        The receiver handles normalization during geometric quantization.
        """
        coords = symbol.coords.copy()

        # Apply impairments
        coords = self._apply_scintillation(coords)
        coords = self._apply_pointing_error(coords)
        coords = self._apply_weather_attenuation(coords)
        coords = self._add_awgn(coords, self.snr_db)

        # DO NOT normalize here - let receiver handle it

        self._symbol_count += 1

        return OpticalSymbol(
            coords=coords,
            symbol_index=symbol.symbol_index,
            packet_id=symbol.packet_id,
            timestamp=symbol.timestamp,
            power=symbol.power * (10 ** (-self.weather_atten * self.distance_km / 10)),
            wavelength=symbol.wavelength
        )

    def get_channel_state(self) -> ChannelState:
        return ChannelState(
            snr_db=self.snr_db,
            ber_raw=0.0,
            pmd_ps=0.0,  # No PMD in free space
            oam_crosstalk_db=-10 * np.log10(self.rytov_variance + 0.01),
            phase_noise_rad=np.sqrt(self.rytov_variance)
        )


class SubseaChannel(FiberChannel):
    """
    Subsea cable channel model.

    Extends fiber model with:
    - Long distances (thousands of km)
    - Multiple EDFA repeaters
    - Accumulated ASE noise
    - Temperature/pressure effects
    """

    def __init__(
        self,
        length_km: float = 6000.0,  # Trans-Atlantic
        repeater_spacing_km: float = 80.0,
        snr_db: float = 12.0,  # Lower due to accumulated noise
        seed: int = None
    ):
        n_repeaters = int(length_km / repeater_spacing_km)

        super().__init__(
            length_km=length_km,
            snr_db=snr_db,
            pmd_coefficient=0.05,  # Better fiber for subsea
            oam_crosstalk_db=-25.0,  # Better control
            n_amplifiers=n_repeaters,
            seed=seed
        )

        self.repeater_spacing_km = repeater_spacing_km
        self.n_repeaters = n_repeaters

        # Accumulated ASE noise degrades SNR
        self.effective_snr = snr_db - 10 * np.log10(n_repeaters)

    def transmit(self, symbol: OpticalSymbol) -> OpticalSymbol:
        """Transmit with repeater-accumulated noise."""
        # Override SNR for this transmission
        original_snr = self.snr_db
        self.snr_db = self.effective_snr

        result = super().transmit(symbol)

        self.snr_db = original_snr
        return result


def create_channel(
    channel_type: str,
    snr_db: float = 20.0,
    **kwargs
) -> OpticalChannel:
    """Factory function to create channel instances."""
    if channel_type == "fiber":
        return FiberChannel(snr_db=snr_db, **kwargs)
    elif channel_type == "freespace":
        return FreespaceChannel(snr_db=snr_db, **kwargs)
    elif channel_type == "subsea":
        return SubseaChannel(snr_db=snr_db, **kwargs)
    else:
        raise ValueError(f"Unknown channel type: {channel_type}")


if __name__ == "__main__":
    from .transmitter import CSPMTransmitter, generate_random_data

    # Test fiber channel
    tx = CSPMTransmitter()
    data = generate_random_data(100)
    symbols, _ = tx.modulate_packet(data)

    print("Testing Fiber Channel (100 km, 20 dB SNR)")
    channel = FiberChannel(length_km=100, snr_db=20, seed=42)
    rx_symbols, state = channel.transmit_sequence(symbols[:10])

    for i, (tx_s, rx_s) in enumerate(zip(symbols[:5], rx_symbols[:5])):
        error = np.linalg.norm(tx_s.coords - rx_s.coords)
        print(f"  Symbol {i}: TX={tx_s.coords[:2]}, RX={rx_s.coords[:2]}, error={error:.4f}")

    print(f"\nChannel state: SNR={state.snr_db}dB, PMD={state.pmd_ps:.2f}ps")

    # Test free-space channel
    print("\nTesting Free-Space Channel (1 km, 15 dB SNR, haze)")
    fso_channel = FreespaceChannel(distance_km=1, snr_db=15, weather="haze", seed=42)
    rx_symbols_fso, state_fso = fso_channel.transmit_sequence(symbols[:10])

    for i, (tx_s, rx_s) in enumerate(zip(symbols[:5], rx_symbols_fso[:5])):
        error = np.linalg.norm(tx_s.coords - rx_s.coords)
        print(f"  Symbol {i}: error={error:.4f}")

    print(f"\nFSO state: SNR={state_fso.snr_db}dB, phase_noise={state_fso.phase_noise_rad:.4f}rad")
