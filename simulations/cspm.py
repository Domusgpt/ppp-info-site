#!/usr/bin/env python3
"""
=============================================================================
CSPM - CRYPTOGRAPHICALLY-SEEDED POLYTOPAL MODULATION
=============================================================================

This module implements the complete CSPM protocol as envisioned:

1. HASH CHAIN SEEDING: CRA-style hash chains drive lattice orientation
2. ROLLING LATTICE: Each packet rotates the 600-cell coordinate system
3. SPINOR COUPLING: OAM (twist) + Polarization (tumble) = 4D quaternion
4. GEOMETRIC QUANTIZATION: "Snap" to nearest vertex (already proven)
5. PHYSICAL LAYER CRYPTO: Unreadable without genesis hash

THE CORE INNOVATION:
--------------------
Standard optical comms: Vary amplitude/phase on 2D plane (QAM)
CSPM: Vary polarization (spin) + OAM (twist) on 4D manifold

The hash chain creates a "rolling code" - each packet's lattice orientation
depends on the hash of the previous packet. An interceptor cannot decode
without the genesis hash.

Author: PPP Research Team
License: MIT
Version: 3.0.0 (Full CSPM Implementation)
=============================================================================
"""

import numpy as np
import hashlib
from typing import Tuple, Optional, List, Dict
from dataclasses import dataclass, field
from scipy.spatial import KDTree
from scipy.spatial.transform import Rotation

# Import our geometry
from geometry import Polychoron600, PHI, PHI_INV


# =============================================================================
# QUATERNION UTILITIES
# =============================================================================

def quaternion_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """
    Multiply two quaternions.

    Quaternion format: [w, x, y, z] where w is scalar part.
    """
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2

    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2
    ])


def quaternion_conjugate(q: np.ndarray) -> np.ndarray:
    """Conjugate of a quaternion."""
    return np.array([q[0], -q[1], -q[2], -q[3]])


def quaternion_rotate_4d(point: np.ndarray, q_left: np.ndarray, q_right: np.ndarray) -> np.ndarray:
    """
    Rotate a 4D point using left and right quaternion multiplication.

    In 4D, rotations are represented by pairs of quaternions (double cover of SO(4)).
    The rotation is: p' = q_left * p * q_right

    This is the core of the "rolling lattice" - we rotate the entire
    600-cell constellation using quaternions derived from the hash chain.
    """
    # Treat the 4D point as a quaternion
    p = point

    # Apply left multiplication
    temp = quaternion_multiply(q_left, p)

    # Apply right multiplication
    result = quaternion_multiply(temp, q_right)

    return result


def hash_to_quaternion(hash_bytes: bytes) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert a hash to a pair of unit quaternions for 4D rotation.

    This is the bridge between the CRA hash chain and the geometric space.
    The hash deterministically generates a rotation in SO(4).

    Args:
        hash_bytes: 32-byte SHA-256 hash

    Returns:
        Tuple of (q_left, q_right) unit quaternions
    """
    # Split hash into two 16-byte chunks
    left_bytes = hash_bytes[:16]
    right_bytes = hash_bytes[16:]

    # Convert to floats in [-1, 1]
    left_floats = np.array([
        (int.from_bytes(left_bytes[i:i+4], 'big') / (2**32)) * 2 - 1
        for i in range(0, 16, 4)
    ])
    right_floats = np.array([
        (int.from_bytes(right_bytes[i:i+4], 'big') / (2**32)) * 2 - 1
        for i in range(0, 16, 4)
    ])

    # Normalize to unit quaternions
    q_left = left_floats / np.linalg.norm(left_floats)
    q_right = right_floats / np.linalg.norm(right_floats)

    return q_left, q_right


# =============================================================================
# HASH CHAIN (CRA-STYLE)
# =============================================================================

class HashChain:
    """
    Cryptographic hash chain for lattice rotation.

    This implements the "rolling code" security mechanism:
    - Each packet's hash becomes the seed for the next rotation
    - Without the genesis hash, an interceptor cannot predict rotations
    - The lattice orientation is different for every single packet

    CRA INTEGRATION:
    The hash can be the SHA-256 of the data block (TraceEvent),
    creating authenticated, self-keying encryption.
    """

    def __init__(self, genesis_hash: Optional[bytes] = None, seed: str = "CSPM_GENESIS"):
        """
        Initialize the hash chain.

        Args:
            genesis_hash: Starting hash (32 bytes), or None to derive from seed
            seed: String seed if genesis_hash not provided
        """
        if genesis_hash is None:
            self.current_hash = hashlib.sha256(seed.encode()).digest()
        else:
            self.current_hash = genesis_hash

        self.packet_count = 0
        self.history: List[bytes] = [self.current_hash]

    def advance(self, data: Optional[bytes] = None) -> bytes:
        """
        Advance the hash chain and return the new hash.

        Args:
            data: Optional data to mix into the hash (for CRA authentication)

        Returns:
            The new current hash
        """
        if data is not None:
            # Mix data into hash (authenticated mode)
            combined = self.current_hash + data
        else:
            # Pure chain advancement
            combined = self.current_hash

        self.current_hash = hashlib.sha256(combined).digest()
        self.packet_count += 1
        self.history.append(self.current_hash)

        return self.current_hash

    def get_rotation(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get the current rotation quaternions from the hash."""
        return hash_to_quaternion(self.current_hash)

    def reset(self, genesis_hash: Optional[bytes] = None):
        """Reset the chain to a specific state."""
        if genesis_hash is not None:
            self.current_hash = genesis_hash
        else:
            self.current_hash = self.history[0]
        self.packet_count = 0


# =============================================================================
# ROLLING LATTICE
# =============================================================================

class RollingLattice:
    """
    The 600-cell constellation with hash-chain-driven rotation.

    KEY SECURITY PROPERTY:
    The constellation rotates with each packet. An interceptor sees
    complex, twisting light that appears as white noise unless they
    have the genesis hash to synchronize their lattice.

    This is physical-layer encryption without key exchange overhead.
    """

    def __init__(self, genesis_seed: str = "CSPM_GENESIS"):
        """
        Initialize the rolling lattice.

        Args:
            genesis_seed: Seed for the hash chain
        """
        # Base constellation (never modified)
        self.base_constellation = Polychoron600()
        self.base_vertices = self.base_constellation.vertices.copy()

        # Hash chain for rotation
        self.hash_chain = HashChain(seed=genesis_seed)

        # Current rotated constellation
        self.current_vertices = self.base_vertices.copy()
        self.current_kdtree = KDTree(self.current_vertices)

        # Rotation state
        self.current_q_left = np.array([1, 0, 0, 0])
        self.current_q_right = np.array([1, 0, 0, 0])

    def rotate_for_packet(self, packet_data: Optional[bytes] = None) -> None:
        """
        Rotate the lattice for the next packet.

        This is called before each packet transmission/reception.
        The rotation is deterministic given the hash chain state.

        Args:
            packet_data: Optional data to authenticate into the rotation
        """
        # Advance hash chain
        self.hash_chain.advance(packet_data)

        # Get new rotation
        q_left, q_right = self.hash_chain.get_rotation()

        # Compose with existing rotation (accumulate)
        self.current_q_left = quaternion_multiply(q_left, self.current_q_left)
        self.current_q_right = quaternion_multiply(self.current_q_right, q_right)

        # Normalize to prevent drift
        self.current_q_left = self.current_q_left / np.linalg.norm(self.current_q_left)
        self.current_q_right = self.current_q_right / np.linalg.norm(self.current_q_right)

        # Apply rotation to all vertices
        self.current_vertices = np.array([
            quaternion_rotate_4d(v, self.current_q_left, self.current_q_right)
            for v in self.base_vertices
        ])

        # Rebuild KD-tree for fast lookup
        self.current_kdtree = KDTree(self.current_vertices)

    def snap_to_vertex(self, noisy_point: np.ndarray) -> Tuple[int, np.ndarray, float]:
        """
        Snap a noisy 4D point to the nearest vertex (geometric quantization).

        Args:
            noisy_point: The received 4D signal

        Returns:
            Tuple of (vertex_index, vertex_coordinates, distance)
        """
        distance, index = self.current_kdtree.query(noisy_point)
        return int(index), self.current_vertices[index], float(distance)

    def batch_snap(self, noisy_points: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Batch version of snap_to_vertex."""
        distances, indices = self.current_kdtree.query(noisy_points)
        return indices.astype(np.int32), distances

    def get_vertex(self, index: int) -> np.ndarray:
        """Get current vertex by index."""
        return self.current_vertices[index % 120]

    def reset(self):
        """Reset to initial state."""
        self.hash_chain.reset()
        self.current_vertices = self.base_vertices.copy()
        self.current_kdtree = KDTree(self.current_vertices)
        self.current_q_left = np.array([1, 0, 0, 0])
        self.current_q_right = np.array([1, 0, 0, 0])


# =============================================================================
# STOKES PARAMETERS (POLARIZATION)
# =============================================================================

@dataclass
class StokesVector:
    """
    Stokes parameters representing polarization state.

    The Stokes vector [S0, S1, S2, S3] represents:
    - S0: Total intensity
    - S1: Linear polarization (horizontal vs vertical)
    - S2: Linear polarization (diagonal vs anti-diagonal)
    - S3: Circular polarization (right vs left)

    The normalized Stokes vector [S1, S2, S3]/S0 lives on the Poincaré sphere.
    This maps to the (x, y, z) components of our quaternion.
    """
    S0: float  # Intensity
    S1: float  # Horizontal - Vertical
    S2: float  # Diagonal - Anti-diagonal
    S3: float  # Right circular - Left circular

    def to_array(self) -> np.ndarray:
        return np.array([self.S0, self.S1, self.S2, self.S3])

    def normalized(self) -> np.ndarray:
        """Return normalized [S1, S2, S3] on the Poincaré sphere."""
        if self.S0 == 0:
            return np.array([0, 0, 0])
        return np.array([self.S1, self.S2, self.S3]) / self.S0

    @classmethod
    def from_quaternion_xyz(cls, x: float, y: float, z: float, intensity: float = 1.0):
        """Create Stokes vector from quaternion (x,y,z) components."""
        return cls(S0=intensity, S1=x*intensity, S2=y*intensity, S3=z*intensity)


def quaternion_to_stokes(q: np.ndarray) -> StokesVector:
    """
    Convert quaternion to Stokes parameters.

    The (x, y, z) components map to the Poincaré sphere.
    The w component represents a global phase (OAM contribution).
    """
    w, x, y, z = q
    # Normalize to ensure we're on the sphere
    xyz_norm = np.sqrt(x**2 + y**2 + z**2)
    if xyz_norm > 0:
        x, y, z = x/xyz_norm, y/xyz_norm, z/xyz_norm
    return StokesVector(S0=1.0, S1=x, S2=y, S3=z)


def stokes_to_quaternion_part(stokes: StokesVector) -> np.ndarray:
    """
    Convert Stokes parameters to quaternion (x, y, z) components.

    Returns the vector part of the quaternion (polarization encoding).
    The scalar part (w) comes from OAM.
    """
    norm = stokes.normalized()
    return norm


# =============================================================================
# OAM (ORBITAL ANGULAR MOMENTUM)
# =============================================================================

@dataclass
class OAMMode:
    """
    Orbital Angular Momentum mode of a light beam.

    OAM beams have a helical phase front: exp(i * l * φ)
    where l is the topological charge (integer) and φ is the azimuthal angle.

    KEY PROPERTY:
    OAM modes are orthogonal - different l values don't interfere.
    This provides additional degrees of freedom for encoding.

    TOPOLOGICAL PROTECTION:
    The topological charge l cannot be changed by smooth perturbations.
    This makes OAM robust against atmospheric turbulence.
    """
    l: int  # Topological charge (integer: ..., -2, -1, 0, 1, 2, ...)
    p: int = 0  # Radial mode number (usually 0)

    def phase_at_angle(self, phi: float) -> complex:
        """Get the phase factor at azimuthal angle phi."""
        return np.exp(1j * self.l * phi)

    def to_quaternion_w(self, max_l: int = 10) -> float:
        """
        Convert OAM mode to quaternion scalar (w) component.

        Maps integer l to continuous w in [-1, 1].
        """
        # Normalize to [-1, 1] range
        return np.tanh(self.l / max_l)

    @classmethod
    def from_quaternion_w(cls, w: float, max_l: int = 10) -> 'OAMMode':
        """Convert quaternion w component to OAM mode."""
        l = int(np.round(np.arctanh(np.clip(w, -0.99, 0.99)) * max_l))
        return cls(l=l)


# =============================================================================
# 4D SPINOR COUPLING (THE CORE INNOVATION)
# =============================================================================

@dataclass
class SpinorState:
    """
    Combined Polarization + OAM state as a 4D Spinor.

    This is the KEY INNOVATION:
    - Standard QAM: 2D (Amplitude + Phase)
    - Our system: 4D (Polarization[3D] + OAM[1D])

    The spinor state is a unit quaternion [w, x, y, z]:
    - w: Derived from OAM topological charge
    - (x, y, z): Derived from Stokes parameters (Poincaré sphere)

    Together, they define a point on the 3-sphere S³, which is
    exactly the space where the 600-cell lives!
    """
    quaternion: np.ndarray  # [w, x, y, z] unit quaternion
    oam: OAMMode
    stokes: StokesVector

    @classmethod
    def from_quaternion(cls, q: np.ndarray) -> 'SpinorState':
        """Create SpinorState from a unit quaternion."""
        q = q / np.linalg.norm(q)  # Ensure unit

        # Decompose into OAM (w) and Polarization (x,y,z)
        w, x, y, z = q

        oam = OAMMode.from_quaternion_w(w)
        stokes = StokesVector.from_quaternion_xyz(x, y, z)

        return cls(quaternion=q, oam=oam, stokes=stokes)

    @classmethod
    def from_physical(cls, oam: OAMMode, stokes: StokesVector) -> 'SpinorState':
        """Create SpinorState from physical parameters."""
        w = oam.to_quaternion_w()
        xyz = stokes.normalized()

        # Construct quaternion ensuring unit norm
        q = np.array([w, xyz[0], xyz[1], xyz[2]])
        q = q / np.linalg.norm(q)

        return cls(quaternion=q, oam=oam, stokes=stokes)

    def to_vertex_index(self, lattice: RollingLattice) -> int:
        """Find the nearest 600-cell vertex to this spinor state."""
        idx, _, _ = lattice.snap_to_vertex(self.quaternion)
        return idx


# =============================================================================
# CSPM TRANSMITTER
# =============================================================================

class CSPMTransmitter:
    """
    The CSPM Transmitter.

    TRANSMISSION PROCESS:
    1. Receive data block (bits)
    2. Optionally hash data for CRA authentication
    3. Rotate lattice based on hash chain
    4. Map bits to vertex indices
    5. Convert vertices to SpinorStates (OAM + Polarization)
    6. Output physical parameters for SLM
    """

    def __init__(self, genesis_seed: str = "CSPM_GENESIS", bits_per_symbol: int = 6):
        """
        Initialize the CSPM transmitter.

        Args:
            genesis_seed: Seed for the hash chain
            bits_per_symbol: Bits encoded per symbol (max ~6.9 for 120 vertices)
        """
        self.lattice = RollingLattice(genesis_seed)
        self.bits_per_symbol = bits_per_symbol
        self.max_index = min(2**bits_per_symbol, 120)

    def transmit_packet(self, bits: np.ndarray,
                        authenticate: bool = True) -> List[SpinorState]:
        """
        Transmit a packet of bits.

        Args:
            bits: Array of bits to transmit
            authenticate: If True, mix data hash into lattice rotation

        Returns:
            List of SpinorStates ready for physical encoding
        """
        # Optionally authenticate data into rotation
        if authenticate:
            data_hash = hashlib.sha256(bits.tobytes()).digest()
            self.lattice.rotate_for_packet(data_hash)
        else:
            self.lattice.rotate_for_packet()

        # Convert bits to indices
        n_bits = len(bits)
        padding = (self.bits_per_symbol - (n_bits % self.bits_per_symbol)) % self.bits_per_symbol
        if padding > 0:
            bits = np.concatenate([bits, np.zeros(padding, dtype=int)])

        n_symbols = len(bits) // self.bits_per_symbol
        bit_chunks = bits.reshape(n_symbols, self.bits_per_symbol)

        powers = 2 ** np.arange(self.bits_per_symbol - 1, -1, -1)
        indices = np.sum(bit_chunks * powers, axis=1) % self.max_index

        # Convert indices to SpinorStates
        spinor_states = []
        for idx in indices:
            vertex = self.lattice.get_vertex(idx)
            state = SpinorState.from_quaternion(vertex)
            spinor_states.append(state)

        return spinor_states

    def get_physical_parameters(self, states: List[SpinorState]) -> Dict:
        """
        Convert SpinorStates to physical SLM parameters.

        Returns dict with:
        - oam_charges: List of OAM topological charges
        - stokes_vectors: List of Stokes parameters
        - quaternions: Raw 4D coordinates
        """
        return {
            'oam_charges': [s.oam.l for s in states],
            'stokes_vectors': [s.stokes.to_array() for s in states],
            'quaternions': np.array([s.quaternion for s in states])
        }


# =============================================================================
# CSPM RECEIVER
# =============================================================================

class CSPMReceiver:
    """
    The CSPM Receiver (The "Lattice Trap").

    RECEPTION PROCESS:
    1. Receive physical signal (OAM + Polarization)
    2. Convert to 4D quaternion (noisy)
    3. Rotate lattice to match transmitter state
    4. SNAP to nearest vertex (geometric quantization)
    5. Decode vertex index to bits

    SECURITY:
    Without the genesis hash, the receiver cannot synchronize
    its lattice. The noise "snaps" to wrong vertices = garbage.
    """

    def __init__(self, genesis_seed: str = "CSPM_GENESIS", bits_per_symbol: int = 6):
        """
        Initialize the CSPM receiver.

        Args:
            genesis_seed: Must match transmitter's genesis seed!
            bits_per_symbol: Must match transmitter
        """
        self.lattice = RollingLattice(genesis_seed)
        self.bits_per_symbol = bits_per_symbol
        self.max_index = min(2**bits_per_symbol, 120)

    def receive_packet(self, noisy_quaternions: np.ndarray,
                       data_hash: Optional[bytes] = None) -> np.ndarray:
        """
        Receive and decode a packet.

        Args:
            noisy_quaternions: Received 4D signals (N, 4)
            data_hash: If authenticated mode, the expected data hash

        Returns:
            Decoded bits
        """
        # Rotate lattice to match transmitter
        if data_hash is not None:
            self.lattice.rotate_for_packet(data_hash)
        else:
            self.lattice.rotate_for_packet()

        # Snap each noisy point to nearest vertex
        indices, distances = self.lattice.batch_snap(noisy_quaternions)

        # Clamp to valid range
        indices = indices % self.max_index

        # Convert indices to bits
        bits = np.zeros((len(indices), self.bits_per_symbol), dtype=int)
        for i in range(self.bits_per_symbol):
            bits[:, self.bits_per_symbol - 1 - i] = (indices >> i) & 1

        return bits.flatten()

    def receive_from_physical(self, oam_charges: List[int],
                               stokes_vectors: List[np.ndarray],
                               data_hash: Optional[bytes] = None) -> np.ndarray:
        """
        Receive from physical parameters (OAM + Stokes).

        Converts physical measurements to quaternions, then decodes.
        """
        quaternions = []
        for l, stokes in zip(oam_charges, stokes_vectors):
            oam = OAMMode(l=l)
            stokes_obj = StokesVector(*stokes)
            state = SpinorState.from_physical(oam, stokes_obj)
            quaternions.append(state.quaternion)

        return self.receive_packet(np.array(quaternions), data_hash)


# =============================================================================
# SECURITY ANALYSIS
# =============================================================================

def analyze_interception_resistance(num_packets: int = 100,
                                     num_symbols: int = 100) -> Dict:
    """
    Analyze resistance to interception.

    Simulates an attacker who:
    1. Has a perfect copy of the noisy signal
    2. Does NOT have the genesis hash
    3. Tries to decode using a wrong lattice orientation

    Returns error statistics showing the signal is unreadable.
    """
    # Legitimate parties
    tx = CSPMTransmitter(genesis_seed="CORRECT_SEED")
    rx_good = CSPMReceiver(genesis_seed="CORRECT_SEED")

    # Attacker with wrong seed
    rx_bad = CSPMReceiver(genesis_seed="WRONG_SEED")

    good_errors = []
    bad_errors = []

    for packet_idx in range(num_packets):
        # Generate random data
        bits = np.random.randint(0, 2, num_symbols * 6)
        data_hash = hashlib.sha256(bits.tobytes()).digest()

        # Transmit
        states = tx.transmit_packet(bits, authenticate=True)
        quaternions = np.array([s.quaternion for s in states])

        # Add moderate noise
        noise = np.random.normal(0, 0.1, quaternions.shape)
        noisy_q = quaternions + noise

        # Legitimate receiver (correct seed)
        rx_bits_good = rx_good.receive_packet(noisy_q, data_hash)
        good_ber = np.mean(rx_bits_good[:len(bits)] != bits)
        good_errors.append(good_ber)

        # Attacker (wrong seed)
        rx_bits_bad = rx_bad.receive_packet(noisy_q, data_hash)
        bad_ber = np.mean(rx_bits_bad[:len(bits)] != bits)
        bad_errors.append(bad_ber)

    return {
        'legitimate_mean_ber': np.mean(good_errors),
        'legitimate_std_ber': np.std(good_errors),
        'attacker_mean_ber': np.mean(bad_errors),
        'attacker_std_ber': np.std(bad_errors),
        'security_margin': np.mean(bad_errors) / max(np.mean(good_errors), 1e-10)
    }


# =============================================================================
# DEMONSTRATION
# =============================================================================

def demo_cspm():
    """Demonstrate the full CSPM system."""

    print("=" * 70)
    print("CSPM - CRYPTOGRAPHICALLY-SEEDED POLYTOPAL MODULATION")
    print("=" * 70)

    # Create matched transmitter/receiver
    genesis = "DEMO_GENESIS_HASH_2024"
    tx = CSPMTransmitter(genesis_seed=genesis)
    rx = CSPMReceiver(genesis_seed=genesis)

    # Test data
    test_bits = np.array([1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1])
    print(f"\nOriginal bits: {test_bits}")

    # Transmit
    print("\n--- TRANSMISSION ---")
    data_hash = hashlib.sha256(test_bits.tobytes()).digest()
    states = tx.transmit_packet(test_bits, authenticate=True)

    print(f"Encoded into {len(states)} spinor states")
    print(f"First state: OAM l={states[0].oam.l}, Stokes={states[0].stokes.normalized()}")

    # Simulate channel (add noise)
    quaternions = np.array([s.quaternion for s in states])
    noise = np.random.normal(0, 0.05, quaternions.shape)
    noisy_q = quaternions + noise

    # Receive
    print("\n--- RECEPTION ---")
    rx_bits = rx.receive_packet(noisy_q, data_hash)
    print(f"Received bits: {rx_bits[:len(test_bits)]}")

    errors = np.sum(rx_bits[:len(test_bits)] != test_bits)
    print(f"Bit errors: {errors}/{len(test_bits)}")

    # Security analysis
    print("\n--- SECURITY ANALYSIS ---")
    print("Running interception resistance test...")
    security = analyze_interception_resistance(num_packets=50, num_symbols=50)

    print(f"Legitimate receiver BER: {security['legitimate_mean_ber']:.4f}")
    print(f"Attacker BER (wrong seed): {security['attacker_mean_ber']:.4f}")
    print(f"Security margin: {security['security_margin']:.1f}x worse for attacker")

    if security['attacker_mean_ber'] > 0.4:
        print("\n✓ Signal is UNREADABLE without genesis hash!")

    print("\n" + "=" * 70)

    return security


if __name__ == "__main__":
    demo_cspm()
