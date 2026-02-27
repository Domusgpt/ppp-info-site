"""
Event Data Recorder (EDR) for Geometric State

Implements EDR pattern for tamper-proof recording of
essential geometric data before/during/after incidents.

Based on EU EDR Regulation (2019/2144) pattern:
- 15 essential + 30 optional data elements
- Recording for seconds before/during/after events
- Tamper-proof storage
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque


@dataclass
class EDRFrame:
    """
    Single frame of EDR data.

    Contains essential geometric state at one point in time.
    """

    timestamp: float
    frame_id: int

    # Essential elements (always recorded)
    quaternion: tuple = (1.0, 0.0, 0.0, 0.0)
    position: tuple = (0.0, 0.0, 0.0)
    velocity: tuple = (0.0, 0.0, 0.0)
    acceleration: tuple = (0.0, 0.0, 0.0)

    # Geometric state
    spinor_coherence: float = 1.0
    isoclinic_left: float = 0.0
    isoclinic_right: float = 0.0
    bridge_magnitude: float = 1.0

    # System state
    drift_detected: bool = False
    correction_applied: bool = False
    constraint_violation: bool = False

    # Optional elements
    hopf_fiber: tuple = (1.0, 0.0, 0.0, 0.0)
    polytope_centroid: tuple = (0.0, 0.0, 0.0, 0.0)
    betti_numbers: tuple = (1, 0, 0)

    def fingerprint(self) -> str:
        """Compute frame fingerprint."""
        data = {
            "t": round(self.timestamp, 6),
            "q": [round(x, 8) for x in self.quaternion],
            "p": [round(x, 6) for x in self.position],
            "v": [round(x, 6) for x in self.velocity],
            "c": round(self.spinor_coherence, 6),
        }
        canonical = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "frame_id": self.frame_id,
            "essential": {
                "quaternion": self.quaternion,
                "position": self.position,
                "velocity": self.velocity,
                "acceleration": self.acceleration,
            },
            "geometric": {
                "coherence": self.spinor_coherence,
                "isoclinic_left": self.isoclinic_left,
                "isoclinic_right": self.isoclinic_right,
                "bridge_magnitude": self.bridge_magnitude,
            },
            "status": {
                "drift_detected": self.drift_detected,
                "correction_applied": self.correction_applied,
                "constraint_violation": self.constraint_violation,
            },
            "optional": {
                "hopf_fiber": self.hopf_fiber,
                "polytope_centroid": self.polytope_centroid,
                "betti_numbers": self.betti_numbers,
            },
            "fingerprint": self.fingerprint(),
        }


@dataclass
class EDRExport:
    """
    Exported EDR recording for incident analysis.
    """

    export_id: str
    trigger_event: str
    trigger_time: float

    pre_event_frames: List[EDRFrame]
    during_event_frames: List[EDRFrame]
    post_event_frames: List[EDRFrame]

    created: float = field(default_factory=lambda: datetime.utcnow().timestamp())

    def get_all_frames(self) -> List[EDRFrame]:
        """Get all frames in chronological order."""
        return self.pre_event_frames + self.during_event_frames + self.post_event_frames

    def compute_chain_hash(self) -> str:
        """Compute hash of entire frame chain."""
        fingerprints = [f.fingerprint() for f in self.get_all_frames()]
        combined = "".join(fingerprints)
        return hashlib.sha256(combined.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "export_id": self.export_id,
            "trigger_event": self.trigger_event,
            "trigger_time": self.trigger_time,
            "created": self.created,
            "frame_counts": {
                "pre_event": len(self.pre_event_frames),
                "during_event": len(self.during_event_frames),
                "post_event": len(self.post_event_frames),
            },
            "pre_event_frames": [f.to_dict() for f in self.pre_event_frames],
            "during_event_frames": [f.to_dict() for f in self.during_event_frames],
            "post_event_frames": [f.to_dict() for f in self.post_event_frames],
            "chain_hash": self.compute_chain_hash(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class EDRCapture:
    """
    Event Data Recorder for continuous geometric state capture.

    Maintains rolling buffer of frames and exports on trigger events.
    """

    def __init__(
        self,
        pre_event_seconds: float = 5.0,
        post_event_seconds: float = 2.0,
        frame_rate: float = 10.0,
        buffer_size: int = 1000
    ):
        """
        Initialize EDR capture.

        Args:
            pre_event_seconds: Seconds of data to keep before trigger
            post_event_seconds: Seconds of data to capture after trigger
            frame_rate: Expected frames per second
            buffer_size: Maximum buffer size
        """
        self.pre_event_seconds = pre_event_seconds
        self.post_event_seconds = post_event_seconds
        self.frame_rate = frame_rate
        self.buffer_size = buffer_size

        self.buffer: deque = deque(maxlen=buffer_size)
        self._frame_counter = 0
        self._triggered = False
        self._trigger_time = 0.0
        self._trigger_event = ""
        self._post_trigger_frames: List[EDRFrame] = []

    def record_frame(
        self,
        quaternion: tuple,
        position: tuple,
        velocity: tuple,
        acceleration: tuple = (0, 0, 0),
        coherence: float = 1.0,
        isoclinic_left: float = 0.0,
        isoclinic_right: float = 0.0,
        drift_detected: bool = False,
        correction_applied: bool = False,
        constraint_violation: bool = False,
        **kwargs
    ) -> EDRFrame:
        """Record a single frame of geometric state."""
        frame = EDRFrame(
            timestamp=datetime.utcnow().timestamp(),
            frame_id=self._frame_counter,
            quaternion=quaternion,
            position=position,
            velocity=velocity,
            acceleration=acceleration,
            spinor_coherence=coherence,
            isoclinic_left=isoclinic_left,
            isoclinic_right=isoclinic_right,
            drift_detected=drift_detected,
            correction_applied=correction_applied,
            constraint_violation=constraint_violation,
            **kwargs
        )

        self._frame_counter += 1

        if self._triggered:
            # Collecting post-trigger frames
            self._post_trigger_frames.append(frame)
        else:
            # Normal buffering
            self.buffer.append(frame)

        return frame

    def trigger(self, event_name: str) -> bool:
        """
        Trigger EDR capture.

        Starts collecting post-event frames.
        Returns True if trigger accepted.
        """
        if self._triggered:
            return False

        self._triggered = True
        self._trigger_time = datetime.utcnow().timestamp()
        self._trigger_event = event_name
        self._post_trigger_frames = []

        return True

    def is_triggered(self) -> bool:
        """Check if capture is in triggered state."""
        return self._triggered

    def should_export(self) -> bool:
        """Check if enough post-trigger frames collected."""
        if not self._triggered:
            return False

        if not self._post_trigger_frames:
            return False

        elapsed = self._post_trigger_frames[-1].timestamp - self._trigger_time
        return elapsed >= self.post_event_seconds

    def export(self) -> Optional[EDRExport]:
        """
        Export captured EDR data.

        Returns EDRExport if triggered, None otherwise.
        """
        if not self._triggered:
            return None

        # Get pre-event frames
        pre_frames = list(self.buffer)

        # Filter to pre-event window
        pre_event_cutoff = self._trigger_time - self.pre_event_seconds
        pre_frames = [f for f in pre_frames if f.timestamp >= pre_event_cutoff]

        # Split during-event frames
        during_frames = [
            f for f in self._post_trigger_frames
            if f.timestamp <= self._trigger_time + 0.5  # 0.5s "during" window
        ]

        post_frames = [
            f for f in self._post_trigger_frames
            if f.timestamp > self._trigger_time + 0.5
        ]

        export = EDRExport(
            export_id=f"EDR-{int(self._trigger_time)}",
            trigger_event=self._trigger_event,
            trigger_time=self._trigger_time,
            pre_event_frames=pre_frames,
            during_event_frames=during_frames,
            post_event_frames=post_frames,
        )

        # Reset trigger state
        self._triggered = False
        self._post_trigger_frames = []

        return export

    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get statistics about current buffer state."""
        if not self.buffer:
            return {"frames": 0, "duration": 0, "oldest": None, "newest": None}

        frames = list(self.buffer)
        return {
            "frames": len(frames),
            "duration": frames[-1].timestamp - frames[0].timestamp if len(frames) > 1 else 0,
            "oldest": frames[0].timestamp,
            "newest": frames[-1].timestamp,
            "triggered": self._triggered,
        }
