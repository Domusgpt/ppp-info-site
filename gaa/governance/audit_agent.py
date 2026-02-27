"""
Audit Agent Implementation

Lightweight monitors that continuously observe TRACE provenance
logs for geometric drift from ISpec constraints.

Audit Agents:
- Monitor TRACE event streams
- Evaluate geometric state against ISpec
- Generate violation reports
- Trigger governance responses
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from datetime import datetime

from .ispec import ISpec
from .constraints import GeometricConstraint
from ..telemetry.events import TRACEEvent, EventType, EventChain
from ..correction.drift import DriftMetrics


class ViolationSeverity(Enum):
    """Severity levels for constraint violations."""

    INFO = "info"           # Notable but not concerning
    WARNING = "warning"     # Approaching limits
    VIOLATION = "violation" # Constraint breached
    CRITICAL = "critical"   # Severe breach requiring intervention


@dataclass
class AuditResult:
    """Result of audit evaluation."""

    passed: bool
    severity: ViolationSeverity
    constraint_type: str
    message: str
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())

    # Details
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    threshold: Optional[float] = None

    # Event reference
    event_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "severity": self.severity.value,
            "constraint_type": self.constraint_type,
            "message": self.message,
            "timestamp": self.timestamp,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "threshold": self.threshold,
            "event_hash": self.event_hash,
        }


class AuditAgent:
    """
    Lightweight audit agent for geometric governance.

    Monitors TRACE events and evaluates against ISpec constraints.
    Generates audit results for violations.
    """

    def __init__(
        self,
        agent_id: str,
        ispec: ISpec,
        geometric_constraint: Optional[GeometricConstraint] = None
    ):
        """
        Initialize audit agent.

        Args:
            agent_id: Unique identifier for this agent
            ispec: Intent specification to enforce
            geometric_constraint: Optional additional geometric constraints
        """
        self.agent_id = agent_id
        self.ispec = ispec
        self.geometric_constraint = geometric_constraint

        self.audit_history: List[AuditResult] = []
        self.violation_count = 0
        self.event_count = 0

        # Callbacks for violations
        self._violation_handlers: List[Callable[[AuditResult], None]] = []

    def add_violation_handler(self, handler: Callable[[AuditResult], None]) -> None:
        """Register callback for violation events."""
        self._violation_handlers.append(handler)

    def evaluate_event(self, event: TRACEEvent) -> List[AuditResult]:
        """
        Evaluate a single TRACE event against constraints.

        Returns list of audit results (may include multiple checks).
        """
        self.event_count += 1
        results = []

        payload = event.payload

        # Check coherence if present
        if "spinor" in payload:
            coherence = payload["spinor"].get("coherence", 1.0)
            result = self._check_coherence(coherence, event.event_hash)
            results.append(result)
            if not result.passed:
                self._handle_violation(result)

        # Check quaternion state if present
        if "quaternion" in payload:
            q_data = payload["quaternion"]
            left_angle = q_data.get("leftAngle", 0.0)
            right_angle = q_data.get("rightAngle", 0.0)

            result = self._check_isoclinic(left_angle, right_angle, event.event_hash)
            results.append(result)
            if not result.passed:
                self._handle_violation(result)

        # Check drift metrics if present
        if "drift" in payload:
            drift = payload["drift"]
            results.extend(self._check_drift(drift, event.event_hash))

        # Check geometric region if present
        if "position" in payload and self.geometric_constraint:
            import numpy as np
            position = np.array(payload["position"])
            result = self._check_region(position, event.event_hash)
            results.append(result)
            if not result.passed:
                self._handle_violation(result)

        self.audit_history.extend(results)
        return results

    def _check_coherence(self, coherence: float, event_hash: str) -> AuditResult:
        """Check coherence against ISpec."""
        passed = self.ispec.validate_coherence(coherence)

        if passed:
            severity = ViolationSeverity.INFO
            message = f"Coherence {coherence:.3f} within bounds"
        elif coherence >= self.ispec.min_spinor_coherence * 0.8:
            severity = ViolationSeverity.WARNING
            message = f"Coherence {coherence:.3f} approaching minimum {self.ispec.min_spinor_coherence}"
        else:
            severity = ViolationSeverity.VIOLATION
            message = f"Coherence {coherence:.3f} below minimum {self.ispec.min_spinor_coherence}"

        return AuditResult(
            passed=passed,
            severity=severity,
            constraint_type="coherence",
            message=message,
            actual_value=coherence,
            threshold=self.ispec.min_spinor_coherence,
            event_hash=event_hash,
        )

    def _check_isoclinic(
        self,
        left_angle: float,
        right_angle: float,
        event_hash: str
    ) -> AuditResult:
        """Check isoclinic constraint."""
        defect = abs(left_angle - right_angle)
        passed = self.ispec.validate_isoclinic(left_angle, right_angle)

        if passed:
            severity = ViolationSeverity.INFO
            message = f"Isoclinic defect {defect:.4f} within bounds"
        elif defect <= self.ispec.max_isoclinic_defect * 1.5:
            severity = ViolationSeverity.WARNING
            message = f"Isoclinic defect {defect:.4f} approaching limit"
        else:
            severity = ViolationSeverity.VIOLATION
            message = f"Isoclinic defect {defect:.4f} exceeds {self.ispec.max_isoclinic_defect}"

        return AuditResult(
            passed=passed,
            severity=severity,
            constraint_type="isoclinic",
            message=message,
            actual_value=defect,
            threshold=self.ispec.max_isoclinic_defect,
            event_hash=event_hash,
        )

    def _check_drift(
        self,
        drift_data: Dict[str, float],
        event_hash: str
    ) -> List[AuditResult]:
        """Check drift metrics."""
        results = []

        validation = self.ispec.validate_drift(
            drift_data.get("hyperbolicity", 0.0),
            drift_data.get("angular_velocity", 0.0),
            drift_data.get("persistence", 0.0),
        )

        for metric, passed in validation.items():
            if passed:
                severity = ViolationSeverity.INFO
                message = f"Drift metric '{metric}' within bounds"
            else:
                severity = ViolationSeverity.VIOLATION
                message = f"Drift metric '{metric}' exceeds limit"

            results.append(AuditResult(
                passed=passed,
                severity=severity,
                constraint_type=f"drift_{metric}",
                message=message,
                event_hash=event_hash,
            ))

        return results

    def _check_region(self, position, event_hash: str) -> AuditResult:
        """Check geometric region constraint."""
        satisfied, reason = self.geometric_constraint.is_satisfied(position)

        if satisfied:
            return AuditResult(
                passed=True,
                severity=ViolationSeverity.INFO,
                constraint_type="region",
                message="Position within permitted region",
                event_hash=event_hash,
            )
        else:
            return AuditResult(
                passed=False,
                severity=ViolationSeverity.VIOLATION,
                constraint_type="region",
                message=reason,
                event_hash=event_hash,
            )

    def _handle_violation(self, result: AuditResult) -> None:
        """Handle a violation by calling registered handlers."""
        self.violation_count += 1
        for handler in self._violation_handlers:
            handler(result)

    def evaluate_chain(self, chain: EventChain) -> List[AuditResult]:
        """Evaluate all events in a chain."""
        all_results = []
        for event in chain.events:
            results = self.evaluate_event(event)
            all_results.extend(results)
        return all_results

    def get_violation_rate(self) -> float:
        """Compute fraction of events with violations."""
        if self.event_count == 0:
            return 0.0
        return self.violation_count / self.event_count

    def get_violations(self) -> List[AuditResult]:
        """Get all violation results."""
        return [r for r in self.audit_history if not r.passed]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of audit activity."""
        violations = self.get_violations()
        by_type = {}
        for v in violations:
            by_type[v.constraint_type] = by_type.get(v.constraint_type, 0) + 1

        return {
            "agent_id": self.agent_id,
            "ispec_name": self.ispec.name,
            "events_evaluated": self.event_count,
            "total_violations": self.violation_count,
            "violation_rate": self.get_violation_rate(),
            "violations_by_type": by_type,
        }
