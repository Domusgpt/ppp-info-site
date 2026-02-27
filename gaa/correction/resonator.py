"""
Resonator Network for Compositional Verification

Implements resonator networks from Berkeley/Intel research for
factorizing compound hypervectors into atomic constituents.

Key insight: If a reasoning state is a valid composition of
grounded concepts, the resonator will converge to factor it.
Failure to converge indicates corrupted composition.

Usage:
1. Register atomic concept vectors
2. Query with compound vector
3. Resonator iteratively decomposes
4. Convergence = valid composition
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from enum import Enum

from .hypervector import Hypervector, HypervectorStore


class ConvergenceStatus(Enum):
    """Status of resonator convergence."""

    CONVERGED = "converged"
    OSCILLATING = "oscillating"
    DIVERGED = "diverged"
    MAX_ITERATIONS = "max_iterations"


@dataclass
class FactorizationResult:
    """Result of resonator factorization attempt."""

    status: ConvergenceStatus
    factors: List[str]
    iterations: int
    final_similarity: float
    convergence_history: List[float]

    @property
    def is_valid_composition(self) -> bool:
        """Check if factorization indicates valid composition."""
        return self.status == ConvergenceStatus.CONVERGED

    @property
    def composition_confidence(self) -> float:
        """Confidence in composition validity."""
        if self.status == ConvergenceStatus.CONVERGED:
            return self.final_similarity
        elif self.status == ConvergenceStatus.MAX_ITERATIONS:
            return self.final_similarity * 0.5
        else:
            return 0.0


class ResonatorNetwork:
    """
    Resonator network for hypervector factorization.

    Given a compound vector C and codebooks of atomic vectors,
    finds factors {f1, f2, ...} such that:

    C ≈ f1 ⊗ f2 ⊗ ... ⊗ fn

    Uses iterative cleanup at each factor position to find
    the decomposition that best reconstructs C.

    Based on:
    - Frady et al. "Resonator Networks" (2020)
    - Intel/Berkeley neuromorphic computing research
    """

    def __init__(
        self,
        dimension: int = 10000,
        max_iterations: int = 100,
        convergence_threshold: float = 0.95,
        oscillation_window: int = 5
    ):
        """
        Initialize resonator network.

        Args:
            dimension: Hypervector dimension
            max_iterations: Maximum iteration count
            convergence_threshold: Similarity threshold for convergence
            oscillation_window: Window for detecting oscillation
        """
        self.dimension = dimension
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.oscillation_window = oscillation_window

        # Codebooks for each factor position
        self.codebooks: List[HypervectorStore] = []

    def add_codebook(self, name: str = "") -> HypervectorStore:
        """Add a codebook for a factor position."""
        codebook = HypervectorStore(self.dimension)
        self.codebooks.append(codebook)
        return codebook

    def set_codebook(self, position: int, codebook: HypervectorStore) -> None:
        """Set codebook at specific position."""
        while len(self.codebooks) <= position:
            self.codebooks.append(HypervectorStore(self.dimension))
        self.codebooks[position] = codebook

    def factorize(
        self,
        compound: Hypervector,
        n_factors: Optional[int] = None
    ) -> FactorizationResult:
        """
        Attempt to factorize compound vector.

        Uses resonator dynamics:
        1. Initialize factor estimates randomly
        2. For each factor position:
           a. Compute residual by unbinding other factors
           b. Clean up residual against codebook
        3. Repeat until convergence or max iterations

        Args:
            compound: Compound hypervector to factorize
            n_factors: Number of factors (defaults to number of codebooks)

        Returns:
            FactorizationResult with factors and convergence info
        """
        if n_factors is None:
            n_factors = len(self.codebooks)

        if n_factors == 0:
            return FactorizationResult(
                status=ConvergenceStatus.DIVERGED,
                factors=[],
                iterations=0,
                final_similarity=0.0,
                convergence_history=[],
            )

        # Initialize factor estimates
        factor_estimates = []
        for i in range(n_factors):
            if i < len(self.codebooks) and len(self.codebooks[i]) > 0:
                # Start with random codebook entry
                names = list(self.codebooks[i].vectors.keys())
                initial = self.codebooks[i].get(names[0])
            else:
                initial = Hypervector.random(self.dimension)
            factor_estimates.append(initial)

        convergence_history = []
        previous_similarities = []

        for iteration in range(self.max_iterations):
            # Update each factor
            for i in range(n_factors):
                # Compute product of all other factors
                other_product = None
                for j in range(n_factors):
                    if j != i:
                        if other_product is None:
                            other_product = factor_estimates[j]
                        else:
                            other_product = other_product.bind(factor_estimates[j])

                # Compute residual: C ⊗ (other_product)^(-1)
                # For bipolar, inverse is same as original
                if other_product is not None:
                    residual = compound.bind(other_product)
                else:
                    residual = compound

                # Clean up against codebook
                if i < len(self.codebooks):
                    name, sim = self.codebooks[i].cleanup(residual)
                    if name:
                        factor_estimates[i] = self.codebooks[i].get(name)

            # Compute reconstruction similarity
            reconstruction = factor_estimates[0]
            for f in factor_estimates[1:]:
                reconstruction = reconstruction.bind(f)

            similarity = compound.cosine_similarity(reconstruction)
            convergence_history.append(similarity)

            # Check convergence
            if similarity >= self.convergence_threshold:
                # Extract factor names
                factor_names = self._get_factor_names(factor_estimates)
                return FactorizationResult(
                    status=ConvergenceStatus.CONVERGED,
                    factors=factor_names,
                    iterations=iteration + 1,
                    final_similarity=similarity,
                    convergence_history=convergence_history,
                )

            # Check for oscillation
            previous_similarities.append(similarity)
            if len(previous_similarities) > self.oscillation_window:
                previous_similarities.pop(0)
                if self._is_oscillating(previous_similarities):
                    factor_names = self._get_factor_names(factor_estimates)
                    return FactorizationResult(
                        status=ConvergenceStatus.OSCILLATING,
                        factors=factor_names,
                        iterations=iteration + 1,
                        final_similarity=similarity,
                        convergence_history=convergence_history,
                    )

        # Max iterations reached
        factor_names = self._get_factor_names(factor_estimates)
        final_sim = convergence_history[-1] if convergence_history else 0.0

        return FactorizationResult(
            status=ConvergenceStatus.MAX_ITERATIONS,
            factors=factor_names,
            iterations=self.max_iterations,
            final_similarity=final_sim,
            convergence_history=convergence_history,
        )

    def _get_factor_names(self, estimates: List[Hypervector]) -> List[str]:
        """Get names of estimated factors from codebooks."""
        names = []
        for i, est in enumerate(estimates):
            if i < len(self.codebooks):
                name, _ = self.codebooks[i].cleanup(est)
                names.append(name or f"unknown_{i}")
            else:
                names.append(f"factor_{i}")
        return names

    def _is_oscillating(self, similarities: List[float]) -> bool:
        """Detect if similarities are oscillating."""
        if len(similarities) < 3:
            return False

        # Check for alternating pattern
        diffs = [similarities[i+1] - similarities[i] for i in range(len(similarities)-1)]
        sign_changes = sum(1 for i in range(len(diffs)-1) if diffs[i] * diffs[i+1] < 0)

        return sign_changes >= len(diffs) - 1

    def verify_composition(
        self,
        compound: Hypervector,
        expected_factors: List[str]
    ) -> Tuple[bool, float]:
        """
        Verify that compound decomposes into expected factors.

        Returns (is_valid, confidence).
        """
        result = self.factorize(compound, len(expected_factors))

        if not result.is_valid_composition:
            return False, 0.0

        # Check if factors match
        if set(result.factors) == set(expected_factors):
            return True, result.composition_confidence
        else:
            return False, result.composition_confidence * 0.5
