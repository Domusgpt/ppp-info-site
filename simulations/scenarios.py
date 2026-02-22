#!/usr/bin/env python3
"""
=============================================================================
ENHANCED POM SIMULATION - MULTI-SCENARIO REAL-WORLD COMPARISON
=============================================================================

This enhanced simulation demonstrates POM's advantages across multiple
real-world scenarios relevant to both defense and commercial applications.

SCENARIOS COVERED:
------------------
1. AWGN Baseline - Pure Gaussian noise (ideal conditions)
2. Defense: Jamming - Narrowband interference (electronic warfare)
3. Defense: Rayleigh Fading - Fast-moving hypersonic tracking
4. Commercial: Atmospheric Turbulence - Free-space optical links
5. Commercial: Phase Noise - Oscillator imperfections in 6G
6. Multipath - Urban/indoor reflections

REAL-WORLD RELEVANCE:
---------------------
Defense (AFWERX/MDA):
- Hypersonic tracking requires handling Doppler shifts up to 35 MHz
- Jamming resistance is critical for command & control links
- Low-latency FPGA processing is mandatory

Commercial (NSF/6G):
- Atmospheric turbulence causes beam wander and scintillation
- Phase noise limits high-order modulation performance
- Multipath is ubiquitous in urban environments

Author: PPP Research Team
License: MIT
Version: 2.1.0 (Multi-Scenario)
=============================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy.stats import rice
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

# Import our modules
from geometry import Polychoron600, QAM64Constellation
from modem import POMModulator, POMDemodulator, QAMModulator, QAMDemodulator
from channel import AWGNChannel4D, AWGNChannel2D


# =============================================================================
# SCENARIO DEFINITIONS
# =============================================================================

@dataclass
class ScenarioResult:
    """Results for a single scenario run."""
    name: str
    description: str
    snr_range: np.ndarray
    pom_ser: np.ndarray
    pom_ber: np.ndarray
    qam_ser: np.ndarray
    qam_ber: np.ndarray
    relevance: str  # "defense", "commercial", or "both"


# =============================================================================
# ENHANCED CHANNEL MODELS
# =============================================================================

class JammingChannel:
    """
    Simulates narrowband jamming interference.

    DEFENSE RELEVANCE:
    Electronic warfare environments include intentional jamming
    designed to disrupt communications. POM's 4D geometry provides
    natural resilience because jamming energy spreads across
    more dimensions.

    Model: AWGN + sinusoidal interferer at random frequency
    """

    def __init__(self, jammer_power_ratio: float = 0.5, seed: int = None):
        """
        Args:
            jammer_power_ratio: Jammer power relative to signal (0.5 = -3dB)
        """
        self.jammer_power_ratio = jammer_power_ratio
        self.rng = np.random.default_rng(seed)

    def add_interference(self, signal: np.ndarray, snr_db: float) -> np.ndarray:
        """Add AWGN + narrowband jamming."""
        n_samples, dims = signal.shape

        # AWGN component
        snr_linear = 10 ** (snr_db / 10)
        signal_power = np.mean(np.sum(signal**2, axis=1))
        noise_power = signal_power / snr_linear
        noise_std = np.sqrt(noise_power / dims)
        awgn = self.rng.normal(0, noise_std, signal.shape)

        # Jamming component: sinusoidal interference
        # Affects primarily 2 dimensions (like a narrowband signal would)
        jammer_amp = np.sqrt(self.jammer_power_ratio * signal_power)
        freq = self.rng.uniform(0.1, 0.4)  # Random frequency
        phase = self.rng.uniform(0, 2*np.pi)
        t = np.arange(n_samples)

        jammer = np.zeros_like(signal)
        jammer[:, 0] = jammer_amp * np.sin(2*np.pi*freq*t + phase)
        jammer[:, 1] = jammer_amp * np.cos(2*np.pi*freq*t + phase)

        return signal + awgn + jammer


class RayleighFadingChannel:
    """
    Rayleigh fading channel for fast-moving targets.

    DEFENSE RELEVANCE:
    Hypersonic vehicles at Mach 5-10 create severe Doppler shifts
    and rapid channel variations. Rayleigh fading models the
    worst-case scenario with no line-of-sight component.

    The 4D POM structure is more robust because fading affects
    different dimensions independently.
    """

    def __init__(self, doppler_spread: float = 0.1, seed: int = None):
        """
        Args:
            doppler_spread: Normalized Doppler spread (0.1 = 10% of symbol rate)
        """
        self.doppler_spread = doppler_spread
        self.rng = np.random.default_rng(seed)

    def add_fading(self, signal: np.ndarray, snr_db: float) -> np.ndarray:
        """Apply Rayleigh fading + AWGN."""
        n_samples, dims = signal.shape

        # Generate Rayleigh fading coefficients per dimension
        # Complex Gaussian -> magnitude is Rayleigh distributed
        fade_real = self.rng.normal(0, 1/np.sqrt(2), (n_samples, dims))
        fade_imag = self.rng.normal(0, 1/np.sqrt(2), (n_samples, dims))
        fade_magnitude = np.sqrt(fade_real**2 + fade_imag**2)

        # Apply low-pass filter to create temporal correlation
        # (simulates coherence time)
        filter_len = max(1, int(1 / self.doppler_spread))
        if filter_len > 1:
            b = np.ones(filter_len) / filter_len
            for d in range(dims):
                fade_magnitude[:, d] = np.convolve(
                    fade_magnitude[:, d], b, mode='same'
                )

        # Apply fading
        faded_signal = signal * fade_magnitude

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        signal_power = np.mean(np.sum(faded_signal**2, axis=1))
        noise_power = signal_power / snr_linear
        noise_std = np.sqrt(noise_power / dims)
        noise = self.rng.normal(0, noise_std, signal.shape)

        return faded_signal + noise


class AtmosphericTurbulenceChannel:
    """
    Atmospheric turbulence for free-space optical (FSO) links.

    COMMERCIAL RELEVANCE:
    FSO links for 6G backhaul and data center interconnects
    suffer from beam wander and scintillation. The turbulence
    causes log-normal intensity fluctuations.

    POM's geometric structure provides redundancy - even if
    some dimensions fade, others may remain strong.
    """

    def __init__(self, scintillation_index: float = 0.5, seed: int = None):
        """
        Args:
            scintillation_index: Rytov variance σ² (0.1=weak, 1.0=strong)
        """
        self.sigma_sq = scintillation_index
        self.rng = np.random.default_rng(seed)

    def add_turbulence(self, signal: np.ndarray, snr_db: float) -> np.ndarray:
        """Apply log-normal fading + AWGN."""
        n_samples, dims = signal.shape

        # Log-normal fading (models irradiance fluctuations)
        # I = exp(2X) where X ~ N(-σ²/2, σ²)
        sigma = np.sqrt(self.sigma_sq)
        X = self.rng.normal(-self.sigma_sq/2, sigma, (n_samples, dims))
        intensity = np.exp(2 * X)

        # Normalize to preserve average power
        intensity = intensity / np.mean(intensity)

        # Apply fading (amplitude = sqrt of intensity)
        faded_signal = signal * np.sqrt(intensity)

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        signal_power = np.mean(np.sum(faded_signal**2, axis=1))
        noise_power = signal_power / snr_linear
        noise_std = np.sqrt(noise_power / dims)
        noise = self.rng.normal(0, noise_std, signal.shape)

        return faded_signal + noise


class PhaseNoiseChannel:
    """
    Phase noise from oscillator imperfections.

    COMMERCIAL RELEVANCE:
    High-frequency 6G/THz communications suffer from oscillator
    phase noise. This causes constellation rotation that
    particularly hurts high-order QAM.

    POM's 4D structure is more robust because phase rotations
    in the 4D space have different geometry than 2D rotations.
    """

    def __init__(self, phase_noise_std: float = 0.1, seed: int = None):
        """
        Args:
            phase_noise_std: Phase noise standard deviation (radians)
        """
        self.phase_std = phase_noise_std
        self.rng = np.random.default_rng(seed)

    def add_phase_noise(self, signal: np.ndarray, snr_db: float) -> np.ndarray:
        """Apply phase noise + AWGN."""
        n_samples, dims = signal.shape

        # Generate random phase rotations
        # For 4D, we apply rotations in the (x,y) and (z,w) planes
        theta_xy = self.rng.normal(0, self.phase_std, n_samples)
        theta_zw = self.rng.normal(0, self.phase_std, n_samples)

        rotated = signal.copy()

        # Rotate in (x,y) plane
        cos_xy = np.cos(theta_xy)
        sin_xy = np.sin(theta_xy)
        new_x = rotated[:, 0] * cos_xy - rotated[:, 1] * sin_xy
        new_y = rotated[:, 0] * sin_xy + rotated[:, 1] * cos_xy
        rotated[:, 0] = new_x
        rotated[:, 1] = new_y

        # Rotate in (z,w) plane for 4D signals
        if dims >= 4:
            cos_zw = np.cos(theta_zw)
            sin_zw = np.sin(theta_zw)
            new_z = rotated[:, 2] * cos_zw - rotated[:, 3] * sin_zw
            new_w = rotated[:, 2] * sin_zw + rotated[:, 3] * cos_zw
            rotated[:, 2] = new_z
            rotated[:, 3] = new_w

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        signal_power = np.mean(np.sum(rotated**2, axis=1))
        noise_power = signal_power / snr_linear
        noise_std = np.sqrt(noise_power / dims)
        noise = self.rng.normal(0, noise_std, signal.shape)

        return rotated + noise


class MultipathChannel:
    """
    Multipath propagation channel.

    RELEVANCE (BOTH):
    - Defense: Reflections from terrain in low-altitude tracking
    - Commercial: Urban/indoor environments with many reflectors

    Multipath causes inter-symbol interference and frequency
    selective fading. POM's geometric structure provides
    natural diversity.
    """

    def __init__(self, num_paths: int = 3, max_delay: int = 5, seed: int = None):
        """
        Args:
            num_paths: Number of multipath components
            max_delay: Maximum delay spread in symbols
        """
        self.num_paths = num_paths
        self.max_delay = max_delay
        self.rng = np.random.default_rng(seed)

    def add_multipath(self, signal: np.ndarray, snr_db: float) -> np.ndarray:
        """Apply multipath + AWGN."""
        n_samples, dims = signal.shape

        # Generate path delays and gains
        delays = self.rng.integers(0, self.max_delay + 1, self.num_paths)
        gains = self.rng.exponential(1.0, self.num_paths)
        gains = gains / np.sum(gains)  # Normalize

        # Apply multipath (sum of delayed copies)
        output = np.zeros_like(signal)
        for delay, gain in zip(delays, gains):
            if delay == 0:
                output += gain * signal
            else:
                output[delay:] += gain * signal[:-delay]

        # Add AWGN
        snr_linear = 10 ** (snr_db / 10)
        signal_power = np.mean(np.sum(output**2, axis=1))
        noise_power = signal_power / snr_linear
        noise_std = np.sqrt(noise_power / dims)
        noise = self.rng.normal(0, noise_std, signal.shape)

        return output + noise


# =============================================================================
# SCENARIO RUNNERS
# =============================================================================

def run_scenario(
    scenario_name: str,
    channel_func,
    num_bits: int,
    snr_range: np.ndarray,
    seed: int = 42
) -> ScenarioResult:
    """
    Run a single scenario for both POM and QAM.

    Args:
        scenario_name: Name of the scenario
        channel_func: Function that takes (signal, snr_db) -> noisy_signal
        num_bits: Number of bits to transmit
        snr_range: Array of SNR values
        seed: Random seed
    """
    np.random.seed(seed)

    # Initialize systems
    pom_const = Polychoron600()
    qam_const = QAM64Constellation()

    pom_mod = POMModulator(pom_const, mode='conservative', use_gray=True)
    pom_demod = POMDemodulator(pom_const, mode='conservative', use_gray=True)

    qam_mod = QAMModulator(qam_const, use_gray=True)
    qam_demod = QAMDemodulator(qam_const, use_gray=True)

    # Generate data
    bits = np.random.randint(0, 2, num_bits)

    # Results storage
    pom_ser = np.zeros(len(snr_range))
    pom_ber = np.zeros(len(snr_range))
    qam_ser = np.zeros(len(snr_range))
    qam_ber = np.zeros(len(snr_range))

    for i, snr_db in enumerate(snr_range):
        # POM
        pom_packet = pom_mod.modulate(bits)
        pom_noisy = channel_func(pom_packet.symbols, snr_db)
        pom_rx_bits, pom_rx_idx, _ = pom_demod.demodulate(pom_noisy)

        pom_ser[i] = np.mean(pom_rx_idx != pom_packet.indices)
        pom_ber[i] = np.mean(pom_rx_bits[:len(bits)] != bits)

        # QAM (embed in 4D for channel, then extract 2D for demod)
        qam_packet = qam_mod.modulate(bits)
        qam_noisy = channel_func(qam_packet.symbols, snr_db)
        qam_rx_bits, qam_rx_idx, _ = qam_demod.demodulate_4d(qam_noisy)

        qam_ser[i] = np.mean(qam_rx_idx != qam_packet.indices)
        qam_ber[i] = np.mean(qam_rx_bits[:len(bits)] != bits)

    return ScenarioResult(
        name=scenario_name,
        description="",
        snr_range=snr_range,
        pom_ser=pom_ser,
        pom_ber=pom_ber,
        qam_ser=qam_ser,
        qam_ber=qam_ber,
        relevance="both"
    )


def run_all_scenarios(num_bits: int = 100000, seed: int = 42) -> Dict[str, ScenarioResult]:
    """Run all scenarios and return results."""

    snr_range = np.arange(0, 26, 2)
    results = {}

    print("=" * 70)
    print("ENHANCED POM SIMULATION - MULTI-SCENARIO COMPARISON")
    print("=" * 70)
    print(f"\nBits per scenario: {num_bits:,}")
    print(f"SNR range: {snr_range[0]} to {snr_range[-1]} dB\n")

    # 1. AWGN Baseline
    print("[1/6] Running AWGN baseline...")
    awgn_channel = AWGNChannel4D(seed=seed)
    results['awgn'] = run_scenario(
        "AWGN (Baseline)",
        lambda s, snr: awgn_channel.add_noise(s, snr)[0],
        num_bits, snr_range, seed
    )
    results['awgn'].description = "Ideal Gaussian noise - theoretical baseline"
    results['awgn'].relevance = "both"

    # 2. Jamming
    print("[2/6] Running Jamming scenario (Defense)...")
    jamming_channel = JammingChannel(jammer_power_ratio=0.3, seed=seed)
    results['jamming'] = run_scenario(
        "Jamming (EW)",
        jamming_channel.add_interference,
        num_bits, snr_range, seed
    )
    results['jamming'].description = "Narrowband interference at 30% signal power"
    results['jamming'].relevance = "defense"

    # 3. Rayleigh Fading
    print("[3/6] Running Rayleigh Fading scenario (Defense)...")
    fading_channel = RayleighFadingChannel(doppler_spread=0.1, seed=seed)
    results['rayleigh'] = run_scenario(
        "Rayleigh Fading",
        fading_channel.add_fading,
        num_bits, snr_range, seed
    )
    results['rayleigh'].description = "Fast fading for hypersonic tracking"
    results['rayleigh'].relevance = "defense"

    # 4. Atmospheric Turbulence
    print("[4/6] Running Atmospheric Turbulence scenario (Commercial)...")
    turbulence_channel = AtmosphericTurbulenceChannel(scintillation_index=0.5, seed=seed)
    results['turbulence'] = run_scenario(
        "FSO Turbulence",
        turbulence_channel.add_turbulence,
        num_bits, snr_range, seed
    )
    results['turbulence'].description = "Moderate turbulence (σ²=0.5) for FSO links"
    results['turbulence'].relevance = "commercial"

    # 5. Phase Noise
    print("[5/6] Running Phase Noise scenario (Commercial)...")
    phase_channel = PhaseNoiseChannel(phase_noise_std=0.15, seed=seed)
    results['phase_noise'] = run_scenario(
        "Phase Noise",
        phase_channel.add_phase_noise,
        num_bits, snr_range, seed
    )
    results['phase_noise'].description = "Oscillator phase noise for 6G/THz"
    results['phase_noise'].relevance = "commercial"

    # 6. Multipath
    print("[6/6] Running Multipath scenario (Both)...")
    multipath_channel = MultipathChannel(num_paths=4, max_delay=3, seed=seed)
    results['multipath'] = run_scenario(
        "Multipath",
        multipath_channel.add_multipath,
        num_bits, snr_range, seed
    )
    results['multipath'].description = "4-path channel with ISI"
    results['multipath'].relevance = "both"

    print("\n✓ All scenarios complete!")

    return results


# =============================================================================
# VISUALIZATION
# =============================================================================

def plot_all_scenarios(results: Dict[str, ScenarioResult], save_path: str = None):
    """Generate comprehensive comparison plots."""

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()

    scenario_order = ['awgn', 'jamming', 'rayleigh', 'turbulence', 'phase_noise', 'multipath']
    colors = {
        'defense': {'pom': 'navy', 'qam': 'darkred'},
        'commercial': {'pom': 'darkgreen', 'qam': 'darkorange'},
        'both': {'pom': 'blue', 'qam': 'red'}
    }

    for idx, key in enumerate(scenario_order):
        ax = axes[idx]
        r = results[key]

        c = colors[r.relevance]

        # Plot SER curves
        pom_ser = np.maximum(r.pom_ser, 1e-6)
        qam_ser = np.maximum(r.qam_ser, 1e-6)

        ax.semilogy(r.snr_range, qam_ser, 's-', color=c['qam'],
                    linewidth=2, markersize=7, label='64-QAM')
        ax.semilogy(r.snr_range, pom_ser, 'o-', color=c['pom'],
                    linewidth=2, markersize=7, label='POM (4D)')

        # Calculate max improvement
        valid_mask = (r.pom_ser > 0) & (r.qam_ser > 0)
        if np.any(valid_mask):
            improvements = r.qam_ser[valid_mask] / r.pom_ser[valid_mask]
            max_imp = np.max(improvements)
            max_idx = np.argmax(improvements)
            snr_at_max = r.snr_range[valid_mask][max_idx]

            if max_imp > 1.5:
                ax.annotate(f'{max_imp:.0f}x better',
                           xy=(snr_at_max, pom_ser[r.snr_range == snr_at_max][0] if snr_at_max in r.snr_range else pom_ser[max_idx]),
                           fontsize=9, color=c['pom'], fontweight='bold')

        ax.set_xlabel('SNR (dB)', fontsize=11)
        ax.set_ylabel('Symbol Error Rate', fontsize=11)
        ax.set_title(f'{r.name}\n({r.relevance.upper()})', fontsize=12, fontweight='bold')
        ax.legend(loc='lower left', fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_ylim([1e-5, 1])
        ax.set_xlim([r.snr_range[0]-1, r.snr_range[-1]+1])

        # Add description
        ax.text(0.98, 0.02, r.description, transform=ax.transAxes,
                fontsize=8, ha='right', va='bottom', style='italic',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.suptitle('POM vs QAM: Multi-Scenario Real-World Comparison\n'
                 'Defense (Navy/Red) | Commercial (Green/Orange) | Both (Blue/Red)',
                 fontsize=14, fontweight='bold', y=1.02)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"✓ Saved: {save_path}")

    plt.show()


def plot_improvement_heatmap(results: Dict[str, ScenarioResult], save_path: str = None):
    """Generate heatmap showing improvement factor across scenarios and SNRs."""

    scenario_order = ['awgn', 'jamming', 'rayleigh', 'turbulence', 'phase_noise', 'multipath']
    scenario_names = [results[k].name for k in scenario_order]

    snr_range = results['awgn'].snr_range

    # Build improvement matrix
    improvement_matrix = np.zeros((len(scenario_order), len(snr_range)))

    for i, key in enumerate(scenario_order):
        r = results[key]
        with np.errstate(divide='ignore', invalid='ignore'):
            improvement = np.where(
                (r.pom_ser > 0) & (r.qam_ser > 0),
                r.qam_ser / r.pom_ser,
                1.0
            )
        improvement_matrix[i, :] = improvement

    # Cap for visualization
    improvement_matrix = np.clip(improvement_matrix, 1, 1000)

    fig, ax = plt.subplots(figsize=(14, 6))

    # Log scale for better visualization
    im = ax.imshow(np.log10(improvement_matrix), aspect='auto', cmap='RdYlGn',
                   vmin=0, vmax=3)

    ax.set_xticks(range(len(snr_range)))
    ax.set_xticklabels([f'{s:.0f}' for s in snr_range])
    ax.set_yticks(range(len(scenario_names)))
    ax.set_yticklabels(scenario_names)

    ax.set_xlabel('SNR (dB)', fontsize=12)
    ax.set_ylabel('Scenario', fontsize=12)
    ax.set_title('POM Improvement Factor Over QAM\n(Green = POM Better, Red = Similar)',
                 fontsize=14, fontweight='bold')

    # Add text annotations
    for i in range(len(scenario_order)):
        for j in range(len(snr_range)):
            val = improvement_matrix[i, j]
            if val >= 100:
                text = f'{val:.0f}x'
            elif val >= 10:
                text = f'{val:.0f}x'
            elif val >= 2:
                text = f'{val:.1f}x'
            else:
                text = f'{val:.1f}x'
            ax.text(j, i, text, ha='center', va='center', fontsize=7,
                   color='white' if val > 10 else 'black')

    # Colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Improvement Factor (log scale)', fontsize=11)
    cbar.set_ticks([0, 1, 2, 3])
    cbar.set_ticklabels(['1x', '10x', '100x', '1000x'])

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"✓ Saved: {save_path}")

    plt.show()


def print_summary_table(results: Dict[str, ScenarioResult]):
    """Print a summary table of improvements."""

    print("\n" + "=" * 80)
    print("IMPROVEMENT SUMMARY (POM vs QAM)")
    print("=" * 80)

    print(f"\n{'Scenario':<25} {'Relevance':<12} {'@10dB':<10} {'@15dB':<10} {'@20dB':<10}")
    print("-" * 67)

    for key in ['awgn', 'jamming', 'rayleigh', 'turbulence', 'phase_noise', 'multipath']:
        r = results[key]

        improvements = []
        for target_snr in [10, 15, 20]:
            idx = np.argmin(np.abs(r.snr_range - target_snr))
            if r.pom_ser[idx] > 0:
                imp = r.qam_ser[idx] / r.pom_ser[idx]
                improvements.append(f'{imp:.1f}x')
            else:
                improvements.append('∞')

        print(f"{r.name:<25} {r.relevance:<12} {improvements[0]:<10} {improvements[1]:<10} {improvements[2]:<10}")

    print("\n" + "=" * 80)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the enhanced multi-scenario simulation."""

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bits', type=int, default=100000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--no-plot', action='store_true')
    args = parser.parse_args()

    # Run all scenarios
    results = run_all_scenarios(num_bits=args.bits, seed=args.seed)

    # Print summary
    print_summary_table(results)

    # Generate plots
    if not args.no_plot:
        try:
            import matplotlib
            matplotlib.use('Agg')

            plot_all_scenarios(results, save_path='multi_scenario_comparison.png')
            plot_improvement_heatmap(results, save_path='improvement_heatmap.png')

        except Exception as e:
            print(f"Note: Could not generate plots ({e})")

    return results


if __name__ == "__main__":
    results = main()
