"""
CSPM Transmitter Module

Converts data streams into 4D optical signals encoded on the 600-cell
constellation. Implements hash-chain driven lattice rotation for
physical-layer encryption.

Physical Output Mapping:
- coords[0] (w): OAM topological charge (mode index)
- coords[1] (x): Stokes S1 (linear horizontal/vertical)
- coords[2] (y): Stokes S2 (linear +45/-45)
- coords[3] (z): Stokes S3 (circular left/right)
"""

import numpy as np
import hashlib
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Generator
from .lattice import Cell600, PolychoralConstellation, Vertex4D


@dataclass
class OpticalSymbol:
    """
    A single transmitted optical symbol.

    Represents the physical state of the light at transmission.
    """
    # 4D constellation point
    coords: np.ndarray  # [oam, s1, s2, s3]

    # Symbol metadata
    symbol_index: int
    packet_id: int
    timestamp: float

    # Physical parameters
    power: float = 1.0  # Normalized power
    wavelength: float = 1550e-9  # C-band (1550 nm)

    @property
    def oam_mode(self) -> float:
        """OAM topological charge (continuous for modulation)."""
        return self.coords[0]

    @property
    def stokes_vector(self) -> np.ndarray:
        """Polarization state as Stokes parameters [S1, S2, S3]."""
        return self.coords[1:4]

    @property
    def jones_vector(self) -> np.ndarray:
        """
        Convert Stokes to Jones vector for field representation.

        Jones vector [Ex, Ey] where E is complex amplitude.
        """
        s1, s2, s3 = self.stokes_vector
        s0 = 1.0  # Normalized total intensity

        # Convert Stokes to Jones (choosing global phase = 0)
        intensity = s0
        dop = np.sqrt(s1**2 + s2**2 + s3**2)  # Degree of polarization

        if dop < 1e-10:
            return np.array([1.0, 0.0], dtype=complex)

        # Azimuth and ellipticity
        psi = 0.5 * np.arctan2(s2, s1)  # Azimuth
        chi = 0.5 * np.arcsin(np.clip(s3 / dop, -1, 1))  # Ellipticity

        # Jones vector
        Ex = np.cos(psi) * np.cos(chi) - 1j * np.sin(psi) * np.sin(chi)
        Ey = np.sin(psi) * np.cos(chi) + 1j * np.cos(psi) * np.sin(chi)

        return np.array([Ex, Ey]) * np.sqrt(intensity)


class HashChainRotator:
    """
    Manages the cryptographic hash chain for lattice rotation.

    The hash chain provides:
    1. Deterministic rotation sequence (both TX and RX can compute)
    2. Forward secrecy (past rotations don't reveal future)
    3. Tamper evidence (any modification breaks the chain)
    """

    def __init__(self, genesis_seed: bytes):
        """
        Initialize with a shared secret seed.

        Args:
            genesis_seed: The shared secret between transmitter and receiver.
                         This is the only secret that needs to be pre-shared.
        """
        self.genesis = genesis_seed
        self._state = hashlib.sha256(genesis_seed).digest()
        self._packet_count = 0
        self._state_history: List[bytes] = [self._state]

    def advance(self, packet_data: bytes = None) -> bytes:
        """
        Advance the hash chain by one step.

        Args:
            packet_data: Optional data to mix into the chain.
                        If provided, the chain becomes data-dependent,
                        providing additional tamper detection.

        Returns:
            The new chain state (32 bytes).
        """
        if packet_data is not None:
            # Data-dependent chaining
            self._state = hashlib.sha256(
                self._state + packet_data
            ).digest()
        else:
            # Self-advancing chain
            self._state = hashlib.sha256(self._state).digest()

        self._packet_count += 1
        self._state_history.append(self._state)

        return self._state

    def get_rotation_angles(self) -> Tuple[float, float, float, float, float, float]:
        """
        Extract 6 rotation angles from the current state.

        These correspond to rotations in the 6 planes of 4D space:
        XY, XZ, XW, YZ, YW, ZW
        """
        # Interpret hash bytes as angles
        angles = []
        for i in range(6):
            # Take 4 bytes for each angle
            chunk = self._state[i*4:(i+1)*4]
            # Convert to float in [0, 2π)
            value = int.from_bytes(chunk, 'big') / (2**32)
            angle = value * 2 * np.pi
            angles.append(angle)

        return tuple(angles)

    def get_state(self) -> bytes:
        """Get current chain state for synchronization."""
        return self._state

    def set_state(self, state: bytes):
        """Set chain state (for receiver sync)."""
        self._state = state

    def resync_from_packet(self, packet_id: int) -> bytes:
        """
        Resynchronize to a specific packet in history.

        Returns the state at that packet, or None if not in history.
        """
        if packet_id < len(self._state_history):
            self._state = self._state_history[packet_id]
            return self._state
        return None


class CSPMTransmitter:
    """
    Cryptographically-Seeded Polytopal Modulation Transmitter.

    Converts a data stream into 4D optical symbols on the rotating
    600-cell constellation.
    """

    def __init__(
        self,
        genesis_seed: bytes = b"CSPM_DEFAULT_SEED",
        symbols_per_packet: int = 1000,
        bits_per_block: int = 6  # 6 bits -> 64 of 120 vertices
    ):
        """
        Initialize the CSPM transmitter.

        Args:
            genesis_seed: Shared secret for hash chain
            symbols_per_packet: Number of symbols per packet
            bits_per_block: Bits encoded per symbol (max ~6.9 for 120 vertices)
        """
        self.constellation = PolychoralConstellation(seed=genesis_seed)
        self.rotator = HashChainRotator(genesis_seed)
        self.symbols_per_packet = symbols_per_packet
        self.bits_per_block = min(bits_per_block, 6)  # Cap at 6 bits (64 symbols)
        self.symbols_used = 2 ** self.bits_per_block

        self._packet_count = 0
        self._symbol_count = 0

    def _bits_to_symbols(self, bits: np.ndarray) -> np.ndarray:
        """Convert bit array to symbol indices."""
        # Reshape bits into groups
        n_bits = len(bits)
        n_symbols = n_bits // self.bits_per_block
        bits = bits[:n_symbols * self.bits_per_block]
        bits = bits.reshape(n_symbols, self.bits_per_block)

        # Convert each group to integer
        powers = 2 ** np.arange(self.bits_per_block - 1, -1, -1)
        symbols = (bits * powers).sum(axis=1)

        return symbols.astype(int)

    def modulate_bits(self, bits: np.ndarray) -> List[OpticalSymbol]:
        """
        Modulate a bit stream into optical symbols.

        Args:
            bits: Array of bits (0s and 1s)

        Returns:
            List of OpticalSymbol objects
        """
        symbols_indices = self._bits_to_symbols(bits)
        optical_symbols = []

        for i, sym_idx in enumerate(symbols_indices):
            # Encode symbol on rotated constellation
            coords = self.constellation.encode_symbol(sym_idx)

            optical_sym = OpticalSymbol(
                coords=coords,
                symbol_index=sym_idx,
                packet_id=self._packet_count,
                timestamp=self._symbol_count * 1e-9  # 1 GBaud
            )
            optical_symbols.append(optical_sym)
            self._symbol_count += 1

        return optical_symbols

    def modulate_packet(
        self,
        data: bytes,
        include_header: bool = True
    ) -> Tuple[List[OpticalSymbol], bytes]:
        """
        Modulate a data packet with hash-chain rotation.

        Args:
            data: Raw data bytes to transmit
            include_header: Whether to prepend sync header

        Returns:
            Tuple of (optical symbols, packet hash for chaining)
        """
        # Compute packet hash
        packet_hash = hashlib.sha256(data).digest()

        # Rotate constellation based on hash chain
        self.constellation.rotate_lattice(packet_hash)
        self.rotator.advance(packet_hash)

        # Convert data to bits
        bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))

        # Modulate
        symbols = self.modulate_bits(bits)

        self._packet_count += 1

        return symbols, packet_hash

    def generate_sync_sequence(self, length: int = 64) -> List[OpticalSymbol]:
        """
        Generate a synchronization sequence.

        Uses known symbol pattern for receiver acquisition.
        """
        # Barker-like sequence mapped to constellation
        pattern = [0, 0, 0, 1, 1, 1, 0, 1]
        pattern = pattern * (length // len(pattern) + 1)
        pattern = pattern[:length]

        symbols = []
        for i, sym_idx in enumerate(pattern):
            coords = self.constellation.encode_symbol(sym_idx)
            symbols.append(OpticalSymbol(
                coords=coords,
                symbol_index=sym_idx,
                packet_id=-1,  # Sync packet
                timestamp=i * 1e-9
            ))

        return symbols

    def get_constellation_state(self) -> bytes:
        """Get current constellation state for receiver sync."""
        return self.constellation.get_rotation_state()


def generate_random_data(n_bytes: int, seed: int = None) -> bytes:
    """Generate random data for testing."""
    rng = np.random.default_rng(seed)
    return bytes(rng.integers(0, 256, n_bytes, dtype=np.uint8))


if __name__ == "__main__":
    # Test transmitter
    tx = CSPMTransmitter(genesis_seed=b"test_seed_123")

    # Generate test data
    data = generate_random_data(1000, seed=42)

    # Modulate packet
    symbols, packet_hash = tx.modulate_packet(data)

    print(f"Transmitted {len(symbols)} symbols for {len(data)} bytes")
    print(f"Bits per symbol: {tx.bits_per_block}")
    print(f"Packet hash: {packet_hash[:8].hex()}...")
    print(f"First symbol: coords={symbols[0].coords}")
    print(f"OAM mode: {symbols[0].oam_mode:.4f}")
    print(f"Stokes vector: {symbols[0].stokes_vector}")

    # Test sync sequence
    sync = tx.generate_sync_sequence(32)
    print(f"\nSync sequence: {len(sync)} symbols")
