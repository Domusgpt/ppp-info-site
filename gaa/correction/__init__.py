"""
Error Correction Layer - Hyperdimensional Computing

Implements HDC-based error correction for reasoning drift detection
and repair using geometric cleanup memory and resonator networks.

Key Components:
- HypervectorStore: High-dimensional distributed representations
- CleanupMemory: Nearest-neighbor projection to valid states
- ResonatorNetwork: Compositional factorization verification
- DriftDetector: δ-hyperbolicity and coherence monitoring

Based on:
- IBM HDC research: "57× more robust than traditional clustering"
- Berkeley/Intel resonator networks for factorization
- Vector Symbolic Architectures (VSA) theory
"""

from .hypervector import HypervectorStore, Hypervector
from .cleanup import CleanupMemory, CorrectionResult
from .resonator import ResonatorNetwork, FactorizationResult
from .drift import DriftDetector, DriftMetrics

__all__ = [
    "HypervectorStore",
    "Hypervector",
    "CleanupMemory",
    "CorrectionResult",
    "ResonatorNetwork",
    "FactorizationResult",
    "DriftDetector",
    "DriftMetrics",
]
