"""
PPP State Serializer

Canonical serialization of PPP telemetry for hash-chained audit trails.
Ensures deterministic representation across platforms and versions.

Handles:
- SonicGeometryEngine telemetry frames
- Quaternion bridge payloads
- Spinor resonance atlas data
- Continuum constellation metrics
"""

import json
import hashlib
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


def _canonicalize_float(f: float, decimals: int = 10) -> float:
    """Round float to canonical precision."""
    if not np.isfinite(f):
        return 0.0
    return round(f, decimals)


def _canonicalize_array(arr: Any, decimals: int = 10) -> List:
    """Convert array to canonical list representation."""
    if isinstance(arr, np.ndarray):
        arr = arr.tolist()
    if isinstance(arr, list):
        return [
            _canonicalize_array(x, decimals) if isinstance(x, (list, np.ndarray))
            else _canonicalize_float(x, decimals) if isinstance(x, float)
            else x
            for x in arr
        ]
    return arr


def _canonicalize_dict(d: Dict, decimals: int = 10) -> Dict:
    """Recursively canonicalize dictionary values."""
    result = {}
    for key in sorted(d.keys()):
        value = d[key]
        if isinstance(value, dict):
            result[key] = _canonicalize_dict(value, decimals)
        elif isinstance(value, (list, np.ndarray)):
            result[key] = _canonicalize_array(value, decimals)
        elif isinstance(value, float):
            result[key] = _canonicalize_float(value, decimals)
        else:
            result[key] = value
    return result


@dataclass
class TelemetryFrame:
    """
    Single frame of PPP telemetry.

    Corresponds to one engine.getAnalysis() call from SonicGeometryEngine.
    """

    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    frame_id: int = 0

    # Quaternion bridge
    quaternion_bridge: Dict[str, float] = field(default_factory=dict)
    left_angle: float = 0.0
    right_angle: float = 0.0
    bridge_magnitude: float = 1.0

    # Spinor harmonics
    spinor_ratios: List[float] = field(default_factory=list)
    pan_lattice: List[float] = field(default_factory=list)
    phase_orbits: List[float] = field(default_factory=list)

    # Hopf fiber
    hopf_fiber: List[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0])

    # Resonance atlas
    resonance_axes: List[List[float]] = field(default_factory=list)
    carrier_embeddings: List[Dict[str, float]] = field(default_factory=list)

    # Signal fabric
    carrier_matrix: List[List[float]] = field(default_factory=list)
    bitstream_hex: str = ""
    spectral_centroid: float = 0.0

    # Transduction grid
    transduction_matrix: List[List[float]] = field(default_factory=list)
    transduction_determinant: float = 1.0
    frobenius_energy: float = 0.0

    # Manifold metrics
    quaternion_trace: float = 0.0
    spinor_coherence: float = 1.0
    braid_density: float = 0.0

    # Topology weave
    topology_axes: List[List[float]] = field(default_factory=list)
    braid_analytics: Dict[str, float] = field(default_factory=dict)

    # Continuum
    flux_density: float = 0.0
    orientation_residual: float = 0.0

    # Lattice
    lattice_centroids: List[List[float]] = field(default_factory=list)

    # Constellation
    constellation_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Convert to canonical dictionary for hashing."""
        raw = {
            "timestamp": self.timestamp,
            "frame_id": self.frame_id,
            "quaternion": {
                "bridge": self.quaternion_bridge,
                "leftAngle": self.left_angle,
                "rightAngle": self.right_angle,
                "bridgeMagnitude": self.bridge_magnitude,
            },
            "spinor": {
                "ratios": self.spinor_ratios,
                "panLattice": self.pan_lattice,
                "phaseOrbits": self.phase_orbits,
            },
            "hopfFiber": self.hopf_fiber,
            "resonance": {
                "axes": self.resonance_axes,
                "carriers": self.carrier_embeddings,
            },
            "signal": {
                "carrierMatrix": self.carrier_matrix,
                "bitstream": self.bitstream_hex,
                "spectralCentroid": self.spectral_centroid,
            },
            "transduction": {
                "matrix": self.transduction_matrix,
                "determinant": self.transduction_determinant,
                "frobeniusEnergy": self.frobenius_energy,
            },
            "manifold": {
                "quaternionTrace": self.quaternion_trace,
                "spinorCoherence": self.spinor_coherence,
                "braidDensity": self.braid_density,
            },
            "topology": {
                "axes": self.topology_axes,
                "braid": self.braid_analytics,
            },
            "continuum": {
                "fluxDensity": self.flux_density,
                "orientationResidual": self.orientation_residual,
            },
            "lattice": {
                "centroids": self.lattice_centroids,
            },
            "constellation": {
                "nodes": self.constellation_nodes,
            },
        }
        return _canonicalize_dict(raw)

    def fingerprint(self) -> bytes:
        """Compute SHA-256 fingerprint."""
        canonical = self.to_canonical_dict()
        canonical_json = json.dumps(canonical, sort_keys=True)
        return hashlib.sha256(canonical_json.encode()).digest()

    def fingerprint_hex(self) -> str:
        """Compute fingerprint as hex string."""
        return self.fingerprint().hex()

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_canonical_dict(), indent=2)

    @classmethod
    def from_ppp_analysis(cls, analysis: Dict[str, Any], frame_id: int = 0) -> 'TelemetryFrame':
        """
        Create frame from SonicGeometryEngine.getAnalysis() output.

        Args:
            analysis: Output from engine.getAnalysis()
            frame_id: Sequential frame identifier
        """
        frame = cls(frame_id=frame_id)

        # Parse quaternion
        if "quaternion" in analysis:
            q = analysis["quaternion"]
            frame.quaternion_bridge = q.get("bridge", {})
            frame.left_angle = q.get("leftAngle", 0.0)
            frame.right_angle = q.get("rightAngle", 0.0)
            frame.bridge_magnitude = q.get("bridgeMagnitude", 1.0)

        # Parse spinor
        if "spinor" in analysis:
            s = analysis["spinor"]
            frame.spinor_ratios = s.get("ratios", [])
            frame.pan_lattice = s.get("panLattice", [])
            frame.phase_orbits = s.get("phaseOrbits", [])

        # Parse hopf fiber
        if "hopfFiber" in analysis:
            hf = analysis["hopfFiber"]
            frame.hopf_fiber = [hf.get("w", 1), hf.get("x", 0), hf.get("y", 0), hf.get("z", 0)]

        # Parse resonance
        if "resonance" in analysis:
            r = analysis["resonance"]
            frame.resonance_axes = r.get("axes", [])
            frame.carrier_embeddings = r.get("carriers", [])

        # Parse signal
        if "signal" in analysis:
            sig = analysis["signal"]
            frame.carrier_matrix = sig.get("carrierMatrix", [])
            frame.bitstream_hex = sig.get("bitstream", {}).get("hex", "")
            frame.spectral_centroid = sig.get("envelope", {}).get("spectralCentroid", 0)

        # Parse transduction
        if "transduction" in analysis:
            t = analysis["transduction"]
            frame.transduction_matrix = t.get("matrix", [])
            frame.transduction_determinant = t.get("determinant", 1.0)
            frame.frobenius_energy = t.get("frobeniusEnergy", 0)

        # Parse manifold
        if "manifold" in analysis:
            m = analysis["manifold"]
            frame.quaternion_trace = m.get("quaternionMetrics", {}).get("trace", 0)
            frame.spinor_coherence = m.get("spinorMetrics", {}).get("coherence", 1)
            frame.braid_density = m.get("spinorMetrics", {}).get("braidDensity", 0)

        # Parse topology
        if "topology" in analysis:
            top = analysis["topology"]
            frame.topology_axes = top.get("axes", [])
            frame.braid_analytics = top.get("braid", {})

        # Parse continuum
        if "continuum" in analysis:
            c = analysis["continuum"]
            frame.flux_density = c.get("fluxDensity", 0)
            frame.orientation_residual = c.get("orientationResidual", 0)

        # Parse lattice
        if "lattice" in analysis:
            lat = analysis["lattice"]
            frame.lattice_centroids = lat.get("centroids", [])

        # Parse constellation
        if "constellation" in analysis:
            con = analysis["constellation"]
            frame.constellation_nodes = con.get("nodes", [])

        return frame


class PPPStateSerializer:
    """
    Serializer for PPP telemetry streams.

    Maintains frame sequence and computes stream-level metrics.
    """

    def __init__(self, session_id: str = ""):
        self.session_id = session_id
        self.frames: List[TelemetryFrame] = []
        self._frame_counter = 0

    def add_frame(self, analysis: Dict[str, Any]) -> TelemetryFrame:
        """
        Add a new frame from PPP analysis.

        Returns the created TelemetryFrame.
        """
        frame = TelemetryFrame.from_ppp_analysis(analysis, self._frame_counter)
        self.frames.append(frame)
        self._frame_counter += 1
        return frame

    def get_frame(self, frame_id: int) -> Optional[TelemetryFrame]:
        """Get frame by ID."""
        for frame in self.frames:
            if frame.frame_id == frame_id:
                return frame
        return None

    def get_fingerprints(self) -> List[str]:
        """Get list of all frame fingerprints."""
        return [f.fingerprint_hex() for f in self.frames]

    def get_stream_hash(self) -> str:
        """Compute hash of entire frame stream."""
        fingerprints = self.get_fingerprints()
        combined = "".join(fingerprints)
        return hashlib.sha256(combined.encode()).hexdigest()

    def export_audit_log(self) -> Dict[str, Any]:
        """Export complete audit log."""
        return {
            "session_id": self.session_id,
            "frame_count": len(self.frames),
            "stream_hash": self.get_stream_hash(),
            "frames": [f.to_canonical_dict() for f in self.frames],
        }

    def export_audit_log_json(self) -> str:
        """Export audit log as JSON."""
        return json.dumps(self.export_audit_log(), indent=2)

    def compute_drift_metrics(self) -> Dict[str, float]:
        """Compute drift metrics across frame stream."""
        if len(self.frames) < 2:
            return {"coherence_drift": 0.0, "quaternion_drift": 0.0}

        coherences = [f.spinor_coherence for f in self.frames]
        coherence_drift = max(coherences) - min(coherences)

        angles = [(f.left_angle, f.right_angle) for f in self.frames]
        angle_diffs = [
            abs(angles[i][0] - angles[i-1][0]) + abs(angles[i][1] - angles[i-1][1])
            for i in range(1, len(angles))
        ]
        quaternion_drift = max(angle_diffs) if angle_diffs else 0.0

        return {
            "coherence_drift": coherence_drift,
            "quaternion_drift": quaternion_drift,
            "mean_coherence": np.mean(coherences),
            "coherence_std": np.std(coherences),
        }
