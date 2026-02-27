"""
Hypervector Implementation

High-dimensional distributed representations for robust encoding.
Information is holographically spread across all dimensions,
providing natural noise tolerance.

Key property: In 10,000-dimensional space, a corrupted bit
affects only 0.01% of the representation.

Operations:
- Binding (⊗): Multiplicative association
- Bundling (+): Additive superposition
- Permutation (ρ): Sequence encoding
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Union
import hashlib


@dataclass
class Hypervector:
    """
    High-dimensional distributed representation.

    Uses bipolar encoding: components ∈ {-1, +1}
    Dimensionality typically 10,000 for robust error tolerance.
    """

    components: np.ndarray
    dimension: int = field(init=False)

    def __post_init__(self):
        self.components = np.asarray(self.components, dtype=np.float64)
        self.dimension = len(self.components)

    @classmethod
    def random(cls, dimension: int = 10000, seed: Optional[int] = None) -> 'Hypervector':
        """Generate random bipolar hypervector."""
        rng = np.random.default_rng(seed)
        components = rng.choice([-1.0, 1.0], size=dimension)
        return cls(components)

    @classmethod
    def zeros(cls, dimension: int = 10000) -> 'Hypervector':
        """Generate zero hypervector."""
        return cls(np.zeros(dimension))

    @classmethod
    def from_seed(cls, seed: bytes, dimension: int = 10000) -> 'Hypervector':
        """
        Generate deterministic hypervector from seed.

        Uses hash-based expansion for reproducibility.
        """
        # Use hash to generate deterministic random state
        hash_bytes = hashlib.sha256(seed).digest()
        seed_int = int.from_bytes(hash_bytes[:8], 'big')

        return cls.random(dimension, seed=seed_int)

    @classmethod
    def from_quaternion(
        cls,
        quaternion: np.ndarray,
        dimension: int = 10000
    ) -> 'Hypervector':
        """
        Encode quaternion into hypervector.

        Uses structured encoding that preserves angular relationships.
        """
        q = np.asarray(quaternion, dtype=np.float64)

        # Normalize quaternion
        q = q / np.linalg.norm(q)

        # Create base vectors for each component
        base_vectors = []
        for i, comp in enumerate(q):
            seed = f"QUAT_BASE_{i}".encode()
            base = cls.from_seed(seed, dimension)
            # Scale by component value
            scaled = Hypervector(base.components * comp)
            base_vectors.append(scaled)

        # Bundle (superpose) all components
        result = base_vectors[0]
        for v in base_vectors[1:]:
            result = result.bundle(v)

        return result.normalize()

    @classmethod
    def from_geometric_state(
        cls,
        state_fingerprint: bytes,
        dimension: int = 10000
    ) -> 'Hypervector':
        """Encode geometric state fingerprint as hypervector."""
        return cls.from_seed(state_fingerprint, dimension)

    def bind(self, other: 'Hypervector') -> 'Hypervector':
        """
        Binding operation (⊗): element-wise multiplication.

        Creates association between hypervectors.
        Approximately self-inverse: x ⊗ x ≈ identity
        """
        if self.dimension != other.dimension:
            raise ValueError("Dimension mismatch for binding")
        return Hypervector(self.components * other.components)

    def bundle(self, other: 'Hypervector') -> 'Hypervector':
        """
        Bundling operation (+): element-wise addition.

        Creates superposition of hypervectors.
        Result is similar to all inputs.
        """
        if self.dimension != other.dimension:
            raise ValueError("Dimension mismatch for bundling")
        return Hypervector(self.components + other.components)

    def permute(self, shift: int = 1) -> 'Hypervector':
        """
        Permutation operation (ρ): circular shift.

        Used for encoding sequence/position information.
        """
        return Hypervector(np.roll(self.components, shift))

    def inverse_permute(self, shift: int = 1) -> 'Hypervector':
        """Inverse permutation."""
        return self.permute(-shift)

    def normalize(self) -> 'Hypervector':
        """Normalize to unit length."""
        norm = np.linalg.norm(self.components)
        if norm < 1e-10:
            return Hypervector.zeros(self.dimension)
        return Hypervector(self.components / norm)

    def binarize(self) -> 'Hypervector':
        """Convert to bipolar {-1, +1}."""
        return Hypervector(np.sign(self.components))

    def cosine_similarity(self, other: 'Hypervector') -> float:
        """Compute cosine similarity."""
        if self.dimension != other.dimension:
            raise ValueError("Dimension mismatch")

        norm_self = np.linalg.norm(self.components)
        norm_other = np.linalg.norm(other.components)

        if norm_self < 1e-10 or norm_other < 1e-10:
            return 0.0

        return np.dot(self.components, other.components) / (norm_self * norm_other)

    def hamming_similarity(self, other: 'Hypervector') -> float:
        """
        Compute Hamming similarity for bipolar vectors.

        Returns fraction of matching signs.
        """
        if self.dimension != other.dimension:
            raise ValueError("Dimension mismatch")

        signs_self = np.sign(self.components)
        signs_other = np.sign(other.components)

        matches = np.sum(signs_self == signs_other)
        return matches / self.dimension

    def add_noise(self, noise_fraction: float, seed: Optional[int] = None) -> 'Hypervector':
        """
        Add noise by flipping random component signs.

        Args:
            noise_fraction: Fraction of components to corrupt [0, 1]
        """
        rng = np.random.default_rng(seed)

        n_flip = int(self.dimension * noise_fraction)
        flip_indices = rng.choice(self.dimension, size=n_flip, replace=False)

        result = self.components.copy()
        result[flip_indices] *= -1

        return Hypervector(result)

    def fingerprint(self) -> bytes:
        """Compute compact fingerprint of hypervector."""
        # Use sign pattern for compact representation
        signs = np.packbits((self.components > 0).astype(np.uint8))
        return hashlib.sha256(signs.tobytes()).digest()

    def __add__(self, other: 'Hypervector') -> 'Hypervector':
        """Bundle via + operator."""
        return self.bundle(other)

    def __mul__(self, other: 'Hypervector') -> 'Hypervector':
        """Bind via * operator."""
        return self.bind(other)

    def __repr__(self) -> str:
        return f"Hypervector(dim={self.dimension}, norm={np.linalg.norm(self.components):.3f})"


class HypervectorStore:
    """
    Store of named hypervectors for semantic encoding.

    Provides:
    - Concept encoding with automatic vector generation
    - Compositional encoding via binding/bundling
    - Nearest-neighbor retrieval for cleanup
    """

    def __init__(self, dimension: int = 10000):
        self.dimension = dimension
        self.vectors: dict[str, Hypervector] = {}
        self._seed_counter = 0

    def add(self, name: str, vector: Optional[Hypervector] = None) -> Hypervector:
        """
        Add a named hypervector.

        If vector not provided, generates random vector.
        """
        if vector is None:
            seed = f"{name}_{self._seed_counter}".encode()
            vector = Hypervector.from_seed(seed, self.dimension)
            self._seed_counter += 1

        self.vectors[name] = vector
        return vector

    def get(self, name: str) -> Optional[Hypervector]:
        """Retrieve hypervector by name."""
        return self.vectors.get(name)

    def encode_composition(self, names: List[str]) -> Hypervector:
        """
        Encode ordered composition via binding.

        encode_composition(["A", "B", "C"]) = A ⊗ ρ(B) ⊗ ρ²(C)
        """
        if not names:
            return Hypervector.zeros(self.dimension)

        result = self.vectors.get(names[0])
        if result is None:
            result = self.add(names[0])

        for i, name in enumerate(names[1:], 1):
            vec = self.vectors.get(name)
            if vec is None:
                vec = self.add(name)
            # Apply positional permutation
            permuted = vec.permute(i)
            result = result.bind(permuted)

        return result

    def encode_set(self, names: List[str]) -> Hypervector:
        """
        Encode unordered set via bundling.

        encode_set(["A", "B", "C"]) = A + B + C
        """
        if not names:
            return Hypervector.zeros(self.dimension)

        vectors = []
        for name in names:
            vec = self.vectors.get(name)
            if vec is None:
                vec = self.add(name)
            vectors.append(vec)

        result = vectors[0]
        for v in vectors[1:]:
            result = result.bundle(v)

        return result.normalize()

    def nearest_neighbor(self, query: Hypervector, top_k: int = 1) -> List[tuple]:
        """
        Find nearest neighbors in store.

        Returns list of (name, similarity) tuples.
        """
        similarities = []
        for name, vec in self.vectors.items():
            sim = query.cosine_similarity(vec)
            similarities.append((name, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def cleanup(self, noisy: Hypervector) -> tuple:
        """
        Clean up noisy vector by snapping to nearest stored vector.

        Returns (cleaned_name, similarity).
        """
        result = self.nearest_neighbor(noisy, top_k=1)
        if not result:
            return (None, 0.0)
        return result[0]

    def __len__(self) -> int:
        return len(self.vectors)

    def __contains__(self, name: str) -> bool:
        return name in self.vectors
