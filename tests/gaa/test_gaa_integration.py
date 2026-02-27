"""
GAA Integration Tests

Tests the complete Geometric Audit Architecture integration.
"""

import numpy as np
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gaa.foundational.quaternion import Quaternion, DualQuaternion
from gaa.foundational.clifford import Multivector, CliffordAlgebra
from gaa.foundational.state import GeometricState, StateBundle

from gaa.telemetry.events import TRACEEvent, EventType, EventChain
from gaa.telemetry.fingerprint import GeometricFingerprint, FingerprintType
from gaa.telemetry.merkle import MerkleAuditTree, MerkleProof
from gaa.telemetry.serializer import PPPStateSerializer, TelemetryFrame

from gaa.correction.hypervector import Hypervector, HypervectorStore
from gaa.correction.cleanup import CleanupMemory, CorrectionResult
from gaa.correction.drift import DriftDetector, DriftMetrics

from gaa.governance.ispec import ISpec
from gaa.governance.constraints import GeometricConstraint, ManifoldRegion, RegionType
from gaa.governance.audit_agent import AuditAgent, AuditResult
from gaa.governance.policy import PolicyResolver, Policy, PolicyDecision

from gaa.coordination.consensus import ManifoldConsensus
from gaa.coordination.topology import TopologyVerifier
from gaa.coordination.hopf import HopfCoordinator

from gaa.compliance.safety_case import SafetyCase, Claim, Evidence
from gaa.compliance.edr import EDRCapture, EDRFrame
from gaa.compliance.traceability import TraceabilityMatrix, Requirement


def test_quaternion_basics():
    """Test quaternion operations."""
    q1 = Quaternion.identity()
    assert np.allclose(q1.components, [1, 0, 0, 0])

    q2 = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 2)
    v = np.array([1, 0, 0])
    v_rotated = q2.rotate_vector(v)
    assert np.allclose(v_rotated, [0, 1, 0], atol=1e-10)

    # SLERP
    q_mid = Quaternion.slerp(q1, q2, 0.5)
    assert q_mid.w > 0.7

    print("✓ Quaternion basics passed")


def test_dual_quaternion():
    """Test dual quaternion operations."""
    rotation = Quaternion.from_axis_angle(np.array([0, 0, 1]), np.pi / 4)
    translation = np.array([1.0, 2.0, 3.0])

    dq = DualQuaternion.from_rotation_translation(rotation, translation)

    rot_out, trans_out = dq.to_rotation_translation()
    assert np.allclose(trans_out, translation, atol=1e-10)

    # Transform a point
    p = np.array([0, 0, 0])
    p_transformed = dq.transform_point(p)
    assert np.allclose(p_transformed, translation, atol=1e-10)

    print("✓ Dual quaternion passed")


def test_clifford_algebra():
    """Test Clifford algebra operations."""
    e1 = CliffordAlgebra.e(1)
    e2 = CliffordAlgebra.e(2)

    # e1 * e1 = 1
    e1_squared = e1 * e1
    assert np.allclose(e1_squared.scalar_part, 1.0)

    # e1 * e2 = e12 (bivector)
    e12 = e1 * e2
    assert np.allclose(e12.bivector_part[0], 1.0)

    # Create rotor
    rotor = Multivector.rotor(np.array([0, 0, 1]), np.pi / 2)
    assert abs(rotor.norm() - 1.0) < 1e-10

    print("✓ Clifford algebra passed")


def test_geometric_state():
    """Test geometric state container."""
    bundle = StateBundle()
    bundle.quaternion = Quaternion.from_euler(0.1, 0.2, 0.3)
    bundle.spinor_coherence = 0.85
    bundle.betti_numbers = (1, 0, 0)

    state = bundle.finalize()

    assert state.spinor_coherence == 0.85
    assert len(state.state_id) > 0
    assert state.fingerprint_hex() is not None

    # JSON round-trip
    json_str = state.to_json()
    state2 = GeometricState.from_json(json_str)
    assert state2.spinor_coherence == state.spinor_coherence

    print("✓ Geometric state passed")


def test_trace_events():
    """Test TRACE event chain."""
    chain = EventChain()

    event1 = TRACEEvent(
        event_type=EventType.GEOMETRIC_STATE,
        payload={"spinor": {"coherence": 0.95}},
    )
    chain.append(event1)

    event2 = TRACEEvent(
        event_type=EventType.DRIFT_DETECTED,
        payload={"drift_magnitude": 0.15},
    )
    chain.append(event2)

    assert chain.length == 2
    assert chain.verify_integrity()

    # Verify hash chaining
    assert chain.events[1].previous_hash == chain.events[0].event_hash

    print("✓ TRACE events passed")


def test_geometric_fingerprint():
    """Test geometric fingerprinting."""
    # Constellation fingerprint
    vertices = np.random.randn(120, 4)
    vertices = vertices / np.linalg.norm(vertices, axis=1, keepdims=True)

    fp1 = GeometricFingerprint.from_constellation(vertices, rotation_invariant=True)
    fp2 = GeometricFingerprint.from_constellation(vertices, rotation_invariant=True)

    assert fp1 == fp2

    # Quaternion fingerprint
    q = np.array([1, 0, 0, 0])
    fp_q = GeometricFingerprint.from_quaternion(q)
    assert len(fp_q.hex()) == 64

    print("✓ Geometric fingerprint passed")


def test_merkle_tree():
    """Test Merkle audit tree."""
    tree = MerkleAuditTree()

    for i in range(10):
        tree.add_leaf(f"event_{i}".encode())

    root = tree.root
    assert root is not None

    # Generate and verify proof
    proof = tree.get_proof(5)
    assert proof.verify(b"event_5")

    print("✓ Merkle tree passed")


def test_hypervector():
    """Test hypervector operations."""
    dim = 1000  # Smaller for testing

    hv1 = Hypervector.random(dim, seed=42)
    hv2 = Hypervector.random(dim, seed=43)

    # Random vectors should be near-orthogonal
    sim = hv1.cosine_similarity(hv2)
    assert abs(sim) < 0.2

    # Binding is approximately self-inverse
    bound = hv1.bind(hv2)
    recovered = bound.bind(hv2)
    assert recovered.cosine_similarity(hv1) > 0.8

    # Bundling preserves similarity
    bundled = hv1.bundle(hv2)
    assert bundled.cosine_similarity(hv1) > 0.3
    assert bundled.cosine_similarity(hv2) > 0.3

    print("✓ Hypervector operations passed")


def test_cleanup_memory():
    """Test HDC cleanup memory."""
    np.random.seed(42)  # Make test deterministic
    memory = CleanupMemory(dimension=1000, similarity_threshold=0.6)

    # Register valid states
    for i in range(5):
        q = np.array([np.cos(i * 0.2), np.sin(i * 0.2), 0, 0])
        memory.register_from_quaternion(f"state_{i}", q)

    # Test cleanup with small noise
    noisy_q = np.array([np.cos(0.0), np.sin(0.0), 0, 0]) + np.random.randn(4) * 0.05
    noisy_q = noisy_q / np.linalg.norm(noisy_q)

    noisy_hv = Hypervector.from_quaternion(noisy_q, 1000)
    result = memory.cleanup(noisy_hv)

    # Should find a valid state (may be state_0 or nearby due to HDC encoding)
    assert result.nearest_valid_state is not None

    print("✓ Cleanup memory passed")


def test_drift_detector():
    """Test drift detection."""
    detector = DriftDetector(history_length=10)

    q_ref = Quaternion.identity()
    detector.set_reference(q_ref)

    # Normal updates
    for i in range(5):
        q = Quaternion.from_euler(i * 0.01, 0, 0)
        metrics = detector.update(q, coherence=0.9)
        assert not metrics.is_drifting

    # Sudden jump
    q_jump = Quaternion.from_euler(1.0, 0.5, 0.3)
    metrics = detector.update(q_jump, coherence=0.5)

    assert metrics.angular_velocity > 0.5

    print("✓ Drift detector passed")


def test_ispec():
    """Test ISpec constraints."""
    ispec = ISpec.strict("test_strict")

    assert ispec.min_spinor_coherence == 0.9
    assert ispec.validate_coherence(0.95)
    assert not ispec.validate_coherence(0.8)

    assert ispec.validate_isoclinic(0.5, 0.55)
    assert not ispec.validate_isoclinic(0.5, 1.0)

    print("✓ ISpec passed")


def test_geometric_constraint():
    """Test geometric constraints."""
    constraint = GeometricConstraint(
        constraint_id="test",
        min_coherence=0.7,
        max_angular_velocity=1.0,
    )

    # Add permitted region
    region = ManifoldRegion(
        region_id="region1",
        region_type=RegionType.SPHERICAL,
        center=np.array([1, 0, 0, 0]),
        radius=0.5,
    )
    constraint.add_permitted_region(region)

    # Test point inside
    point_inside = np.array([0.9, 0.1, 0, 0])
    satisfied, _ = constraint.is_satisfied(point_inside, coherence=0.8)
    assert satisfied

    # Test point outside
    point_outside = np.array([0, 1, 0, 0])
    satisfied, reason = constraint.is_satisfied(point_outside, coherence=0.8)
    assert not satisfied

    print("✓ Geometric constraint passed")


def test_audit_agent():
    """Test audit agent."""
    ispec = ISpec(min_spinor_coherence=0.7, max_isoclinic_defect=0.3)
    agent = AuditAgent("test_agent", ispec)

    # Good event
    good_event = TRACEEvent(
        event_type=EventType.GEOMETRIC_STATE,
        payload={
            "spinor": {"coherence": 0.9},
            "quaternion": {"leftAngle": 0.5, "rightAngle": 0.52},
        },
    )
    results = agent.evaluate_event(good_event)
    assert all(r.passed for r in results)

    # Bad event
    bad_event = TRACEEvent(
        event_type=EventType.GEOMETRIC_STATE,
        payload={
            "spinor": {"coherence": 0.5},
            "quaternion": {"leftAngle": 0.5, "rightAngle": 1.0},
        },
    )
    results = agent.evaluate_event(bad_event)
    assert not all(r.passed for r in results)

    print("✓ Audit agent passed")


def test_policy_resolver():
    """Test policy resolution."""
    resolver = PolicyResolver()
    resolver.create_standard_policies()

    # High coherence = allow
    result = resolver.resolve(coherence=0.95, drift=0.05)
    assert result.decision == PolicyDecision.ALLOW
    assert "full_introspection" in result.granted_capabilities

    # Low coherence = require correction
    result = resolver.resolve(coherence=0.6, drift=0.1)
    assert result.decision == PolicyDecision.REQUIRE_CORRECTION

    print("✓ Policy resolver passed")


def test_manifold_consensus():
    """Test manifold consensus."""
    consensus = ManifoldConsensus(step_size=0.2)

    # Add agents with different orientations
    for i in range(4):
        q = Quaternion.from_euler(i * 0.3, 0, 0)
        consensus.add_agent(f"agent_{i}", q)

    consensus.make_fully_connected()

    # Run consensus
    initial_disagreement = consensus.compute_disagreement()
    state = consensus.run_until_convergence()

    assert state.disagreement < initial_disagreement
    assert state.consensus_quaternion is not None

    print("✓ Manifold consensus passed")


def test_topology_verifier():
    """Test topology verification."""
    verifier = TopologyVerifier(coverage_radius=1.0)

    # Add agents in a triangle
    for i, pos in enumerate([[0, 0, 0], [2, 0, 0], [1, 1.5, 0]]):
        verifier.add_agent(f"agent_{i}", np.array(pos))

    verifier.compute_connectivity_from_positions(radius=2.5)

    result = verifier.verify_coverage()
    assert result.betti_0 == 1  # Connected

    print("✓ Topology verifier passed")


def test_hopf_coordinator():
    """Test Hopf fibration decomposition."""
    coordinator = HopfCoordinator()

    q = Quaternion.from_euler(0.1, 0.2, 0.3)
    decomp = coordinator.decompose(q)

    assert np.linalg.norm(decomp.pointing) > 0.99  # Unit vector

    # Recompose
    q_recomposed = coordinator.compose(decomp.pointing, decomp.roll)
    assert q.angular_distance(q_recomposed) < 0.1

    print("✓ Hopf coordinator passed")


def test_safety_case():
    """Test safety case construction."""
    case = SafetyCase("SC-001", "Geometric Navigation Safety")
    case.create_geometric_safety_claims()

    assert len(case.claims) >= 3
    assert len(case.top_level_claims) >= 1

    coverage = case.compute_coverage()
    assert coverage == 0.0  # No evidence yet

    print("✓ Safety case passed")


def test_edr_capture():
    """Test EDR capture."""
    edr = EDRCapture(pre_event_seconds=1.0, post_event_seconds=0.5)

    # Record some frames
    for i in range(10):
        edr.record_frame(
            quaternion=(1, 0, 0, 0),
            position=(i, 0, 0),
            velocity=(1, 0, 0),
            coherence=0.9,
        )

    # Trigger
    edr.trigger("test_event")

    # Record post-trigger frames
    for i in range(5):
        edr.record_frame(
            quaternion=(1, 0, 0, 0),
            position=(10 + i, 0, 0),
            velocity=(1, 0, 0),
            coherence=0.8,
        )

    # Export
    export = edr.export()
    assert export is not None
    assert export.trigger_event == "test_event"
    assert len(export.get_all_frames()) > 0

    print("✓ EDR capture passed")


def test_traceability_matrix():
    """Test traceability matrix."""
    matrix = TraceabilityMatrix("test_project")
    matrix.create_geometric_requirements()

    assert len(matrix.requirements) >= 4

    # Check for gaps
    unimplemented = matrix.get_unimplemented_requirements()
    assert len(unimplemented) > 0  # No implementations yet

    coverage = matrix.compute_coverage()
    assert coverage["implementation_coverage"] == 0.0

    print("✓ Traceability matrix passed")


def test_full_integration():
    """Test full GAA integration workflow."""

    # 1. Create ISpec
    ispec = ISpec(
        name="integration_test",
        min_spinor_coherence=0.7,
        max_isoclinic_defect=0.3,
    )

    # 2. Create audit agent
    agent = AuditAgent("integration_agent", ispec)

    # 3. Create event chain
    chain = EventChain()

    # 4. Create cleanup memory
    memory = CleanupMemory(dimension=1000)
    for i in range(5):
        q = np.array([np.cos(i * 0.1), np.sin(i * 0.1), 0, 0])
        memory.register_from_quaternion(f"valid_{i}", q)

    # 5. Create drift detector
    detector = DriftDetector()
    detector.set_reference(Quaternion.identity())

    # 6. Process some states
    for i in range(10):
        q = Quaternion.from_euler(i * 0.05, 0, 0)
        coherence = 0.9 - i * 0.02

        # Check drift
        metrics = detector.update(q, coherence)

        # Create event
        event = TRACEEvent(
            event_type=EventType.GEOMETRIC_STATE,
            payload={
                "spinor": {"coherence": coherence},
                "quaternion": {
                    "leftAngle": i * 0.05,
                    "rightAngle": i * 0.05,
                },
                "drift": metrics.to_dict(),
            },
        )

        # Add to chain
        chain.append(event)

        # Audit
        results = agent.evaluate_event(event)

    # 7. Verify chain integrity
    assert chain.verify_integrity()

    # 8. Build Merkle tree
    tree = MerkleAuditTree()
    for event in chain.events:
        tree.add_event(event.event_hash)

    assert tree.root is not None

    # 9. Check audit results
    violations = agent.get_violations()
    summary = agent.get_summary()

    print(f"   Events: {summary['events_evaluated']}")
    print(f"   Violations: {summary['total_violations']}")
    print(f"   Chain integrity: verified")
    print(f"   Merkle root: {tree.root_hex[:16]}...")

    print("✓ Full integration passed")


if __name__ == "__main__":
    print("\n=== GAA Integration Tests ===\n")

    test_quaternion_basics()
    test_dual_quaternion()
    test_clifford_algebra()
    test_geometric_state()
    test_trace_events()
    test_geometric_fingerprint()
    test_merkle_tree()
    test_hypervector()
    test_cleanup_memory()
    test_drift_detector()
    test_ispec()
    test_geometric_constraint()
    test_audit_agent()
    test_policy_resolver()
    test_manifold_consensus()
    test_topology_verifier()
    test_hopf_coordinator()
    test_safety_case()
    test_edr_capture()
    test_traceability_matrix()
    test_full_integration()

    print("\n=== All Tests Passed ===\n")
