"""
TRACE Event System

Hash-chained audit events for geometric cognition trails.
Each event links to its predecessor via cryptographic hash,
creating a tamper-evident log.

Event Types:
- GEOMETRIC_STATE: Snapshot of polytope/spinor state
- POLYTOPE_TRANSITION: State change in geometric space
- COHERENCE_CHECK: Spinor coherence measurement
- CORRECTION_APPLIED: HDC cleanup correction event
- DRIFT_DETECTED: Reasoning drift above threshold
- CONSTRAINT_VIOLATION: ISpec constraint breach
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


class EventType(Enum):
    """Types of TRACE audit events."""

    # Geometric state events
    GEOMETRIC_STATE = "geometric_state"
    POLYTOPE_TRANSITION = "polytope_transition"
    QUATERNION_UPDATE = "quaternion_update"

    # Spinor/coherence events
    COHERENCE_CHECK = "coherence_check"
    ISOCLINIC_DECOMPOSITION = "isoclinic_decomposition"
    HOPF_FIBER_UPDATE = "hopf_fiber_update"

    # Error correction events
    CORRECTION_APPLIED = "correction_applied"
    DRIFT_DETECTED = "drift_detected"
    RESONATOR_FACTORIZATION = "resonator_factorization"

    # Governance events
    CONSTRAINT_VIOLATION = "constraint_violation"
    POLICY_EVALUATION = "policy_evaluation"
    LICENSE_CHECK = "license_check"

    # Coordination events
    CONSENSUS_UPDATE = "consensus_update"
    TOPOLOGY_VERIFICATION = "topology_verification"
    SWARM_STATE = "swarm_state"

    # Compliance events
    SAFETY_ASSERTION = "safety_assertion"
    EDR_CAPTURE = "edr_capture"
    TRACEABILITY_LINK = "traceability_link"


@dataclass
class TRACEEvent:
    """
    Single event in the TRACE audit chain.

    Each event contains:
    - Unique event ID (content-addressable hash)
    - Link to previous event (hash chain)
    - Timestamp
    - Event type and payload
    - Geometric fingerprint (compact state digest)
    """

    event_type: EventType
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    previous_hash: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    geometric_fingerprint: str = ""
    agent_id: str = ""
    session_id: str = ""

    # Computed fields
    event_hash: str = field(init=False, default="")

    def __post_init__(self):
        """Compute event hash after initialization."""
        self.event_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of event content."""
        content = {
            "type": self.event_type.value,
            "timestamp": round(self.timestamp, 6),
            "previous": self.previous_hash,
            "payload": self.payload,
            "fingerprint": self.geometric_fingerprint,
            "agent": self.agent_id,
            "session": self.session_id,
        }
        canonical = json.dumps(content, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify_chain(self, previous_event: Optional['TRACEEvent']) -> bool:
        """Verify this event correctly chains to previous."""
        if previous_event is None:
            return self.previous_hash == ""
        return self.previous_hash == previous_event.event_hash

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_hash": self.event_hash,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "payload": self.payload,
            "geometric_fingerprint": self.geometric_fingerprint,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TRACEEvent':
        """Create event from dictionary."""
        event = cls(
            event_type=EventType(data["event_type"]),
            timestamp=data["timestamp"],
            previous_hash=data["previous_hash"],
            payload=data["payload"],
            geometric_fingerprint=data.get("geometric_fingerprint", ""),
            agent_id=data.get("agent_id", ""),
            session_id=data.get("session_id", ""),
        )
        # Verify hash matches
        if event.event_hash != data.get("event_hash"):
            raise ValueError("Event hash mismatch - possible tampering")
        return event

    @classmethod
    def from_json(cls, json_str: str) -> 'TRACEEvent':
        """Create event from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class EventChain:
    """
    Append-only chain of TRACE events.

    Maintains hash chain integrity and provides verification.
    """

    events: List[TRACEEvent] = field(default_factory=list)
    genesis_hash: str = ""

    def __post_init__(self):
        """Initialize genesis hash if empty chain."""
        if not self.genesis_hash:
            self.genesis_hash = hashlib.sha256(b"TRACE_GENESIS").hexdigest()

    def append(self, event: TRACEEvent) -> TRACEEvent:
        """
        Append event to chain with proper linking.

        Returns the event with updated hash linkage.
        """
        # Get previous hash
        if self.events:
            previous_hash = self.events[-1].event_hash
        else:
            previous_hash = self.genesis_hash

        # Create new event with correct linkage
        linked_event = TRACEEvent(
            event_type=event.event_type,
            timestamp=event.timestamp,
            previous_hash=previous_hash,
            payload=event.payload,
            geometric_fingerprint=event.geometric_fingerprint,
            agent_id=event.agent_id,
            session_id=event.session_id,
        )

        self.events.append(linked_event)
        return linked_event

    def verify_integrity(self) -> bool:
        """Verify entire chain integrity."""
        if not self.events:
            return True

        # Check genesis link
        if self.events[0].previous_hash != self.genesis_hash:
            return False

        # Check all subsequent links
        for i in range(1, len(self.events)):
            if not self.events[i].verify_chain(self.events[i - 1]):
                return False

        return True

    def get_event(self, event_hash: str) -> Optional[TRACEEvent]:
        """Find event by hash."""
        for event in self.events:
            if event.event_hash == event_hash:
                return event
        return None

    def get_events_by_type(self, event_type: EventType) -> List[TRACEEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_events_in_range(
        self,
        start_time: float,
        end_time: float
    ) -> List[TRACEEvent]:
        """Get events within time range."""
        return [
            e for e in self.events
            if start_time <= e.timestamp <= end_time
        ]

    @property
    def head_hash(self) -> str:
        """Get hash of most recent event."""
        if self.events:
            return self.events[-1].event_hash
        return self.genesis_hash

    @property
    def length(self) -> int:
        """Number of events in chain."""
        return len(self.events)

    def to_json(self) -> str:
        """Serialize chain to JSON."""
        return json.dumps({
            "genesis_hash": self.genesis_hash,
            "events": [e.to_dict() for e in self.events],
        }, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'EventChain':
        """Deserialize chain from JSON."""
        data = json.loads(json_str)
        chain = cls(genesis_hash=data["genesis_hash"])
        for event_data in data["events"]:
            event = TRACEEvent.from_dict(event_data)
            chain.events.append(event)
        return chain


def create_geometric_state_event(
    state_fingerprint: str,
    quaternion_data: Dict[str, float],
    spinor_metrics: Dict[str, float],
    agent_id: str = "",
    session_id: str = "",
) -> TRACEEvent:
    """Factory function for geometric state events."""
    return TRACEEvent(
        event_type=EventType.GEOMETRIC_STATE,
        payload={
            "quaternion": quaternion_data,
            "spinor": spinor_metrics,
        },
        geometric_fingerprint=state_fingerprint,
        agent_id=agent_id,
        session_id=session_id,
    )


def create_correction_event(
    pre_correction_hash: str,
    post_correction_hash: str,
    correction_magnitude: float,
    correction_type: str,
    agent_id: str = "",
    session_id: str = "",
) -> TRACEEvent:
    """Factory function for correction applied events."""
    return TRACEEvent(
        event_type=EventType.CORRECTION_APPLIED,
        payload={
            "pre_correction_hash": pre_correction_hash,
            "post_correction_hash": post_correction_hash,
            "correction_magnitude": correction_magnitude,
            "correction_type": correction_type,
        },
        geometric_fingerprint=post_correction_hash,
        agent_id=agent_id,
        session_id=session_id,
    )


def create_drift_event(
    current_state_hash: str,
    reference_state_hash: str,
    drift_magnitude: float,
    drift_type: str,
    threshold: float,
    agent_id: str = "",
    session_id: str = "",
) -> TRACEEvent:
    """Factory function for drift detection events."""
    return TRACEEvent(
        event_type=EventType.DRIFT_DETECTED,
        payload={
            "current_state": current_state_hash,
            "reference_state": reference_state_hash,
            "drift_magnitude": drift_magnitude,
            "drift_type": drift_type,
            "threshold": threshold,
            "exceeded": drift_magnitude > threshold,
        },
        geometric_fingerprint=current_state_hash,
        agent_id=agent_id,
        session_id=session_id,
    )
