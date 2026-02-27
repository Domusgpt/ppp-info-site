#!/usr/bin/env python3
"""
Fractal Constellation Benchmark

Compares:
1. Standard 600-cell (fixed rate)
2. Fractal Level 1 (24×5 = 120 symbols, graceful degradation)
3. Fractal Level 2 (24×5×5 = 600 symbols, higher capacity)

Key metrics:
- BER vs SNR for each configuration
- Effective throughput with graceful degradation
- LPI security comparison

Copyright (c) 2025-2026 Clear Seas Solutions LLC
"""

import numpy as np
import sys

try:
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
except ImportError:
    print("matplotlib required: pip install matplotlib")
    sys.exit(1)

from cspm.lattice import PolychoralConstellation
from cspm.fractal_constellation import FractalConstellation, FractalCSPM


def benchmark_fixed_rate(snr_range: np.ndarray, n_symbols: int = 2000):
    """Benchmark 600-cell at fixed rate."""
    bers = []

    for snr_db in snr_range:
        tx = PolychoralConstellation(seed=b"BENCH_TX")
        rx = PolychoralConstellation(seed=b"BENCH_TX")

        snr_linear = 10 ** (snr_db / 10)
        noise_std = 1.0 / np.sqrt(2 * snr_linear)

        errors = 0
        np.random.seed(42)

        for i in range(n_symbols):
            symbol = np.random.randint(0, 120)
            encoded = tx.encode_symbol(symbol)

            noise = np.random.randn(4) * noise_std
            received = encoded + noise
            received = received / np.linalg.norm(received)

            decoded, _ = rx.decode_symbol(received)
            if decoded != symbol:
                errors += 1

            if (i + 1) % 100 == 0:
                tx.rotate_lattice(f"p{i}".encode())
                rx.rotate_lattice(f"p{i}".encode())

        bers.append(errors / n_symbols)

    return np.array(bers)


def benchmark_fractal_fixed(snr_range: np.ndarray, max_level: int = 1,
                           n_symbols: int = 2000):
    """Benchmark fractal constellation at fixed decoding level."""
    bers = []
    fc = FractalConstellation(max_level=max_level, seed=b"BENCH_FRACTAL")
    n_syms = fc.n_symbols

    for snr_db in snr_range:
        fc = FractalConstellation(max_level=max_level, seed=b"BENCH_FRACTAL")

        snr_linear = 10 ** (snr_db / 10)
        noise_std = 1.0 / np.sqrt(2 * snr_linear)

        errors = 0
        np.random.seed(42)

        for i in range(n_symbols):
            symbol = np.random.randint(0, n_syms)
            encoded = fc.encode(symbol)

            noise = np.random.randn(4) * noise_std
            received = encoded + noise
            received = received / np.linalg.norm(received)

            path, dist, confs = fc.decode(received)
            decoded = fc.path_to_symbol(path)

            if decoded != symbol:
                errors += 1

            if (i + 1) % 100 == 0:
                fc.rotate_all(f"p{i}".encode())

        bers.append(errors / n_symbols)

    return np.array(bers)


def benchmark_fractal_adaptive(snr_range: np.ndarray, max_level: int = 2,
                               n_symbols: int = 2000):
    """
    Benchmark fractal with adaptive decoding.

    Returns (bers, effective_bits) where effective_bits varies with SNR.
    """
    bers = []
    effective_bits = []
    fc = FractalConstellation(max_level=max_level, seed=b"BENCH_ADAPTIVE")
    bits_per_level = fc.bits_per_level

    for snr_db in snr_range:
        fc = FractalConstellation(max_level=max_level, seed=b"BENCH_ADAPTIVE")

        snr_linear = 10 ** (snr_db / 10)
        noise_std = 1.0 / np.sqrt(2 * snr_linear)

        level_counts = [0] * (max_level + 1)
        errors = 0
        np.random.seed(42)

        # Adaptive threshold based on SNR
        confidence_threshold = 0.3 / (1 + snr_db / 15)

        for i in range(n_symbols):
            symbol = np.random.randint(0, fc.n_symbols)
            true_path = fc.symbol_to_path(symbol)
            encoded = fc.encode(symbol)

            noise = np.random.randn(4) * noise_std
            received = encoded + noise
            received = received / np.linalg.norm(received)

            # Adaptive decoding
            decoded_path, decoded_level = fc.decode_adaptive(
                received, confidence_threshold)

            level_counts[decoded_level] += 1

            # Check if decoded path matches true path up to decoded level
            if decoded_path != true_path[:len(decoded_path)]:
                errors += 1

            if (i + 1) % 100 == 0:
                fc.rotate_all(f"p{i}".encode())

        bers.append(errors / n_symbols)

        # Compute average bits based on level distribution
        avg_bits = 0
        for lvl, count in enumerate(level_counts):
            avg_bits += sum(bits_per_level[:lvl+1]) * count
        avg_bits /= n_symbols
        effective_bits.append(avg_bits)

    return np.array(bers), np.array(effective_bits)


def benchmark_lpi_fractal(snr_range: np.ndarray, n_symbols: int = 1000):
    """
    Benchmark LPI security with fractal constellation.

    Test: attacker doesn't know which LEVEL rotated.
    """
    legit_bers = []
    attack_bers = []

    for snr_db in snr_range:
        tx = FractalConstellation(max_level=1, seed=b"LPI_TX")
        rx_legit = FractalConstellation(max_level=1, seed=b"LPI_TX")
        rx_attack = FractalConstellation(max_level=1, seed=b"WRONG")

        snr_linear = 10 ** (snr_db / 10)
        noise_std = 1.0 / np.sqrt(2 * snr_linear)

        legit_errors = 0
        attack_errors = 0
        np.random.seed(42)

        for i in range(n_symbols):
            symbol = np.random.randint(0, tx.n_symbols)
            encoded = tx.encode(symbol)

            noise = np.random.randn(4) * noise_std
            received = encoded + noise
            received = received / np.linalg.norm(received)

            path_l, _, _ = rx_legit.decode(received)
            path_a, _, _ = rx_attack.decode(received)

            dec_l = rx_legit.path_to_symbol(path_l)
            dec_a = rx_attack.path_to_symbol(path_a)

            if dec_l != symbol:
                legit_errors += 1
            if dec_a != symbol:
                attack_errors += 1

            if (i + 1) % 50 == 0:
                # Rotate different levels independently!
                tx.rotate_level(0, f"L0_{i}".encode())
                tx.rotate_level(1, f"L1_{i}".encode())
                rx_legit.rotate_level(0, f"L0_{i}".encode())
                rx_legit.rotate_level(1, f"L1_{i}".encode())
                # Attacker rotates wrong (or not at all)
                rx_attack.rotate_all(f"wrong_{i}".encode())

        legit_bers.append(legit_errors / n_symbols)
        attack_bers.append(attack_errors / n_symbols)

    return np.array(legit_bers), np.array(attack_bers)


def create_benchmark_plots():
    """Generate all benchmark plots."""
    print("=" * 70)
    print("FRACTAL CONSTELLATION BENCHMARK")
    print("=" * 70)

    fig = plt.figure(figsize=(16, 12))
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)

    snr_range = np.arange(5, 30, 2)

    # =========================================================================
    # PLOT 1: BER Comparison - 600-cell vs Fractal
    # =========================================================================
    print("\n[1/4] Comparing 600-cell vs Fractal L1...")

    ber_600 = benchmark_fixed_rate(snr_range, n_symbols=1500)
    ber_frac1 = benchmark_fractal_fixed(snr_range, max_level=1, n_symbols=1500)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.semilogy(snr_range, ber_600, 'b-o', label='600-cell (6.9 bits)', linewidth=2)
    ax1.semilogy(snr_range, ber_frac1, 'r-s', label='Fractal L1 (6.9 bits)', linewidth=2)
    ax1.axhline(y=0.5, color='gray', linestyle=':', alpha=0.5)

    ax1.set_xlabel('SNR (dB)', fontsize=12)
    ax1.set_ylabel('Symbol Error Rate', fontsize=12)
    ax1.set_title('BER Comparison: Same Rate\n(600-cell vs Fractal Level 1)', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim([1e-3, 1.0])

    # =========================================================================
    # PLOT 2: Adaptive Rate - Graceful Degradation
    # =========================================================================
    print("[2/4] Testing graceful degradation...")

    ber_adapt, bits_adapt = benchmark_fractal_adaptive(snr_range, max_level=2,
                                                        n_symbols=1500)

    ax2 = fig.add_subplot(gs[0, 1])
    ax2_bits = ax2.twinx()

    line1, = ax2.semilogy(snr_range, ber_adapt, 'b-o', label='SER', linewidth=2)
    line2, = ax2_bits.plot(snr_range, bits_adapt, 'g-s', label='Effective bits', linewidth=2)

    ax2.set_xlabel('SNR (dB)', fontsize=12)
    ax2.set_ylabel('Symbol Error Rate', fontsize=12, color='blue')
    ax2_bits.set_ylabel('Effective bits/symbol', fontsize=12, color='green')
    ax2.set_title('Adaptive Fractal L2: Graceful Degradation\n(Rate adapts to channel)', fontsize=12)

    ax2.tick_params(axis='y', labelcolor='blue')
    ax2_bits.tick_params(axis='y', labelcolor='green')
    ax2_bits.set_ylim([4, 10])

    # Combined legend
    ax2.legend([line1, line2], ['SER', 'Effective bits/sym'], loc='center right')
    ax2.grid(True, alpha=0.3)

    # =========================================================================
    # PLOT 3: LPI Security with Independent Level Rotation
    # =========================================================================
    print("[3/4] Testing LPI with level-independent rotation...")

    legit_ber, attack_ber = benchmark_lpi_fractal(snr_range, n_symbols=1000)

    ax3 = fig.add_subplot(gs[1, 0])
    ax3.semilogy(snr_range, legit_ber, 'b-o', label='Legitimate RX', linewidth=2)
    ax3.semilogy(snr_range, attack_ber, 'r-x', label='Attacker RX', linewidth=2)
    ax3.axhline(y=119/120, color='gray', linestyle=':', label='Random guess')

    ax3.set_xlabel('SNR (dB)', fontsize=12)
    ax3.set_ylabel('Symbol Error Rate', fontsize=12)
    ax3.set_title('Fractal LPI: Independent Level Rotation\n(2 hash chains, not 1)', fontsize=12)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim([1e-2, 1.5])

    # =========================================================================
    # PLOT 4: Capacity Comparison
    # =========================================================================
    print("[4/4] Computing capacity comparison...")

    ax4 = fig.add_subplot(gs[1, 1])

    configs = [
        ('600-cell\n(standard)', 120, 6.91, 1),
        ('Fractal L1\n(24×5)', 120, 6.91, 2),
        ('Fractal L2\n(24×5×5)', 600, 9.23, 3),
        ('Fractal L3\n(24×5×5×5)', 3000, 11.55, 4),
    ]

    names = [c[0] for c in configs]
    symbols = [c[1] for c in configs]
    bits = [c[2] for c in configs]
    levels = [c[3] for c in configs]

    colors = ['steelblue', 'coral', 'forestgreen', 'purple']
    bars = ax4.bar(names, bits, color=colors, edgecolor='black', linewidth=2)

    # Add symbol count labels
    for bar, sym, b in zip(bars, symbols, bits):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                f'{sym} sym\n{b:.2f} bits', ha='center', va='bottom', fontsize=10)

    ax4.set_ylabel('Bits per Symbol', fontsize=12)
    ax4.set_title('Fractal Capacity Scaling\n(Each level adds ~2.3 bits)', fontsize=12)
    ax4.set_ylim([0, 14])

    # Add note about graceful degradation
    ax4.text(0.5, 0.95,
            "L2+ degrade gracefully:\nHigh noise → L0 only (4.6 bits)\nLow noise → Full rate",
            transform=ax4.transAxes, fontsize=9, ha='center', va='top',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    plt.savefig('fractal_benchmark.png', dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved: fractal_benchmark.png")

    # =========================================================================
    # Print numerical summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("NUMERICAL RESULTS")
    print("=" * 70)

    print("\nBER @ 15dB:")
    idx = np.argmin(np.abs(snr_range - 15))
    print(f"  600-cell:    {ber_600[idx]*100:.1f}%")
    print(f"  Fractal L1:  {ber_frac1[idx]*100:.1f}%")
    print(f"  Fractal L2 (adaptive): {ber_adapt[idx]*100:.1f}% @ {bits_adapt[idx]:.1f} bits/sym")

    print("\nBER @ 20dB:")
    idx = np.argmin(np.abs(snr_range - 20))
    print(f"  600-cell:    {ber_600[idx]*100:.1f}%")
    print(f"  Fractal L1:  {ber_frac1[idx]*100:.1f}%")
    print(f"  Fractal L2 (adaptive): {ber_adapt[idx]*100:.1f}% @ {bits_adapt[idx]:.1f} bits/sym")

    print("\nLPI Security @ 15dB (Fractal):")
    idx = np.argmin(np.abs(snr_range - 15))
    print(f"  Legitimate: {legit_ber[idx]*100:.1f}%")
    print(f"  Attacker:   {attack_ber[idx]*100:.1f}%")

    print("\nCapacity Scaling:")
    for name, sym, b, _ in configs:
        print(f"  {name.replace(chr(10), ' ')}: {sym} symbols = {b:.2f} bits")

    print("\n" + "=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)
    print("""
1. SAME RATE, ADDED FEATURES:
   Fractal L1 = 600-cell in capacity, but with:
   - Graceful degradation
   - Independent per-level rotation (more LPI dimensions)
   - Hierarchical structure for adaptive systems

2. HIGHER CAPACITY:
   Fractal L2 achieves 600 symbols (9.23 bits) - 5× the 600-cell
   Fractal L3 achieves 3000 symbols (11.55 bits) - 25× the 600-cell

3. GRACEFUL DEGRADATION:
   Under noise, automatically falls back to coarse level
   Still delivers ~4.6 bits when fine levels fail

4. MULTI-LEVEL LPI:
   Each level can rotate independently
   Attacker must track N hash chains, not just 1
   More degrees of freedom for security

5. SATELLITE APPLICATION:
   Varying link margin → adaptive rate
   Same modulation hardware, variable throughput
   No mode switching needed
""")


if __name__ == "__main__":
    np.random.seed(42)
    create_benchmark_plots()
