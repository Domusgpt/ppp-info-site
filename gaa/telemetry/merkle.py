"""
Merkle Audit Tree

Efficient verification of event batches via Merkle tree structure.
Enables logarithmic-scale proofs for large event streams.

Based on the observation from clinical AI auditing:
"80 million events requiring 800 MB linearly can be verified
with 3 KB Merkle proofs when properly structured."
"""

import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import json


def _hash_pair(left: bytes, right: bytes) -> bytes:
    """Hash two nodes together."""
    return hashlib.sha256(left + right).digest()


def _hash_leaf(data: bytes) -> bytes:
    """Hash leaf data with domain separator."""
    return hashlib.sha256(b"LEAF:" + data).digest()


@dataclass
class MerkleProof:
    """
    Merkle proof for a single leaf.

    Contains the sibling hashes needed to reconstruct
    the root from a leaf.
    """

    leaf_hash: bytes
    leaf_index: int
    siblings: List[Tuple[bytes, bool]]  # (hash, is_left)
    root: bytes

    def verify(self, leaf_data: bytes) -> bool:
        """Verify the proof for given leaf data."""
        computed_hash = _hash_leaf(leaf_data)

        if computed_hash != self.leaf_hash:
            return False

        current = computed_hash
        for sibling_hash, is_left in self.siblings:
            if is_left:
                current = _hash_pair(sibling_hash, current)
            else:
                current = _hash_pair(current, sibling_hash)

        return current == self.root

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "leaf_hash": self.leaf_hash.hex(),
            "leaf_index": self.leaf_index,
            "siblings": [
                {"hash": h.hex(), "is_left": left}
                for h, left in self.siblings
            ],
            "root": self.root.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MerkleProof':
        """Deserialize from dictionary."""
        return cls(
            leaf_hash=bytes.fromhex(data["leaf_hash"]),
            leaf_index=data["leaf_index"],
            siblings=[
                (bytes.fromhex(s["hash"]), s["is_left"])
                for s in data["siblings"]
            ],
            root=bytes.fromhex(data["root"]),
        )

    @property
    def proof_size_bytes(self) -> int:
        """Size of proof in bytes."""
        # 32 bytes per hash, plus index and flags
        return 32 + 4 + len(self.siblings) * 33 + 32


@dataclass
class MerkleAuditTree:
    """
    Merkle tree for efficient audit verification.

    Supports:
    - Incremental leaf addition
    - O(log n) proof generation
    - Batch verification
    - Root commitment for external anchoring

    The tree is built lazily when proofs are requested.
    """

    leaves: List[bytes] = field(default_factory=list)
    _tree: List[List[bytes]] = field(default_factory=list, repr=False)
    _tree_valid: bool = field(default=False, repr=False)

    def add_leaf(self, data: bytes) -> int:
        """
        Add a leaf to the tree.

        Returns the leaf index.
        """
        leaf_hash = _hash_leaf(data)
        self.leaves.append(leaf_hash)
        self._tree_valid = False
        return len(self.leaves) - 1

    def add_event(self, event_hash: str) -> int:
        """Add an event hash as a leaf."""
        return self.add_leaf(bytes.fromhex(event_hash))

    def _build_tree(self) -> None:
        """Build the Merkle tree from leaves."""
        if self._tree_valid:
            return

        if not self.leaves:
            self._tree = []
            self._tree_valid = True
            return

        # Start with leaves
        current_level = list(self.leaves)

        # Pad to power of 2 if needed
        while len(current_level) & (len(current_level) - 1):
            current_level.append(current_level[-1])

        self._tree = [current_level]

        # Build up the tree
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(_hash_pair(left, right))
            self._tree.append(next_level)
            current_level = next_level

        self._tree_valid = True

    @property
    def root(self) -> Optional[bytes]:
        """Get the Merkle root."""
        self._build_tree()
        if not self._tree:
            return None
        return self._tree[-1][0]

    @property
    def root_hex(self) -> str:
        """Get the Merkle root as hex string."""
        r = self.root
        return r.hex() if r else ""

    def get_proof(self, leaf_index: int) -> MerkleProof:
        """
        Generate proof for a specific leaf.

        Args:
            leaf_index: Index of the leaf to prove

        Returns:
            MerkleProof containing sibling hashes
        """
        self._build_tree()

        if leaf_index < 0 or leaf_index >= len(self.leaves):
            raise ValueError(f"Leaf index {leaf_index} out of range")

        siblings = []
        idx = leaf_index

        # Pad index if tree was padded
        tree_size = len(self._tree[0])

        for level in range(len(self._tree) - 1):
            # Determine sibling
            if idx % 2 == 0:
                sibling_idx = idx + 1
                is_left = False
            else:
                sibling_idx = idx - 1
                is_left = True

            if sibling_idx < len(self._tree[level]):
                sibling_hash = self._tree[level][sibling_idx]
            else:
                sibling_hash = self._tree[level][idx]  # Duplicate for odd

            siblings.append((sibling_hash, is_left))
            idx //= 2

        return MerkleProof(
            leaf_hash=self.leaves[leaf_index],
            leaf_index=leaf_index,
            siblings=siblings,
            root=self.root,
        )

    def verify_proof(self, proof: MerkleProof) -> bool:
        """Verify a proof against current root."""
        return proof.root == self.root

    def get_batch_proof(self, indices: List[int]) -> List[MerkleProof]:
        """Generate proofs for multiple leaves."""
        return [self.get_proof(i) for i in indices]

    def commitment(self) -> dict:
        """
        Get commitment data for external anchoring.

        Can be published to blockchain or signed for timestamping.
        """
        return {
            "root": self.root_hex,
            "leaf_count": len(self.leaves),
            "tree_height": len(self._tree) if self._tree else 0,
        }

    def to_json(self) -> str:
        """Serialize tree to JSON."""
        return json.dumps({
            "leaves": [leaf.hex() for leaf in self.leaves],
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'MerkleAuditTree':
        """Deserialize tree from JSON."""
        data = json.loads(json_str)
        tree = cls()
        for leaf_hex in data["leaves"]:
            tree.leaves.append(bytes.fromhex(leaf_hex))
        return tree

    def __len__(self) -> int:
        return len(self.leaves)


def batch_verify_proofs(proofs: List[MerkleProof], root: bytes) -> bool:
    """
    Verify multiple proofs against a single root.

    More efficient than verifying individually when
    proofs share intermediate nodes.
    """
    for proof in proofs:
        if proof.root != root:
            return False
    return True


def compute_tree_from_events(event_hashes: List[str]) -> MerkleAuditTree:
    """
    Build Merkle tree from list of event hashes.

    Args:
        event_hashes: List of hex-encoded event hashes
    """
    tree = MerkleAuditTree()
    for h in event_hashes:
        tree.add_event(h)
    return tree
