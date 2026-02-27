"""
Coordination Layer - Multi-Agent Geometric Coordination

Implements manifold consensus protocols for sub-agent alignment
and topological coverage verification without centralization.

Key Components:
- ManifoldConsensus: Riemannian gradient descent for agent alignment
- TopologyVerifier: Coordinate-free coverage verification
- HopfCoordinator: Hopf fibration-based orientation decomposition
- SwarmAnalyzer: Persistence landscape analysis of swarm state

Based on:
- Sarlette & Sepulchre SO(3) consensus
- De Silva & Ghrist coverage verification
- Watterson & Kumar Hopf Fibration Control
"""

from .consensus import ManifoldConsensus, ConsensusState
from .topology import TopologyVerifier, CoverageResult
from .hopf import HopfCoordinator, HopfDecomposition
from .swarm import SwarmAnalyzer, SwarmMetrics

__all__ = [
    "ManifoldConsensus",
    "ConsensusState",
    "TopologyVerifier",
    "CoverageResult",
    "HopfCoordinator",
    "HopfDecomposition",
    "SwarmAnalyzer",
    "SwarmMetrics",
]
