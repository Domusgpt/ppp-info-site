#!/usr/bin/env python3
"""
=============================================================================
COMPREHENSIVE POLYTOPE BENCHMARK
=============================================================================

This script tests all 4D polytopes against all realistic channel models
to provide an honest, thorough comparison.

WHAT THIS TESTS:
- All regular polychora (5-cell, 8-cell, 16-cell, 24-cell, 600-cell)
- Semi-regular polytopes (rectified, snub)
- Lattice-based structures (D4, E8)
- QAM baselines (16, 64, 256)

ACROSS CHANNELS:
- AWGN (baseline)
- Rayleigh/Rician/Nakagami fading
- Atmospheric turbulence + OAM crosstalk
- Hardware impairments (phase noise, IQ imbalance, PA, ADC)
- Doppler and timing jitter
- Jamming and impulse noise
- Composite realistic scenarios

Author: PPP Research Team
License: MIT
=============================================================================
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import sys
import time

# Local imports
from polytopes import (
    Polytope4D, Pentachoron, Tesseract, Hexadecachoron,
    Icositetrachoron, Hexacosichoron, RectifiedTesseract,
    Snub24Cell, D4Lattice, E8Projection, QAM, get_all_polytopes
)
from realistic_channels import (
    ChannelModel, AWGNChannel, RayleighFadingChannel, RicianFadingChannel,
    NakagamiFadingChannel, AtmosphericTurbulenceChannel, OAMCrosstalkChannel,
    PhaseNoiseChannel, IQImbalanceChannel, NonlinearPAChannel,
    QuantizationChannel, DopplerChannel, TimingJitterChannel,
    JammingChannel, ImpulseNoiseChannel, CompositeChannel,
    get_defense_scenario, get_fso_scenario, get_urban_mobile_scenario,
    get_all_channels
)


# =============================================================================
# BENCHMARK CONFIGURATION
# =============================================================================

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    num_symbols: int = 50000
    snr_range: List[float] = None
    random_seed: int = 42

    def __post_init__(self):
        if self.snr_range is None:
            self.snr_range = [5, 10, 15, 20, 25]


@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""
    polytope_name: str
    channel_name: str
    snr_db: float
    num_symbols: int
    num_errors: int
    ser: float
    ber: float
    elapsed_time: float


# =============================================================================
# BENCHMARK FUNCTIONS
# =============================================================================

def run_single_test(
    polytope: Polytope4D,
    channel: ChannelModel,
    snr_db: float,
    num_symbols: int
) -> BenchmarkResult:
    """
    Run a single modulation/channel/demodulation test.

    Returns:
        BenchmarkResult with error statistics
    """
    start_time = time.time()

    n_vertices = polytope.num_vertices
    bits_per_symbol = int(np.floor(np.log2(n_vertices)))
    usable_vertices = 2 ** bits_per_symbol

    # Generate random symbol indices
    tx_indices = np.random.randint(0, usable_vertices, num_symbols)

    # Modulate
    tx_symbols = polytope.vertices[tx_indices]

    # Apply channel
    rx_symbols, channel_state = channel.apply(tx_symbols, snr_db)

    # Demodulate
    rx_indices, distances = polytope.batch_nearest(rx_symbols)
    rx_indices = rx_indices % usable_vertices  # Wrap to usable range

    # Calculate errors
    symbol_errors = np.sum(tx_indices != rx_indices)
    ser = symbol_errors / num_symbols

    # Approximate BER (assuming Gray coding, ~1 bit error per symbol error)
    bit_errors = symbol_errors
    bits_transmitted = num_symbols * bits_per_symbol
    ber = bit_errors / bits_transmitted if bits_transmitted > 0 else 0

    elapsed = time.time() - start_time

    return BenchmarkResult(
        polytope_name=polytope.name,
        channel_name=channel.get_name(),
        snr_db=snr_db,
        num_symbols=num_symbols,
        num_errors=symbol_errors,
        ser=ser,
        ber=ber,
        elapsed_time=elapsed
    )


def run_benchmark(
    polytopes: Dict[str, Polytope4D],
    channels: Dict[str, ChannelModel],
    config: BenchmarkConfig
) -> List[BenchmarkResult]:
    """
    Run full benchmark across all polytopes and channels.

    Returns:
        List of BenchmarkResult objects
    """
    np.random.seed(config.random_seed)
    results = []

    total_tests = len(polytopes) * len(channels) * len(config.snr_range)
    current_test = 0

    print(f"\nRunning {total_tests} benchmark tests...")
    print("-" * 70)

    for poly_name, polytope in polytopes.items():
        for channel_name, channel in channels.items():
            for snr_db in config.snr_range:
                current_test += 1

                result = run_single_test(
                    polytope, channel, snr_db, config.num_symbols
                )
                results.append(result)

                # Progress update
                if current_test % 20 == 0 or current_test == total_tests:
                    print(f"  Progress: {current_test}/{total_tests} "
                          f"({100*current_test/total_tests:.1f}%)")

    return results


def analyze_results(results: List[BenchmarkResult]) -> Dict:
    """
    Analyze benchmark results.

    Returns summary statistics and rankings.
    """
    # Group by polytope and channel
    by_polytope = {}
    by_channel = {}
    by_snr = {}

    for r in results:
        # By polytope
        if r.polytope_name not in by_polytope:
            by_polytope[r.polytope_name] = []
        by_polytope[r.polytope_name].append(r)

        # By channel
        if r.channel_name not in by_channel:
            by_channel[r.channel_name] = []
        by_channel[r.channel_name].append(r)

        # By SNR
        if r.snr_db not in by_snr:
            by_snr[r.snr_db] = []
        by_snr[r.snr_db].append(r)

    # Compute average SER per polytope
    polytope_avg_ser = {}
    for name, res_list in by_polytope.items():
        avg_ser = np.mean([r.ser for r in res_list])
        polytope_avg_ser[name] = avg_ser

    # Rank polytopes by average SER
    ranked = sorted(polytope_avg_ser.items(), key=lambda x: x[1])

    return {
        'by_polytope': by_polytope,
        'by_channel': by_channel,
        'by_snr': by_snr,
        'polytope_avg_ser': polytope_avg_ser,
        'ranking': ranked
    }


def print_summary_table(results: List[BenchmarkResult], analysis: Dict):
    """Print summary results table."""
    print("\n" + "=" * 90)
    print("COMPREHENSIVE BENCHMARK SUMMARY")
    print("=" * 90)

    # Get unique values
    polytopes = sorted(set(r.polytope_name for r in results))
    channels = sorted(set(r.channel_name for r in results))
    snrs = sorted(set(r.snr_db for r in results))

    # Print polytope rankings
    print("\n1. POLYTOPE RANKING (by average SER across all channels):")
    print("-" * 60)
    print(f"{'Rank':<6} {'Polytope':<35} {'Avg SER':>12}")
    print("-" * 60)

    for rank, (name, avg_ser) in enumerate(analysis['ranking'], 1):
        print(f"{rank:<6} {name:<35} {avg_ser:>12.6f}")

    print("-" * 60)

    # Print channel comparison for best polytopes
    print("\n2. CHANNEL COMPARISON (Top 5 Polytopes at SNR=20dB):")
    print("-" * 90)

    top_5 = [name for name, _ in analysis['ranking'][:5]]

    # Header
    header = f"{'Channel':<40}"
    for poly_name in top_5:
        short_name = poly_name[:12] + ".." if len(poly_name) > 14 else poly_name
        header += f" {short_name:>14}"
    print(header)
    print("-" * 90)

    # Data rows
    for channel_name in channels:
        row = f"{channel_name:<40}"
        for poly_name in top_5:
            # Find result for this combo at SNR=20
            matching = [r for r in results
                       if r.polytope_name == poly_name
                       and r.channel_name == channel_name
                       and r.snr_db == 20.0]
            if matching:
                ser = matching[0].ser
                row += f" {ser:>14.6f}"
            else:
                row += f" {'N/A':>14}"
        print(row)

    print("-" * 90)

    # Print SNR sensitivity
    print("\n3. SNR SENSITIVITY (600-Cell vs 64-QAM):")
    print("-" * 60)
    print(f"{'SNR (dB)':<12} {'600-Cell SER':>15} {'64-QAM SER':>15} {'Improvement':>15}")
    print("-" * 60)

    for snr in snrs:
        # Find AWGN results
        cell_600 = [r for r in results
                   if '600-Cell' in r.polytope_name
                   and 'AWGN' in r.channel_name
                   and r.snr_db == snr]
        qam_64 = [r for r in results
                 if '64-QAM' in r.polytope_name
                 and 'AWGN' in r.channel_name
                 and r.snr_db == snr]

        if cell_600 and qam_64:
            ser_600 = cell_600[0].ser
            ser_qam = qam_64[0].ser
            if ser_600 > 0:
                improvement = ser_qam / ser_600
            else:
                improvement = float('inf')
            print(f"{snr:<12.0f} {ser_600:>15.6f} {ser_qam:>15.6f} {improvement:>14.1f}x")

    print("-" * 60)


def print_detailed_results(results: List[BenchmarkResult]):
    """Print detailed results for each channel type."""
    print("\n" + "=" * 90)
    print("DETAILED RESULTS BY CHANNEL TYPE")
    print("=" * 90)

    channels = sorted(set(r.channel_name for r in results))

    for channel_name in channels:
        print(f"\n{'='*70}")
        print(f"Channel: {channel_name}")
        print(f"{'='*70}")

        channel_results = [r for r in results if r.channel_name == channel_name]

        # Group by SNR
        snrs = sorted(set(r.snr_db for r in channel_results))

        for snr in snrs:
            print(f"\n  SNR = {snr} dB:")
            snr_results = [r for r in channel_results if r.snr_db == snr]
            snr_results.sort(key=lambda x: x.ser)

            for r in snr_results[:5]:  # Top 5 only
                print(f"    {r.polytope_name:<35} SER={r.ser:.6f}")


def run_quick_benchmark():
    """Run a quick benchmark with reduced parameters."""
    print("=" * 70)
    print("QUICK BENCHMARK (reduced parameters for speed)")
    print("=" * 70)

    config = BenchmarkConfig(
        num_symbols=10000,
        snr_range=[10, 15, 20],
        random_seed=42
    )

    # Select key polytopes
    polytopes = {
        '16-cell': Hexadecachoron(),
        '24-cell': Icositetrachoron(),
        '600-cell': Hexacosichoron(),
        '64-qam': QAM(64),
    }

    # Select key channels
    channels = {
        'awgn': AWGNChannel(4),
        'rayleigh': RayleighFadingChannel(4),
        'turbulence': AtmosphericTurbulenceChannel(0.5, 4),
        'jamming': JammingChannel(10.0, 'broadband', 4),
    }

    results = run_benchmark(polytopes, channels, config)
    analysis = analyze_results(results)
    print_summary_table(results, analysis)

    return results, analysis


def run_full_benchmark():
    """Run full comprehensive benchmark."""
    print("=" * 70)
    print("FULL COMPREHENSIVE BENCHMARK")
    print("=" * 70)

    config = BenchmarkConfig(
        num_symbols=50000,
        snr_range=[5, 10, 15, 20, 25],
        random_seed=42
    )

    # All polytopes
    polytopes = {
        '5-cell': Pentachoron(),
        '8-cell': Tesseract(),
        '16-cell': Hexadecachoron(),
        '24-cell': Icositetrachoron(),
        '600-cell': Hexacosichoron(),
        'rect-tesseract': RectifiedTesseract(),
        'snub-24': Snub24Cell(),
        'd4-lattice': D4Lattice(radius=2),
        'e8-proj': E8Projection('standard'),
        '16-qam': QAM(16),
        '64-qam': QAM(64),
        '256-qam': QAM(256),
    }

    # Key channels
    channels = {
        'awgn': AWGNChannel(4),
        'rayleigh': RayleighFadingChannel(4),
        'rician-10': RicianFadingChannel(10.0, 4),
        'nakagami-2': NakagamiFadingChannel(2.0, 4),
        'turbulence': AtmosphericTurbulenceChannel(0.5, 4),
        'oam-xt': OAMCrosstalkChannel(10, 0.15, 4),
        'phase-noise': PhaseNoiseChannel(0.02, 4),
        'iq-imbal': IQImbalanceChannel(1.5, 7.0, 4),
        'jamming': JammingChannel(10.0, 'broadband', 4),
        'impulse': ImpulseNoiseChannel(0.02, 8.0, 4),
        'defense': get_defense_scenario(),
        'fso': get_fso_scenario(),
        'urban': get_urban_mobile_scenario(),
    }

    results = run_benchmark(polytopes, channels, config)
    analysis = analyze_results(results)
    print_summary_table(results, analysis)
    print_detailed_results(results)

    return results, analysis


def generate_latex_table(results: List[BenchmarkResult], analysis: Dict) -> str:
    """Generate LaTeX table for publication."""
    latex = []
    latex.append("\\begin{table}[htbp]")
    latex.append("\\centering")
    latex.append("\\caption{Symbol Error Rate Comparison at SNR=20dB}")
    latex.append("\\label{tab:ser_comparison}")
    latex.append("\\begin{tabular}{lcccc}")
    latex.append("\\hline")
    latex.append("Modulation & AWGN & Rayleigh & Turbulence & Jamming \\\\")
    latex.append("\\hline")

    polytopes = ['24-cell', '600-cell', '64-qam', '256-qam']
    channels = ['awgn', 'rayleigh', 'turbulence', 'jamming']

    for poly_name in polytopes:
        row = poly_name.replace('-', ' ').title()
        for ch_name in channels:
            matching = [r for r in results
                       if poly_name in r.polytope_name.lower()
                       and ch_name in r.channel_name.lower()
                       and r.snr_db == 20.0]
            if matching:
                ser = matching[0].ser
                if ser < 0.0001:
                    row += f" & $<10^{{-4}}$"
                else:
                    row += f" & {ser:.4f}"
            else:
                row += " & --"
        row += " \\\\"
        latex.append(row)

    latex.append("\\hline")
    latex.append("\\end{tabular}")
    latex.append("\\end{table}")

    return "\n".join(latex)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("4D Polytope Comprehensive Benchmark")
    print("=" * 70)

    if len(sys.argv) > 1 and sys.argv[1] == '--full':
        results, analysis = run_full_benchmark()
    else:
        results, analysis = run_quick_benchmark()

    # Generate LaTeX table
    print("\n" + "=" * 70)
    print("LATEX TABLE FOR PUBLICATION:")
    print("=" * 70)
    latex = generate_latex_table(results, analysis)
    print(latex)

    print("\n✓ Benchmark complete!")
