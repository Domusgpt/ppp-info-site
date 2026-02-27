"""
Policy Resolution System

Context-aware policy evaluation consuming geometric metrics.
Determines access to Atlas artifacts and capabilities based
on geometric state compliance.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from datetime import datetime


class PolicyDecision(Enum):
    """Possible policy decisions."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CORRECTION = "require_correction"
    ESCALATE = "escalate"


@dataclass
class Policy:
    """
    Single governance policy with geometric conditions.

    Policies define rules for accessing Atlas artifacts
    or exercising capabilities based on geometric state.
    """

    policy_id: str
    name: str = ""
    description: str = ""
    priority: int = 0  # Higher = evaluated first

    # Conditions (all must be met for policy to apply)
    min_coherence: Optional[float] = None
    max_drift: Optional[float] = None
    required_region: Optional[str] = None
    max_angular_velocity: Optional[float] = None

    # Decision when conditions are met
    decision: PolicyDecision = PolicyDecision.ALLOW

    # Actions
    grant_capabilities: List[str] = field(default_factory=list)
    revoke_capabilities: List[str] = field(default_factory=list)
    inject_context: Optional[str] = None

    # Metadata
    enabled: bool = True
    created: float = field(default_factory=lambda: datetime.utcnow().timestamp())

    def evaluate(
        self,
        coherence: float = 1.0,
        drift: float = 0.0,
        region: str = "",
        angular_velocity: float = 0.0
    ) -> tuple:
        """
        Evaluate policy conditions.

        Returns (applies, decision) where applies indicates
        if all conditions are met.
        """
        if not self.enabled:
            return False, None

        # Check each condition
        if self.min_coherence is not None and coherence < self.min_coherence:
            return False, None

        if self.max_drift is not None and drift > self.max_drift:
            return False, None

        if self.required_region is not None and region != self.required_region:
            return False, None

        if self.max_angular_velocity is not None and angular_velocity > self.max_angular_velocity:
            return False, None

        return True, self.decision

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "conditions": {
                "min_coherence": self.min_coherence,
                "max_drift": self.max_drift,
                "required_region": self.required_region,
                "max_angular_velocity": self.max_angular_velocity,
            },
            "decision": self.decision.value,
            "grant_capabilities": self.grant_capabilities,
            "revoke_capabilities": self.revoke_capabilities,
            "inject_context": self.inject_context,
            "enabled": self.enabled,
        }


@dataclass
class PolicyEvaluationResult:
    """Result of policy evaluation."""

    decision: PolicyDecision
    matching_policy: Optional[str]
    granted_capabilities: List[str]
    revoked_capabilities: List[str]
    context_injection: Optional[str]
    evaluation_chain: List[str]
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())


class PolicyResolver:
    """
    Resolves policies based on geometric state.

    Evaluates policies in priority order and returns
    the first matching decision.
    """

    def __init__(self):
        self.policies: List[Policy] = []
        self.default_decision = PolicyDecision.DENY
        self._evaluation_count = 0

    def add_policy(self, policy: Policy) -> None:
        """Add a policy and re-sort by priority."""
        self.policies.append(policy)
        self.policies.sort(key=lambda p: -p.priority)

    def remove_policy(self, policy_id: str) -> bool:
        """Remove policy by ID."""
        for i, p in enumerate(self.policies):
            if p.policy_id == policy_id:
                self.policies.pop(i)
                return True
        return False

    def resolve(
        self,
        coherence: float = 1.0,
        drift: float = 0.0,
        region: str = "",
        angular_velocity: float = 0.0
    ) -> PolicyEvaluationResult:
        """
        Resolve policies for given geometric state.

        Evaluates policies in priority order, returns
        first matching result.
        """
        self._evaluation_count += 1
        evaluation_chain = []
        granted = []
        revoked = []
        context = None

        for policy in self.policies:
            applies, decision = policy.evaluate(
                coherence=coherence,
                drift=drift,
                region=region,
                angular_velocity=angular_velocity,
            )

            evaluation_chain.append(f"{policy.policy_id}: {'match' if applies else 'skip'}")

            if applies:
                granted.extend(policy.grant_capabilities)
                revoked.extend(policy.revoke_capabilities)
                if policy.inject_context:
                    context = policy.inject_context

                return PolicyEvaluationResult(
                    decision=decision,
                    matching_policy=policy.policy_id,
                    granted_capabilities=granted,
                    revoked_capabilities=revoked,
                    context_injection=context,
                    evaluation_chain=evaluation_chain,
                )

        # No policy matched - use default
        return PolicyEvaluationResult(
            decision=self.default_decision,
            matching_policy=None,
            granted_capabilities=[],
            revoked_capabilities=[],
            context_injection=None,
            evaluation_chain=evaluation_chain,
        )

    def create_standard_policies(self) -> None:
        """Create a set of standard geometric policies."""

        # High coherence = full access
        self.add_policy(Policy(
            policy_id="high_coherence",
            name="High Coherence Full Access",
            priority=100,
            min_coherence=0.9,
            max_drift=0.1,
            decision=PolicyDecision.ALLOW,
            grant_capabilities=["full_introspection", "atlas_access"],
        ))

        # Medium coherence = limited access
        self.add_policy(Policy(
            policy_id="medium_coherence",
            name="Medium Coherence Limited Access",
            priority=50,
            min_coherence=0.7,
            max_drift=0.3,
            decision=PolicyDecision.ALLOW,
            grant_capabilities=["basic_introspection"],
        ))

        # Low coherence = require correction
        self.add_policy(Policy(
            policy_id="low_coherence",
            name="Low Coherence Correction Required",
            priority=25,
            min_coherence=0.5,
            decision=PolicyDecision.REQUIRE_CORRECTION,
        ))

        # Very low coherence = deny
        self.add_policy(Policy(
            policy_id="critical_coherence",
            name="Critical Coherence Deny",
            priority=10,
            decision=PolicyDecision.DENY,
        ))

    def to_json(self) -> str:
        """Serialize policies to JSON."""
        return json.dumps({
            "policies": [p.to_dict() for p in self.policies],
            "default_decision": self.default_decision.value,
        }, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'PolicyResolver':
        """Deserialize from JSON."""
        data = json.loads(json_str)
        resolver = cls()
        resolver.default_decision = PolicyDecision(data.get("default_decision", "deny"))

        for p_data in data.get("policies", []):
            policy = Policy(
                policy_id=p_data["policy_id"],
                name=p_data.get("name", ""),
                description=p_data.get("description", ""),
                priority=p_data.get("priority", 0),
                min_coherence=p_data.get("conditions", {}).get("min_coherence"),
                max_drift=p_data.get("conditions", {}).get("max_drift"),
                required_region=p_data.get("conditions", {}).get("required_region"),
                max_angular_velocity=p_data.get("conditions", {}).get("max_angular_velocity"),
                decision=PolicyDecision(p_data.get("decision", "deny")),
                grant_capabilities=p_data.get("grant_capabilities", []),
                revoke_capabilities=p_data.get("revoke_capabilities", []),
                inject_context=p_data.get("inject_context"),
                enabled=p_data.get("enabled", True),
            )
            resolver.add_policy(policy)

        return resolver
