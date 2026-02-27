"""
Governance Layer - ISpec Constraints and Audit Agents

Implements the Verifiability-First Agents (VFA) architecture pattern
for geometric governance of AI reasoning.

Key Components:
- ISpec: Intent Specification with geometric constraints
- GeometricConstraint: Manifold/polytope region restrictions
- AuditAgent: Lightweight monitors for TRACE provenance
- PolicyResolver: Context-aware policy evaluation

Based on:
- CRA "context as licensed artifact" model
- VFA architecture for verifiable AI agents
"""

from .ispec import ISpec, ConstraintType
from .constraints import GeometricConstraint, ManifoldRegion
from .audit_agent import AuditAgent, AuditResult, ViolationSeverity
from .policy import PolicyResolver, Policy, PolicyDecision

__all__ = [
    "ISpec",
    "ConstraintType",
    "GeometricConstraint",
    "ManifoldRegion",
    "AuditAgent",
    "AuditResult",
    "ViolationSeverity",
    "PolicyResolver",
    "Policy",
    "PolicyDecision",
]
