"""
Foundational Layer - Geometric Algebra Primitives

Provides quaternion, dual quaternion, and Clifford algebra representations
for rotation state, along with E(3)/SE(3) equivariant encodings.

Key Components:
- Quaternion: Unit quaternion for 3D rotations (SO(3) double cover)
- DualQuaternion: Unified rotation + translation (SE(3) representation)
- CliffordAlgebra: General geometric algebra operations (Cl(3,0))
- GeometricState: Unified state container for PPP integration
"""

from .quaternion import Quaternion, DualQuaternion
from .clifford import CliffordAlgebra, Multivector
from .state import GeometricState, StateBundle

__all__ = [
    "Quaternion",
    "DualQuaternion",
    "CliffordAlgebra",
    "Multivector",
    "GeometricState",
    "StateBundle",
]
