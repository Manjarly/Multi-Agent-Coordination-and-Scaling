"""
State Management, Epistemic Consistency, and Optimistic Concurrency Control (OCC).
Provides vector clocks, atomic transactions, conflict-free state merging,
and verifiable epistemic belief graphs for large multi-agent teams.
"""

from __future__ import annotations
import copy
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class InvariantStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    QUARANTINED = "QUARANTINED"


@dataclass
class VectorClock:
    """Vector clock representation for distributed causal ordering."""
    clock: Dict[str, int] = field(default_factory=dict)

    def increment(self, agent_id: str) -> None:
        self.clock[agent_id] = self.clock.get(agent_id, 0) + 1

    def update(self, other: VectorClock) -> None:
        for agent_id, count in other.clock.items():
            self.clock[agent_id] = max(self.clock.get(agent_id, 0), count)

    def is_causally_before(self, other: VectorClock) -> bool:
        """Returns True if self <= other and self != other."""
        less_or_equal = True
        strictly_less = False
        all_keys = set(self.clock.keys()) | set(other.clock.keys())
        for k in all_keys:
            v_self = self.clock.get(k, 0)
            v_other = other.clock.get(k, 0)
            if v_self > v_other:
                return False
            if v_self < v_other:
                strictly_less = True
        return strictly_less and less_or_equal

    def copy(self) -> VectorClock:
        return VectorClock(copy.deepcopy(self.clock))


@dataclass
class EpistemicAssertion:
    """A claim, proof step, or state assertion made by an agent."""
    assertion_id: str
    author_id: str
    claim_type: str  # e.g., "hypothesis", "constraint_bound", "refactor_patch", "proof_step"
    content: Any
    confidence: float
    supporting_evidence: List[str] = field(default_factory=list)
    status: InvariantStatus = InvariantStatus.PROPOSED
    verifiers: Set[str] = field(default_factory=set)
    refuters: Set[str] = field(default_factory=set)
    timestamp: float = field(default_factory=time.time)
    vector_clock: VectorClock = field(default_factory=VectorClock)
    hash_digest: str = ""

    def __post_init__(self):
        if not self.hash_digest:
            raw = f"{self.assertion_id}:{self.author_id}:{self.claim_type}:{str(self.content)}"
            self.hash_digest = hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class StatePatch:
    """An atomic mutation proposal for the shared state."""
    patch_id: str
    agent_id: str
    base_version: int
    target_key: str
    operation: str  # 'set', 'append', 'delete', 'merge_dict'
    payload: Any
    vector_clock: VectorClock
    timestamp: float = field(default_factory=time.time)


class SharedWorkspace:
    """
    Optimistic Concurrency Control (OCC) shared workspace for multi-agent execution.
    Eliminates silent overwrite bugs, detects concurrent conflict writes,
    and supports rollback journals and snapshot isolation.
    """

    def __init__(self):
        self.version: int = 0
        self.state: Dict[str, Any] = {}
        self.assertions: Dict[str, EpistemicAssertion] = {}
        self.journal: List[Dict[str, Any]] = []
        self.vector_clock: VectorClock = VectorClock()
        self.conflict_count: int = 0
        self.quarantine_vault: List[EpistemicAssertion] = []

    def get(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(self.state.get(key, default))

    def get_snapshot(self) -> Tuple[int, Dict[str, Any], VectorClock]:
        return self.version, copy.deepcopy(self.state), self.vector_clock.copy()

    def propose_patch(self, patch: StatePatch) -> Tuple[bool, Optional[str]]:
        """
        Validates patch against OCC versioning.
        Returns (success, error_or_conflict_reason).
        """
        # Conflict detection: If base_version lags behind current workspace version,
        # inspect if the target_key was modified since base_version.
        if patch.base_version < self.version:
            # Check journal entries between base_version and current version
            modified_keys = {
                entry["patch"].target_key
                for entry in self.journal[patch.base_version :]
            }
            if patch.target_key in modified_keys:
                self.conflict_count += 1
                return False, f"OCC Conflict: key '{patch.target_key}' modified concurrently since v{patch.base_version}"

        # Apply patch atomically
        prev_val = self.state.get(patch.target_key, None)
        if patch.operation == "set":
            self.state[patch.target_key] = copy.deepcopy(patch.payload)
        elif patch.operation == "append":
            current_list = self.state.setdefault(patch.target_key, [])
            if isinstance(current_list, list):
                current_list.append(copy.deepcopy(patch.payload))
            else:
                return False, f"Type mismatch: '{patch.target_key}' is not a list"
        elif patch.operation == "merge_dict":
            current_dict = self.state.setdefault(patch.target_key, {})
            if isinstance(current_dict, dict) and isinstance(patch.payload, dict):
                current_dict.update(copy.deepcopy(patch.payload))
            else:
                return False, f"Type mismatch: '{patch.target_key}' or payload is not a dict"
        elif patch.operation == "delete":
            self.state.pop(patch.target_key, None)
        else:
            return False, f"Unknown operation '{patch.operation}'"

        # Update metadata
        self.version += 1
        self.vector_clock.update(patch.vector_clock)
        self.journal.append({
            "version": self.version,
            "patch": patch,
            "prev_val": prev_val,
            "timestamp": time.time(),
        })
        return True, None

    def register_assertion(self, assertion: EpistemicAssertion) -> None:
        """Records an agent's claim into the global epistemic registry."""
        self.assertions[assertion.assertion_id] = assertion

    def vote_on_assertion(self, assertion_id: str, verifier_id: str, approves: bool) -> InvariantStatus:
        """Updates consensus on an assertion via quorum verification."""
        if assertion_id not in self.assertions:
            raise KeyError(f"Assertion {assertion_id} not found")
        assertion = self.assertions[assertion_id]
        if approves:
            assertion.verifiers.add(verifier_id)
        else:
            assertion.refuters.add(verifier_id)

        # Quorum rule: 2+ verifiers and no refuters -> VERIFIED
        # 1+ refuters -> REFUTED & moved to quarantine
        if len(assertion.refuters) > 0:
            assertion.status = InvariantStatus.REFUTED
            if assertion not in self.quarantine_vault:
                self.quarantine_vault.append(assertion)
        elif len(assertion.verifiers) >= 2:
            assertion.status = InvariantStatus.VERIFIED
        else:
            assertion.status = InvariantStatus.PROPOSED
        return assertion.status

    def rollback_to_version(self, target_version: int) -> None:
        """Rolls back the workspace state to a prior version using the journal."""
        if target_version < 0 or target_version > self.version:
            raise ValueError(f"Invalid target version {target_version}")

        while self.version > target_version:
            last_entry = self.journal.pop()
            patch = last_entry["patch"]
            prev_val = last_entry["prev_val"]
            if prev_val is None:
                self.state.pop(patch.target_key, None)
            else:
                self.state[patch.target_key] = prev_val
            self.version -= 1
