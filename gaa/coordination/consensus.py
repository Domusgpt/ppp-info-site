"""
Manifold Consensus for Multi-Agent Coordination

Implements consensus algorithms on quaternion manifolds (S³/SO(3))
for coordinating agent orientations without centralized command.

Based on Riemannian gradient descent following Sarlette & Sepulchre's
work on attitude synchronization.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from ..foundational.quaternion import Quaternion


@dataclass
class ConsensusState:
    """State of consensus computation."""

    # Agent states
    agent_quaternions: Dict[str, Quaternion] = field(default_factory=dict)

    # Consensus metrics
    disagreement: float = 0.0
    fiedler_value: float = 0.0
    convergence_rate: float = 0.0

    # Computed consensus
    consensus_quaternion: Optional[Quaternion] = None

    # Iteration tracking
    iteration: int = 0
    converged: bool = False

    def get_agent_count(self) -> int:
        return len(self.agent_quaternions)


class ManifoldConsensus:
    """
    Consensus protocol on quaternion manifold.

    Agents follow Riemannian gradient descent to synchronize
    their orientations on S³.

    Update rule:
    q_i(t+1) = q_i(t) * exp(ε * Σ_j log(q_i(t)^(-1) * q_j(t)))

    where ε is the step size and the sum is over neighbors j.
    """

    def __init__(
        self,
        step_size: float = 0.1,
        convergence_threshold: float = 0.01,
        max_iterations: int = 1000
    ):
        """
        Initialize consensus protocol.

        Args:
            step_size: Gradient descent step size ε
            convergence_threshold: Disagreement threshold for convergence
            max_iterations: Maximum iterations
        """
        self.step_size = step_size
        self.convergence_threshold = convergence_threshold
        self.max_iterations = max_iterations

        # Agents and connectivity
        self.agents: Dict[str, Quaternion] = {}
        self.adjacency: Dict[str, List[str]] = {}

        # State history
        self.history: List[ConsensusState] = []

    def add_agent(
        self,
        agent_id: str,
        quaternion: Quaternion,
        neighbors: Optional[List[str]] = None
    ) -> None:
        """Add an agent to the consensus group."""
        self.agents[agent_id] = quaternion
        self.adjacency[agent_id] = neighbors or []

    def set_adjacency(self, adjacency: Dict[str, List[str]]) -> None:
        """Set full adjacency matrix."""
        self.adjacency = adjacency

    def make_fully_connected(self) -> None:
        """Make all agents neighbors of each other."""
        agent_ids = list(self.agents.keys())
        for agent_id in agent_ids:
            self.adjacency[agent_id] = [a for a in agent_ids if a != agent_id]

    def compute_disagreement(self) -> float:
        """
        Compute total disagreement function.

        ψ = Σ_edges ||q_i - q_j||²

        Lower values indicate better consensus.
        """
        disagreement = 0.0
        counted_edges = set()

        for agent_id, neighbors in self.adjacency.items():
            q_i = self.agents[agent_id]
            for neighbor_id in neighbors:
                edge = tuple(sorted([agent_id, neighbor_id]))
                if edge in counted_edges:
                    continue
                counted_edges.add(edge)

                q_j = self.agents.get(neighbor_id)
                if q_j is None:
                    continue

                # Use angular distance
                dist = q_i.angular_distance(q_j)
                disagreement += dist ** 2

        return disagreement

    def compute_fiedler_value(self) -> float:
        """
        Compute algebraic connectivity (Fiedler value).

        This is the second-smallest eigenvalue of the graph Laplacian.
        Larger values indicate faster consensus convergence.
        """
        agent_ids = list(self.agents.keys())
        n = len(agent_ids)

        if n < 2:
            return 0.0

        # Build adjacency matrix
        A = np.zeros((n, n))
        id_to_idx = {aid: i for i, aid in enumerate(agent_ids)}

        for agent_id, neighbors in self.adjacency.items():
            i = id_to_idx[agent_id]
            for neighbor_id in neighbors:
                if neighbor_id in id_to_idx:
                    j = id_to_idx[neighbor_id]
                    A[i, j] = 1

        # Laplacian: L = D - A
        D = np.diag(A.sum(axis=1))
        L = D - A

        # Eigenvalues
        eigenvalues = np.linalg.eigvalsh(L)
        eigenvalues.sort()

        if len(eigenvalues) >= 2:
            return float(eigenvalues[1])
        return 0.0

    def compute_consensus(self) -> Quaternion:
        """
        Compute the weighted Fréchet mean of all quaternions.

        This is the "consensus point" that minimizes total distance.
        """
        if not self.agents:
            return Quaternion.identity()

        # Simple average in embedding space
        # (exact Fréchet mean requires iterative optimization)
        total = np.zeros(4)
        for q in self.agents.values():
            # Handle hemisphere ambiguity
            if total[0] * q.w < 0:
                total -= q.components
            else:
                total += q.components

        return Quaternion(total)

    def step(self) -> ConsensusState:
        """
        Perform one consensus iteration.

        Each agent updates toward the mean of its neighbors.
        """
        new_quaternions = {}

        for agent_id, q_i in self.agents.items():
            neighbors = self.adjacency.get(agent_id, [])

            if not neighbors:
                new_quaternions[agent_id] = q_i
                continue

            # Compute update direction (Riemannian gradient)
            update = np.zeros(4)

            for neighbor_id in neighbors:
                q_j = self.agents.get(neighbor_id)
                if q_j is None:
                    continue

                # log_q_i(q_j) ≈ direction from q_i to q_j
                # Simplified: use difference in embedding space
                diff = q_j.components - q_i.components

                # Handle hemisphere
                if np.dot(q_i.components, q_j.components) < 0:
                    diff = -q_j.components - q_i.components

                update += diff

            # Average and scale by step size
            update = self.step_size * update / len(neighbors)

            # Apply update
            new_components = q_i.components + update
            new_quaternions[agent_id] = Quaternion(new_components)

        # Update all agents
        self.agents = new_quaternions

        # Compute state
        state = ConsensusState(
            agent_quaternions=dict(self.agents),
            disagreement=self.compute_disagreement(),
            fiedler_value=self.compute_fiedler_value(),
            consensus_quaternion=self.compute_consensus(),
            iteration=len(self.history) + 1,
            converged=False,
        )

        if state.disagreement < self.convergence_threshold:
            state.converged = True

        self.history.append(state)
        return state

    def run_until_convergence(self) -> ConsensusState:
        """Run iterations until convergence or max iterations."""
        for _ in range(self.max_iterations):
            state = self.step()
            if state.converged:
                break
        return self.history[-1] if self.history else ConsensusState()

    def get_convergence_rate(self) -> float:
        """Estimate convergence rate from history."""
        if len(self.history) < 2:
            return 0.0

        disagreements = [s.disagreement for s in self.history]
        if disagreements[0] < 1e-10:
            return 1.0

        # Exponential decay rate estimation
        ratios = [
            disagreements[i] / disagreements[i-1]
            for i in range(1, len(disagreements))
            if disagreements[i-1] > 1e-10
        ]

        if ratios:
            return 1.0 - np.mean(ratios)
        return 0.0
