"""
Cryptographically-Seeded Polytopal Modulation (CSPM) for Optical Networks

A physical-layer optical communication system that modulates signals onto
the 120 vertices of a 600-cell polytope in 4D Hilbert space, using:
- Polarization Bloch sphere (2D) + OAM superposition Bloch sphere (2D)
- Coherent superposition states for continuous 4D manifold

Key innovations (HONEST CLAIMS):
1. Geometric error correction via vertex quantization
   - Overhead is IN the constellation, not "zero"
   - O(120) complexity, comparable to 128-QAM's O(128)
2. LPI/LPD obfuscation via hash-chain lattice rotation
   - NOT encryption - provides signal obscurity
   - Resistant to blind equalization (constellation rotates)
3. ~1-2 dB SNR advantage over 128-QAM (fair comparison)

See WHITEPAPER.md v3.0 for honest performance claims.
See ROADMAP.md for development priorities.

Copyright (c) 2025 Paul Phillips - Clear Seas Solutions LLC
"""

from .lattice import Cell600, PolychoralConstellation
from .transmitter import CSPMTransmitter, HashChainRotator
from .channel import OpticalChannel, FiberChannel, FreespaceChannel
from .receiver import CSPMReceiver, GeometricQuantizer
from .baseline import QAMModulator, QAMDemodulator, QAMFiberChannel
from .simulation import run_comparison, BERAnalysis
from .adversarial import run_full_security_analysis, AttackResult

__version__ = "2.0.0"  # Honest revision
__author__ = "Paul Phillips"

__all__ = [
    "Cell600",
    "PolychoralConstellation",
    "CSPMTransmitter",
    "HashChainRotator",
    "OpticalChannel",
    "FiberChannel",
    "FreespaceChannel",
    "CSPMReceiver",
    "GeometricQuantizer",
    "QAMModulator",
    "QAMDemodulator",
    "QAMFiberChannel",
    "run_comparison",
    "BERAnalysis",
    "run_full_security_analysis",
    "AttackResult",
]
