#!/usr/bin/env python3
"""
Networked CSPM Architecture Analysis

Evaluating what makes sense for a practical system with:
- LEO + GEO satellite constellation
- Legacy signal processing compatibility
- Graceful upgrade path
- Mixed secure/commercial traffic

This analysis compares architectures and recommends a practical approach.

Copyright (c) 2025-2026 Clear Seas Solutions LLC
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum


class ModulationMode(Enum):
    """Available modulation modes in the system."""
    LEGACY_QPSK = "legacy_qpsk"          # 2 bits/sym, most robust
    LEGACY_16QAM = "legacy_16qam"        # 4 bits/sym
    LEGACY_64QAM = "legacy_64qam"        # 6 bits/sym
    LEGACY_256QAM = "legacy_256qam"      # 8 bits/sym

    CSPM_COARSE = "cspm_coarse"          # 4.6 bits/sym (level 0 only)
    CSPM_STANDARD = "cspm_standard"      # 6.9 bits/sym (600-cell or fractal L1)
    CSPM_HIGH = "cspm_high"              # 9.2 bits/sym (fractal L2)

    HYBRID_BASE = "hybrid_base"          # Legacy base + CSPM enhancement


@dataclass
class LinkBudget:
    """Simplified link budget for analysis."""
    frequency_ghz: float
    tx_power_dbw: float
    tx_gain_dbi: float
    path_loss_db: float
    rx_gain_dbi: float
    noise_figure_db: float
    bandwidth_mhz: float

    @property
    def snr_db(self) -> float:
        """Estimated SNR at receiver."""
        # Simplified: P_rx - N
        p_rx = self.tx_power_dbw + self.tx_gain_dbi - self.path_loss_db + self.rx_gain_dbi
        # Noise power: kTB + NF
        k_db = -228.6  # Boltzmann constant in dBW/K/Hz
        t_db = 10 * np.log10(290)  # 290K reference
        b_db = 10 * np.log10(self.bandwidth_mhz * 1e6)
        n_db = k_db + t_db + b_db + self.noise_figure_db
        return p_rx - n_db


@dataclass
class NodeCapability:
    """What a network node can do."""
    node_id: str
    supports_legacy: bool = True
    supports_cspm: bool = False
    supports_fractal: bool = False
    max_cspm_level: int = 0
    has_position_estimation: bool = False
    has_multi_tx_sync: bool = False


# =============================================================================
# ARCHITECTURE OPTIONS ANALYSIS
# =============================================================================

def analyze_architectures():
    """Compare different system architectures."""

    print("=" * 78)
    print("NETWORKED CSPM ARCHITECTURE ANALYSIS")
    print("=" * 78)

    # -------------------------------------------------------------------------
    # Architecture A: Pure CSPM (no legacy)
    # -------------------------------------------------------------------------
    arch_a = {
        "name": "Pure CSPM",
        "description": "Full 4D encoding, no backward compatibility",
        "pros": [
            "Maximum LPI security",
            "Full geometric benefits",
            "Simplest protocol (one mode)",
            "Best position estimation",
        ],
        "cons": [
            "Zero legacy compatibility",
            "Requires full infrastructure replacement",
            "High deployment barrier",
            "No graceful migration path",
        ],
        "best_for": "Greenfield military/secure networks",
        "complexity": "Low (single mode)",
        "deployment_risk": "High",
    }

    # -------------------------------------------------------------------------
    # Architecture B: Parallel Modes (switch between)
    # -------------------------------------------------------------------------
    arch_b = {
        "name": "Parallel Modes",
        "description": "Switch between legacy QAM and CSPM based on capability",
        "pros": [
            "Full legacy compatibility",
            "Full CSPM when available",
            "Clear separation of concerns",
            "Easy to understand",
        ],
        "cons": [
            "Mode negotiation overhead",
            "No benefit for legacy receivers from CSPM",
            "Wasted capacity during mixed operation",
            "Complex handover during mode switch",
        ],
        "best_for": "Transitional networks with clear upgrade timeline",
        "complexity": "Medium",
        "deployment_risk": "Medium",
    }

    # -------------------------------------------------------------------------
    # Architecture C: Layered/Superimposed (like DVB hierarchical)
    # -------------------------------------------------------------------------
    arch_c = {
        "name": "Layered Modulation",
        "description": "Legacy as base layer, CSPM as enhancement layer",
        "pros": [
            "Legacy always works (base layer)",
            "CSPM adds capability without breaking legacy",
            "Graceful degradation built-in",
            "Same spectrum, enhanced for capable receivers",
        ],
        "cons": [
            "Power split between layers (SNR penalty)",
            "More complex signal generation",
            "Interference between layers if not careful",
            "Legacy gets less power than pure legacy",
        ],
        "best_for": "Broadcast/multicast with mixed receivers",
        "complexity": "High",
        "deployment_risk": "Medium",
    }

    # -------------------------------------------------------------------------
    # Architecture D: Frequency Partitioned (OFDM subcarriers)
    # -------------------------------------------------------------------------
    arch_d = {
        "name": "Frequency Partitioned",
        "description": "Some subcarriers legacy, some CSPM",
        "pros": [
            "Clean separation in frequency domain",
            "Legacy and CSPM don't interfere",
            "Flexible allocation based on traffic",
            "Standard OFDM processing applies",
        ],
        "cons": [
            "Reduced bandwidth for each mode",
            "Spatial field needs wideband (conflicts)",
            "Complex resource allocation",
            "Position estimation harder (narrowband CSPM)",
        ],
        "best_for": "Mixed traffic with clear service separation",
        "complexity": "Medium-High",
        "deployment_risk": "Low",
    }

    # -------------------------------------------------------------------------
    # Architecture E: Time Partitioned (frame structure)
    # -------------------------------------------------------------------------
    arch_e = {
        "name": "Time Partitioned",
        "description": "Legacy and CSPM in different time slots",
        "pros": [
            "Clean separation in time domain",
            "Full bandwidth for each mode",
            "Simple scheduling",
            "Legacy devices just ignore CSPM slots",
        ],
        "cons": [
            "Reduced duty cycle for each mode",
            "Latency impact from time sharing",
            "Sync overhead at slot boundaries",
            "Position estimation needs continuous signal",
        ],
        "best_for": "Networks with bursty traffic, clear QoS tiers",
        "complexity": "Medium",
        "deployment_risk": "Low",
    }

    # -------------------------------------------------------------------------
    # Architecture F: RECOMMENDED - Hybrid Fractal with Legacy Fallback
    # -------------------------------------------------------------------------
    arch_f = {
        "name": "Hybrid Fractal (RECOMMENDED)",
        "description": """
        Use fractal's hierarchical structure strategically:
        - Level 0 (coarse): Maps to/from legacy QPSK (compatibility)
        - Level 1: CSPM enhancement (6.9 bits total)
        - Level 2+: High-capacity secure mode (9+ bits)

        The KEY INSIGHT: Fractal level 0 IS a 24-symbol constellation.
        This can be designed to be decodable by legacy equipment as
        a non-standard but simple PSK-like scheme.
        """,
        "pros": [
            "Fractal coarse level = legacy-compatible",
            "Same signal, different decode depths",
            "Natural graceful degradation",
            "No mode switching, just decode depth",
            "LPI at fine levels, open at coarse",
            "Position estimation uses all levels",
        ],
        "cons": [
            "Coarse level not standard QAM (needs mapping)",
            "Legacy devices see reduced rate (4.6 vs 6 bits)",
            "Rotation breaks even coarse for non-synced receivers",
        ],
        "best_for": "New satellite constellations with legacy ground segment",
        "complexity": "Medium",
        "deployment_risk": "Low-Medium",
    }

    architectures = [arch_a, arch_b, arch_c, arch_d, arch_e, arch_f]

    # Print analysis
    for arch in architectures:
        print(f"\n{'─' * 78}")
        print(f"ARCHITECTURE: {arch['name']}")
        print(f"{'─' * 78}")
        print(f"\n{arch['description'].strip()}\n")

        print("PROS:")
        for pro in arch['pros']:
            print(f"  ✓ {pro}")

        print("\nCONS:")
        for con in arch['cons']:
            print(f"  ✗ {con}")

        print(f"\nBest for: {arch['best_for']}")
        print(f"Complexity: {arch['complexity']}")
        print(f"Deployment Risk: {arch['deployment_risk']}")

    return architectures


def design_hybrid_fractal_system():
    """
    Design the recommended hybrid system in detail.
    """

    print("\n" + "=" * 78)
    print("DETAILED DESIGN: Hybrid Fractal with Legacy Compatibility")
    print("=" * 78)

    design = """

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         SIGNAL STRUCTURE                                 │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                          │
    │   Level 2+  ●───●───●     High Security (9+ bits)                       │
    │            /│\\ /│\\ /│\\    - Full LPI (hash chain rotation)              │
    │   Level 1 ● ● ● ● ● ●     Standard CSPM (6.9 bits)                      │
    │          /│ │ │ │ │ │\\    - Per-level rotation                          │
    │   Level 0 ●─●─●─●─●─●─●   Legacy Compatible (4.6 bits)                  │
    │          ═══════════════  - NO ROTATION (or slow/predictable)           │
    │           24 coarse       - Decodable by legacy with adapter            │
    │           symbols                                                        │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘

    KEY DESIGN DECISIONS:

    1. LEVEL 0 IS UNROTATED (or slowly rotated with published schedule)
       - Legacy receivers can always decode coarse symbols
       - This is the "public" layer for broadcast/emergency
       - 24 symbols ≈ APSK-24 (similar to DVB-S2 modes)

    2. LEVELS 1+ USE HASH CHAIN ROTATION
       - Secure layer for authorized receivers
       - Each level can rotate independently
       - LPI increases with level depth

    3. LEGACY MAPPING
       - 24-cell vertices map to custom APSK-24 constellation
       - Legacy coherent receiver sees valid (if non-standard) PSK
       - Existing DSP can be adapted with firmware update

    4. FRAME STRUCTURE

       ┌──────────┬──────────┬──────────┬──────────┐
       │  SYNC    │  HEADER  │  PAYLOAD │  PILOT   │
       │ (L0 only)│ (L0+meta)│ (L0-L2)  │ (L0 only)│
       └──────────┴──────────┴──────────┴──────────┘

       - SYNC: Level 0 only, unrotated, for legacy acquisition
       - HEADER: Level 0 + metadata (what levels are active)
       - PAYLOAD: Hierarchical (decode to your capability)
       - PILOT: Level 0, for channel estimation

    5. CAPABILITY NEGOTIATION
       - Node advertises max decode level
       - TX chooses encoding depth based on:
         * RX capability
         * Security requirement
         * Channel condition (SNR)

    6. POSITION ESTIMATION
       - Uses timing differences across all levels
       - Multi-satellite: each sat has different level rotation
       - Position encoded in relative phase across levels

    """
    print(design)

    # Rate table
    print("RATE TABLE:")
    print("─" * 60)
    print(f"{'Mode':<25} {'Symbols':<10} {'Bits/Sym':<10} {'Security':<15}")
    print("─" * 60)

    modes = [
        ("Legacy (L0 only)", 24, 4.58, "None (open)"),
        ("Standard (L0+L1)", 120, 6.91, "LPI Level 1"),
        ("Enhanced (L0+L1+L2)", 600, 9.23, "LPI Level 2"),
        ("Maximum (L0+L1+L2+L3)", 3000, 11.55, "LPI Level 3"),
    ]

    for mode, syms, bits, sec in modes:
        print(f"{mode:<25} {syms:<10} {bits:<10.2f} {sec:<15}")

    print("─" * 60)

    # Comparison to pure legacy
    print("\nCOMPARISON TO LEGACY ALTERNATIVES:")
    print("─" * 60)

    comparisons = [
        ("QPSK", 4, 2.0, "None"),
        ("16-QAM", 16, 4.0, "None"),
        ("64-QAM", 64, 6.0, "None"),
        ("256-QAM", 256, 8.0, "None"),
        ("Hybrid L0", 24, 4.58, "Upgradeable"),
        ("Hybrid L2", 600, 9.23, "Full LPI"),
    ]

    print(f"{'Mode':<15} {'Symbols':<10} {'Bits/Sym':<10} {'LPI':<15}")
    print("─" * 60)
    for mode, syms, bits, sec in comparisons:
        print(f"{mode:<15} {syms:<10} {bits:<10.2f} {sec:<15}")

    return design


def satellite_link_analysis():
    """
    Analyze link budgets for LEO/GEO hybrid scenario.
    """

    print("\n" + "=" * 78)
    print("SATELLITE LINK BUDGET ANALYSIS")
    print("=" * 78)

    # LEO link (e.g., Starlink-like)
    leo_link = LinkBudget(
        frequency_ghz=12.0,      # Ku-band
        tx_power_dbw=13.0,       # ~20W
        tx_gain_dbi=38.0,        # Phased array
        path_loss_db=180.0,      # ~550km altitude
        rx_gain_dbi=35.0,        # Ground terminal
        noise_figure_db=2.0,
        bandwidth_mhz=250.0,
    )

    # GEO link (e.g., traditional GEO)
    geo_link = LinkBudget(
        frequency_ghz=12.0,
        tx_power_dbw=20.0,       # Higher power
        tx_gain_dbi=42.0,        # Large antenna
        path_loss_db=205.0,      # ~36,000km
        rx_gain_dbi=40.0,        # Larger ground terminal
        noise_figure_db=1.5,
        bandwidth_mhz=36.0,      # Typical transponder
    )

    print(f"\nLEO Link (550km):")
    print(f"  SNR: {leo_link.snr_db:.1f} dB")
    print(f"  Recommended mode: ", end="")
    if leo_link.snr_db > 25:
        print("Fractal L2 (9.2 bits/sym)")
    elif leo_link.snr_db > 15:
        print("Fractal L1 (6.9 bits/sym)")
    else:
        print("Fractal L0 (4.6 bits/sym)")

    print(f"\nGEO Link (36,000km):")
    print(f"  SNR: {geo_link.snr_db:.1f} dB")
    print(f"  Recommended mode: ", end="")
    if geo_link.snr_db > 25:
        print("Fractal L2 (9.2 bits/sym)")
    elif geo_link.snr_db > 15:
        print("Fractal L1 (6.9 bits/sym)")
    else:
        print("Fractal L0 (4.6 bits/sym)")

    print("\nMULTI-SATELLITE SCENARIO:")
    print("""
    ┌────────────────────────────────────────────────────────────────────┐
    │                          GEO                                        │
    │                           ●  (timing reference)                     │
    │                          /│\\                                        │
    │                         / │ \\                                       │
    │        LEO-1 ●─────────/──│──\\─────────● LEO-2                     │
    │               \\       /   │   \\       /                            │
    │                \\     /    │    \\     /                             │
    │                 \\   /     │     \\   /                              │
    │                  \\ /      │      \\ /                               │
    │                   ●───────●───────●  Ground receivers               │
    │                          RX                                         │
    └────────────────────────────────────────────────────────────────────┘

    Position Estimation:
    - GEO provides stable timing reference (slow moving)
    - LEO satellites provide geometric diversity (fast moving)
    - Each satellite uses different level rotations
    - Receiver triangulates from differential timing

    Throughput:
    - LEO-1 + LEO-2: Combined 2× single link rate
    - GEO: Lower rate but always available
    - Handover: Fractal gracefully degrades as geometry changes
    """)

    return leo_link, geo_link


def recommend_implementation_path():
    """
    Recommend practical implementation steps.
    """

    print("\n" + "=" * 78)
    print("RECOMMENDED IMPLEMENTATION PATH")
    print("=" * 78)

    phases = """

    PHASE 1: GROUND VALIDATION (6-12 months)
    ─────────────────────────────────────────
    ├── Implement fractal constellation in SDR (GNU Radio / USRP)
    ├── Test Level 0 compatibility with legacy coherent receivers
    ├── Validate LPI at Levels 1-2 with simulated attacker
    ├── Measure actual BER vs theoretical curves
    └── Deliverable: Working SDR prototype, test report

    PHASE 2: SINGLE LINK DEMO (6-12 months)
    ───────────────────────────────────────
    ├── Ground-to-ground link with full fractal stack
    ├── Demonstrate adaptive rate (vary SNR, watch level switching)
    ├── Legacy receiver compatibility test
    ├── Position estimation with 2 TXs
    └── Deliverable: Field demonstration, performance data

    PHASE 3: MULTI-NODE NETWORK (12-18 months)
    ─────────────────────────────────────────
    ├── 3+ node network with mixed capabilities
    ├── Legacy + CSPM coexistence
    ├── Multi-TX position estimation
    ├── Handover between nodes
    └── Deliverable: Network testbed, protocol specification

    PHASE 4: SATELLITE INTEGRATION (18-24 months)
    ─────────────────────────────────────────────
    ├── Payload design for LEO cubesat
    ├── Ground segment adaptation
    ├── Link budget validation
    ├── Multi-satellite geometry tests
    └── Deliverable: Flight-ready payload design

    PHASE 5: ON-ORBIT DEMO (24-36 months)
    ─────────────────────────────────────
    ├── Launch on rideshare opportunity
    ├── Commission and calibrate
    ├── Full system demonstration
    ├── Publish results
    └── Deliverable: Operational demonstration, peer-reviewed results


    CRITICAL PATH ITEMS:

    1. Level 0 ↔ Legacy mapping is the KEY to adoption
       - Must work with existing ground infrastructure
       - Firmware update only, no hardware change

    2. Multi-satellite sync is the KEY to position estimation
       - Need common timing reference
       - GEO can provide this

    3. Hash chain management is the KEY to security
       - How do authorized receivers get initial state?
       - How do we handle lost sync?
       - Key distribution architecture

    4. Regulatory approval for non-standard modulation
       - May need to characterize spectral properties
       - Show compliance with ITU spectrum masks
       - Interference analysis with adjacent systems

    """
    print(phases)

    return phases


def main():
    """Run full analysis."""
    analyze_architectures()
    design_hybrid_fractal_system()
    satellite_link_analysis()
    recommend_implementation_path()

    print("\n" + "=" * 78)
    print("SUMMARY: RECOMMENDED APPROACH")
    print("=" * 78)
    print("""
    The HYBRID FRACTAL architecture is recommended because:

    1. LEGACY COMPATIBILITY via Level 0
       - Unrotated coarse level = always decodable
       - Maps to APSK-24-like constellation
       - Legacy receivers need firmware update only

    2. GRACEFUL CAPABILITY SCALING
       - Same signal, decode to your capability
       - No mode negotiation complexity
       - Natural degradation under noise

    3. PROGRESSIVE SECURITY
       - Level 0: Open (broadcast, emergency)
       - Level 1: Basic LPI (standard secure)
       - Level 2+: Full LPI (high security)

    4. SATELLITE-FRIENDLY
       - Adapts to varying link margin automatically
       - Multi-satellite position estimation
       - Works with LEO + GEO hybrid constellations

    5. HONEST TRADE-OFFS
       - Level 0 is 4.6 bits (vs 6 bits for 64-QAM)
       - But: upgradeable to 9+ bits for capable receivers
       - And: LPI not available in pure QAM at any rate

    The unique value is NOT "better QAM" but "QAM + LPI + Position + Adaptation"
    in a single modulation scheme with backward compatibility.
    """)


if __name__ == "__main__":
    main()
