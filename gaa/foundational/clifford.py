"""
Clifford Algebra Implementation

Provides geometric algebra operations for Cl(3,0) and Cl(4,0),
enabling unified treatment of rotations, reflections, and projections.

Mathematical Foundation:
- Clifford algebra Cl(n,0) over Euclidean space
- Basis elements: scalars, vectors, bivectors, trivectors, ...
- Geometric product: ab = a·b + a∧b

Key Operations:
- Multivector arithmetic (addition, geometric product)
- Grade projection and extraction
- Exponential map (rotors from bivectors)
- Hodge dual for complementary subspaces

References:
- Hestenes & Sobczyk (1984) "Clifford Algebra to Geometric Calculus"
- Dorst, Fontijne, Mann (2007) "Geometric Algebra for Computer Science"
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import hashlib


# Cl(3,0) basis element indices
# Grade 0: 1 (scalar)
# Grade 1: e1, e2, e3 (vectors)
# Grade 2: e12, e13, e23 (bivectors)
# Grade 3: e123 (pseudoscalar)

CL3_GRADES = {
    0: [0],          # scalar
    1: [1, 2, 3],    # vectors
    2: [4, 5, 6],    # bivectors
    3: [7],          # pseudoscalar
}

CL3_BASIS_NAMES = ['1', 'e1', 'e2', 'e3', 'e12', 'e13', 'e23', 'e123']


def _cl3_geometric_product_table() -> np.ndarray:
    """
    Precompute geometric product table for Cl(3,0).

    Returns 8x8x8 array where table[i,j] gives the result
    of multiplying basis element i by basis element j.
    Format: (sign, result_index)
    """
    # Encoding: value = sign * (result_index + 1)
    # 0 means result is 0
    table = np.zeros((8, 8), dtype=np.int8)

    # Products of basis elements
    # 1 * anything = anything
    table[0, :] = [1, 2, 3, 4, 5, 6, 7, 8]
    table[:, 0] = [1, 2, 3, 4, 5, 6, 7, 8]

    # e_i * e_i = 1
    table[1, 1] = 1   # e1*e1 = 1
    table[2, 2] = 1   # e2*e2 = 1
    table[3, 3] = 1   # e3*e3 = 1

    # e_i * e_j = e_ij (i < j)
    table[1, 2] = 5   # e1*e2 = e12
    table[2, 1] = -5  # e2*e1 = -e12
    table[1, 3] = 6   # e1*e3 = e13
    table[3, 1] = -6  # e3*e1 = -e13
    table[2, 3] = 7   # e2*e3 = e23
    table[3, 2] = -7  # e3*e2 = -e23

    # Bivector products
    table[4, 4] = -1  # e12*e12 = -1
    table[5, 5] = -1  # e13*e13 = -1
    table[6, 6] = -1  # e23*e23 = -1

    # Mixed bivector products
    table[4, 5] = -7   # e12*e13 = -e23
    table[5, 4] = 7    # e13*e12 = e23
    table[4, 6] = 6    # e12*e23 = e13
    table[6, 4] = -6   # e23*e12 = -e13
    table[5, 6] = -5   # e13*e23 = -e12
    table[6, 5] = 5    # e23*e13 = e12

    # Vector * Bivector
    table[1, 4] = 3    # e1*e12 = e2
    table[4, 1] = -3   # e12*e1 = -e2
    table[2, 4] = -2   # e2*e12 = -e1
    table[4, 2] = 2    # e12*e2 = e1
    table[1, 5] = 4    # e1*e13 = e3
    table[5, 1] = -4   # e13*e1 = -e3
    table[3, 5] = -2   # e3*e13 = -e1
    table[5, 3] = 2    # e13*e3 = e1
    table[2, 6] = 4    # e2*e23 = e3
    table[6, 2] = -4   # e23*e2 = -e3
    table[3, 6] = -3   # e3*e23 = -e2
    table[6, 3] = 3    # e23*e3 = e2
    table[1, 6] = 8    # e1*e23 = e123
    table[6, 1] = 8    # e23*e1 = e123
    table[2, 5] = -8   # e2*e13 = -e123
    table[5, 2] = -8   # e13*e2 = -e123
    table[3, 4] = 8    # e3*e12 = e123
    table[4, 3] = 8    # e12*e3 = e123

    # Pseudoscalar products
    table[7, 7] = -1   # e123*e123 = -1

    # Vector * Pseudoscalar
    table[1, 7] = 7    # e1*e123 = e23
    table[7, 1] = 7    # e123*e1 = e23
    table[2, 7] = -6   # e2*e123 = -e13
    table[7, 2] = -6   # e123*e2 = -e13
    table[3, 7] = 5    # e3*e123 = e12
    table[7, 3] = 5    # e123*e3 = e12

    # Bivector * Pseudoscalar
    table[4, 7] = 4    # e12*e123 = e3
    table[7, 4] = -4   # e123*e12 = -e3
    table[5, 7] = -3   # e13*e123 = -e2
    table[7, 5] = 3    # e123*e13 = e2
    table[6, 7] = 2    # e23*e123 = e1
    table[7, 6] = -2   # e123*e23 = -e1

    return table


_CL3_PRODUCT_TABLE = _cl3_geometric_product_table()


@dataclass
class Multivector:
    """
    Multivector in Clifford algebra Cl(3,0).

    A multivector is a linear combination of basis blades:
    M = s + v1*e1 + v2*e2 + v3*e3 + b12*e12 + b13*e13 + b23*e23 + p*e123

    Components stored as 8-element array:
    [scalar, e1, e2, e3, e12, e13, e23, e123]
    """

    components: np.ndarray = field(default_factory=lambda: np.zeros(8))

    def __post_init__(self):
        self.components = np.asarray(self.components, dtype=np.float64)
        if self.components.shape != (8,):
            raise ValueError(f"Multivector must have 8 components, got {self.components.shape}")

    @classmethod
    def scalar(cls, s: float) -> 'Multivector':
        """Create scalar multivector."""
        components = np.zeros(8)
        components[0] = s
        return cls(components)

    @classmethod
    def vector(cls, v: np.ndarray) -> 'Multivector':
        """Create vector (grade-1) multivector."""
        v = np.asarray(v, dtype=np.float64)
        if v.shape != (3,):
            raise ValueError("Vector must have 3 components")
        components = np.zeros(8)
        components[1:4] = v
        return cls(components)

    @classmethod
    def bivector(cls, b: np.ndarray) -> 'Multivector':
        """Create bivector (grade-2) multivector."""
        b = np.asarray(b, dtype=np.float64)
        if b.shape != (3,):
            raise ValueError("Bivector must have 3 components")
        components = np.zeros(8)
        components[4:7] = b
        return cls(components)

    @classmethod
    def pseudoscalar(cls, p: float) -> 'Multivector':
        """Create pseudoscalar (grade-3) multivector."""
        components = np.zeros(8)
        components[7] = p
        return cls(components)

    @classmethod
    def rotor(cls, axis: np.ndarray, angle: float) -> 'Multivector':
        """
        Create rotor (unit even multivector) from axis-angle.

        A rotor R = cos(θ/2) - sin(θ/2)*B where B is the unit bivector
        representing the rotation plane.
        """
        axis = np.asarray(axis, dtype=np.float64)
        axis = axis / np.linalg.norm(axis)

        # Bivector from axis (Hodge dual of axis in 3D)
        bivector = np.array([axis[2], -axis[1], axis[0]])

        half_angle = angle / 2.0
        components = np.zeros(8)
        components[0] = np.cos(half_angle)
        components[4:7] = -np.sin(half_angle) * bivector

        return cls(components)

    @property
    def scalar_part(self) -> float:
        """Extract scalar (grade-0) part."""
        return self.components[0]

    @property
    def vector_part(self) -> np.ndarray:
        """Extract vector (grade-1) part."""
        return self.components[1:4].copy()

    @property
    def bivector_part(self) -> np.ndarray:
        """Extract bivector (grade-2) part."""
        return self.components[4:7].copy()

    @property
    def pseudoscalar_part(self) -> float:
        """Extract pseudoscalar (grade-3) part."""
        return self.components[7]

    def grade(self, k: int) -> 'Multivector':
        """Extract grade-k part."""
        if k not in CL3_GRADES:
            raise ValueError(f"Grade must be 0-3, got {k}")

        components = np.zeros(8)
        for idx in CL3_GRADES[k]:
            components[idx] = self.components[idx]
        return Multivector(components)

    def even(self) -> 'Multivector':
        """Extract even-grade parts (scalar + bivector)."""
        components = np.zeros(8)
        components[0] = self.components[0]
        components[4:7] = self.components[4:7]
        return Multivector(components)

    def odd(self) -> 'Multivector':
        """Extract odd-grade parts (vector + pseudoscalar)."""
        components = np.zeros(8)
        components[1:4] = self.components[1:4]
        components[7] = self.components[7]
        return Multivector(components)

    def reverse(self) -> 'Multivector':
        """
        Reversion: reverses the order of basis vectors in each blade.

        Scalars and vectors unchanged, bivectors and trivector negated.
        """
        components = self.components.copy()
        components[4:7] = -components[4:7]  # Bivectors
        components[7] = -components[7]       # Pseudoscalar
        return Multivector(components)

    def conjugate(self) -> 'Multivector':
        """Clifford conjugate: grade involution + reversion."""
        components = self.components.copy()
        components[1:4] = -components[1:4]  # Vectors
        components[7] = -components[7]       # Pseudoscalar
        return Multivector(components)

    def norm(self) -> float:
        """Multivector norm: sqrt(|M * M~|)."""
        rev = self.reverse()
        product = self * rev
        return np.sqrt(abs(product.scalar_part))

    def normalized(self) -> 'Multivector':
        """Return unit multivector."""
        n = self.norm()
        if n < 1e-10:
            return Multivector.scalar(0.0)
        return Multivector(self.components / n)

    def __add__(self, other: 'Multivector') -> 'Multivector':
        """Multivector addition."""
        if not isinstance(other, Multivector):
            raise TypeError(f"Cannot add Multivector with {type(other)}")
        return Multivector(self.components + other.components)

    def __sub__(self, other: 'Multivector') -> 'Multivector':
        """Multivector subtraction."""
        if not isinstance(other, Multivector):
            raise TypeError(f"Cannot subtract {type(other)} from Multivector")
        return Multivector(self.components - other.components)

    def __mul__(self, other: 'Multivector') -> 'Multivector':
        """Geometric product."""
        if not isinstance(other, Multivector):
            # Scalar multiplication
            if isinstance(other, (int, float)):
                return Multivector(self.components * other)
            raise TypeError(f"Cannot multiply Multivector with {type(other)}")

        result = np.zeros(8)

        for i in range(8):
            if abs(self.components[i]) < 1e-15:
                continue
            for j in range(8):
                if abs(other.components[j]) < 1e-15:
                    continue

                product_code = _CL3_PRODUCT_TABLE[i, j]
                if product_code == 0:
                    continue

                sign = 1 if product_code > 0 else -1
                result_idx = abs(product_code) - 1

                result[result_idx] += sign * self.components[i] * other.components[j]

        return Multivector(result)

    def __rmul__(self, other: float) -> 'Multivector':
        """Right scalar multiplication."""
        return Multivector(self.components * other)

    def __neg__(self) -> 'Multivector':
        """Negation."""
        return Multivector(-self.components)

    def inner(self, other: 'Multivector') -> 'Multivector':
        """Inner (dot) product."""
        # For grade-1 vectors: a·b is scalar part of ab
        product = self * other
        return product.grade(0)

    def outer(self, other: 'Multivector') -> 'Multivector':
        """Outer (wedge) product."""
        # a ∧ b = (ab - ba) / 2 for anticommuting parts
        # For vectors: gives bivector
        ab = self * other
        ba = other * self
        return Multivector((ab.components - ba.components) / 2.0)

    def sandwich(self, rotor: 'Multivector') -> 'Multivector':
        """
        Sandwich product: R * self * R~

        Used for rotations and reflections.
        """
        return rotor * self * rotor.reverse()

    def exp(self) -> 'Multivector':
        """
        Exponential of multivector.

        For bivectors: exp(B) = cos(|B|) + sin(|B|)*B/|B|
        This gives a rotor.
        """
        # For pure bivector
        b = self.bivector_part
        b_norm = np.linalg.norm(b)

        if b_norm < 1e-10:
            # exp(scalar) = e^s
            return Multivector.scalar(np.exp(self.scalar_part))

        # exp(bivector) = cos(|B|) + sin(|B|) * B/|B|
        cos_b = np.cos(b_norm)
        sin_b = np.sin(b_norm)
        b_unit = b / b_norm

        result = np.zeros(8)
        result[0] = cos_b * np.exp(self.scalar_part)
        result[4:7] = sin_b * b_unit * np.exp(self.scalar_part)

        return Multivector(result)

    def log(self) -> 'Multivector':
        """
        Logarithm of even multivector (rotor).

        Returns bivector such that exp(result) ≈ self.
        """
        # For rotor R = cos(θ/2) + sin(θ/2)*B_unit
        s = self.scalar_part
        b = self.bivector_part
        b_norm = np.linalg.norm(b)

        if b_norm < 1e-10:
            # Nearly identity
            return Multivector.scalar(np.log(abs(s)))

        # θ/2 = atan2(|B|, s)
        half_angle = np.arctan2(b_norm, s)
        b_unit = b / b_norm

        result = np.zeros(8)
        result[4:7] = half_angle * b_unit

        return Multivector(result)

    def fingerprint(self) -> bytes:
        """Compute cryptographic fingerprint."""
        canonical = np.round(self.components, decimals=10)
        return hashlib.sha256(canonical.tobytes()).digest()

    def __repr__(self) -> str:
        terms = []
        for i, name in enumerate(CL3_BASIS_NAMES):
            if abs(self.components[i]) > 1e-10:
                if name == '1':
                    terms.append(f"{self.components[i]:.4f}")
                else:
                    terms.append(f"{self.components[i]:.4f}*{name}")
        return "Multivector(" + " + ".join(terms) + ")" if terms else "Multivector(0)"


class CliffordAlgebra:
    """
    Factory and utility class for Clifford algebra operations.

    Provides construction of common elements and transformations.
    """

    @staticmethod
    def basis(i: int) -> Multivector:
        """Get i-th basis element (0=1, 1=e1, 2=e2, etc.)."""
        components = np.zeros(8)
        components[i] = 1.0
        return Multivector(components)

    @staticmethod
    def e(i: int) -> Multivector:
        """Get basis vector e_i (1-indexed)."""
        if i < 1 or i > 3:
            raise ValueError(f"Basis vector index must be 1-3, got {i}")
        return CliffordAlgebra.basis(i)

    @staticmethod
    def I3() -> Multivector:
        """Pseudoscalar I = e1*e2*e3."""
        return Multivector.pseudoscalar(1.0)

    @staticmethod
    def rotation(axis: np.ndarray, angle: float) -> Multivector:
        """Create rotation rotor from axis-angle."""
        return Multivector.rotor(axis, angle)

    @staticmethod
    def reflection(normal: np.ndarray) -> Multivector:
        """Create reflection versor from plane normal."""
        return Multivector.vector(normal).normalized()

    @staticmethod
    def project_onto(v: Multivector, blade: Multivector) -> Multivector:
        """Project vector v onto blade."""
        blade_rev = blade.reverse()
        return (v.inner(blade) * blade_rev) * Multivector.scalar(1.0 / (blade * blade_rev).scalar_part)

    @staticmethod
    def reject_from(v: Multivector, blade: Multivector) -> Multivector:
        """Reject vector v from blade (orthogonal complement)."""
        projected = CliffordAlgebra.project_onto(v, blade)
        return v - projected

    @staticmethod
    def angle_between(a: Multivector, b: Multivector) -> float:
        """Compute angle between two vectors."""
        a_vec = a.vector_part
        b_vec = b.vector_part

        a_norm = np.linalg.norm(a_vec)
        b_norm = np.linalg.norm(b_vec)

        if a_norm < 1e-10 or b_norm < 1e-10:
            return 0.0

        cos_angle = np.dot(a_vec, b_vec) / (a_norm * b_norm)
        return np.arccos(np.clip(cos_angle, -1.0, 1.0))
