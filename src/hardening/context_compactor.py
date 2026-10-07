"""
Hierarchical Context Compactor and Epistemic Scoping.
Solves Context Window Hyper-Inflation and Attention Degradation (Lost-in-the-Middle)
as team size N and task horizon T scale together.
"""

from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.state import EpistemicAssertion, InvariantStatus, VectorClock


@dataclass
class CompactedMilestone:
    milestone_id: str
    step_range: Tuple[int, int]
    canonical_invariants: List[str]
    rejected_hypotheses: List[str]
    causal_vector_clock: VectorClock
    compressed_tokens: int
    raw_tokens_represented: int
    compression_ratio: float


class HierarchicalContextCompactor:
    """
    Transforms unbounded trajectory histories into bounded, high-density epistemic checkpoints.
    Ensures agents stay within token budgets without losing foundational constraints.
    """

    def __init__(self, target_checkpoint_interval: int = 10, max_token_ceiling: int = 8000):
        self.interval = target_checkpoint_interval
        self.max_ceiling = max_token_ceiling
        self.milestones: List[CompactedMilestone] = []

    def compact_trajectory(
        self,
        step_start: int,
        step_end: int,
        raw_events: List[Dict[str, Any]],
        active_assertions: List[EpistemicAssertion],
        clock: VectorClock,
    ) -> CompactedMilestone:
        """
        Condenses raw interaction events into a single verified invariant snapshot.
        """
        raw_token_count = sum(e.get("tokens", 100) for e in raw_events)
        
        # Filter verified vs refuted invariants
        canonical = [
            f"INVARIANT [{a.assertion_id}]: {a.claim_type} -> {str(a.content)[:80]}"
            for a in active_assertions
            if a.status == InvariantStatus.VERIFIED
        ]
        rejected = [
            f"REFUTED [{a.assertion_id}]: {str(a.content)[:60]}"
            for a in active_assertions
            if a.status in (InvariantStatus.REFUTED, InvariantStatus.QUARANTINED)
        ]

        # Estimated tokens for compacted milestone
        compressed_tokens = len(canonical) * 25 + len(rejected) * 15 + 100
        compression_ratio = raw_token_count / max(1, compressed_tokens)

        milestone = CompactedMilestone(
            milestone_id=f"ms_{step_start}_{step_end}",
            step_range=(step_start, step_end),
            canonical_invariants=canonical,
            rejected_hypotheses=rejected,
            causal_vector_clock=clock.copy(),
            compressed_tokens=compressed_tokens,
            raw_tokens_represented=raw_token_count,
            compression_ratio=round(compression_ratio, 2),
        )
        self.milestones.append(milestone)
        return milestone

    def build_scoped_agent_context(
        self,
        agent_id: str,
        role: str,
        assigned_subtask: str,
        recent_events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generates a bounded context projection tailored to an agent's specific role and subtask.
        Eliminates irrelevant peer chatter and prevents context pollution.
        """
        # Include latest milestone summary
        latest_ms = self.milestones[-1] if self.milestones else None
        
        scoped_summary = []
        if latest_ms:
            scoped_summary.append(f"=== CHECKPOINT (Steps {latest_ms.step_range[0]}-{latest_ms.step_range[1]}) ===")
            scoped_summary.extend(latest_ms.canonical_invariants[:6])
            if latest_ms.rejected_hypotheses:
                scoped_summary.append("KNOWN DEAD ENDS:")
                scoped_summary.extend(latest_ms.rejected_hypotheses[:3])

        # Filter recent events to only relevant subtask or direct messages
        scoped_recent = []
        for ev in recent_events[-6:]:
            if ev.get("agent_id") == agent_id or ev.get("subtask") == assigned_subtask or ev.get("role") == "ARCHITECT":
                scoped_recent.append(ev)

        return {
            "agent_id": agent_id,
            "role": role,
            "subtask": assigned_subtask,
            "milestone_context": scoped_summary,
            "recent_events": scoped_recent,
            "effective_tokens": (len(scoped_summary) * 20) + (len(scoped_recent) * 50),
        }
