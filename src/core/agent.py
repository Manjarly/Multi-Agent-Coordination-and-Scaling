"""
Agent abstractions, roles, tiers, context window management,
and token/cost accounting.
"""

from __future__ import annotations
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.core.state import EpistemicAssertion, StatePatch, VectorClock


class AgentRole(str, Enum):
    ARCHITECT = "ARCHITECT"          # High-level planning, sub-task decomposition, strategic steering
    WORKER = "WORKER"                # Domain execution, sub-problem solver, hypothesis generation
    VERIFIER = "VERIFIER"            # Strict proof/contract checking, adversarial counterexamples
    SYNTHESIZER = "SYNTHESIZER"      # Aggregates worker solutions, detects merge conflicts


class ModelTier(str, Enum):
    FRONTIER = "FRONTIER"            # e.g., Claude 3.7 Sonnet / Opus class: highest reasoning, highest cost
    FAST = "FAST"                    # e.g., Claude 3.5 Haiku class: low latency, high throughput, moderate cost
    LIGHTWEIGHT = "LIGHTWEIGHT"      # Small specialized model / local: lowest cost, narrower domain


@dataclass
class TierProfile:
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float
    reasoning_power: float          # [0.0 - 1.0]: capacity to solve complex reasoning steps
    base_latency_sec: float         # Execution latency
    hallucination_rate: float       # Base unverified error probability per complex step
    context_limit: int              # Max context window in tokens


TIER_PROFILES: Dict[ModelTier, TierProfile] = {
    ModelTier.FRONTIER: TierProfile(
        cost_per_1k_input_tokens=0.003,
        cost_per_1k_output_tokens=0.015,
        reasoning_power=0.92,
        base_latency_sec=1.2,
        hallucination_rate=0.04,
        context_limit=200_000,
    ),
    ModelTier.FAST: TierProfile(
        cost_per_1k_input_tokens=0.0008,
        cost_per_1k_output_tokens=0.004,
        reasoning_power=0.74,
        base_latency_sec=0.35,
        hallucination_rate=0.12,
        context_limit=128_000,
    ),
    ModelTier.LIGHTWEIGHT: TierProfile(
        cost_per_1k_input_tokens=0.0002,
        cost_per_1k_output_tokens=0.001,
        reasoning_power=0.52,
        base_latency_sec=0.12,
        hallucination_rate=0.25,
        context_limit=32_000,
    ),
}


@dataclass
class AgentMessage:
    message_id: str
    sender_id: str
    recipient_id: str                # Specific agent id or "BROADCAST" or "SUPERVISOR"
    topic: str
    payload: Any
    token_cost: int
    vector_clock: VectorClock
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentMetrics:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_steps: int = 0
    successful_steps: int = 0
    rejected_patches: int = 0
    hallucinations_flagged: int = 0
    active_runtime_sec: float = 0.0


class BoundedContextBuffer:
    """
    Manages an agent's context horizon with sliding window and hierarchical compaction.
    Prevents Context Bloat and Attention Degradation during long horizons (T >> 1).
    """

    def __init__(self, max_tokens: int = 8000, compact_threshold: float = 0.8):
        self.max_tokens = max_tokens
        self.compact_threshold = int(max_tokens * compact_threshold)
        self.raw_events: List[Dict[str, Any]] = []
        self.milestone_summaries: List[str] = []
        self.current_token_count: int = 0

    def add_event(self, event_type: str, content: str, token_est: int) -> None:
        self.raw_events.append({"type": event_type, "content": content, "tokens": token_est})
        self.current_token_count += token_est

        if self.current_token_count > self.compact_threshold:
            self._compact_context()

    def _compact_context(self) -> None:
        """Compacts older raw events into a high-density summary to avoid context blowup."""
        if len(self.raw_events) <= 4:
            return
        
        # Keep recent 3 events intact, compact the rest
        to_compact = self.raw_events[:-3]
        compacted_tokens = sum(e["tokens"] for e in to_compact)
        
        # In a production LLM system, an LLM summarizer generates this.
        # Here we model the compaction ratio (approx 5:1 compression)
        summary_text = f"[Compacted Milestone: {len(to_compact)} events compacted, key invariant state preserved]"
        summary_tokens = max(50, int(compacted_tokens * 0.18))
        
        self.milestone_summaries.append(summary_text)
        self.raw_events = self.raw_events[-3:]
        
        # Recalculate token count
        self.current_token_count = (
            sum(e["tokens"] for e in self.raw_events) + len(self.milestone_summaries) * summary_tokens
        )

    def render_context(self) -> str:
        parts = []
        if self.milestone_summaries:
            parts.append("=== PREVIOUS MILESTONES ===")
            parts.extend(self.milestone_summaries)
        parts.append("=== RECENT WORKING MEMORY ===")
        for e in self.raw_events:
            parts.append(f"[{e['type']}] {e['content']}")
        return "\n".join(parts)


class BoundedAgent:
    """
    An agent participating in a multi-agent team.
    Tracks epistemic state, token expenditures, concurrency patches, and execution.
    """

    def __init__(
        self,
        agent_id: str,
        role: AgentRole = AgentRole.WORKER,
        tier: ModelTier = ModelTier.FAST,
        max_context_tokens: int = 16_000,
    ):
        self.agent_id = agent_id
        self.role = role
        self.tier = tier
        self.profile = TIER_PROFILES[tier]
        self.context_buffer = BoundedContextBuffer(max_tokens=max_context_tokens)
        self.vector_clock = VectorClock()
        self.metrics = AgentMetrics()
        self.assigned_subtask: Optional[str] = None
        self.is_alive: bool = True

    def consume_tokens(self, input_tokens: int, output_tokens: int, latency_override: Optional[float] = None) -> float:
        """Updates token accounting and computes dollar expenditure."""
        cost = (
            (input_tokens / 1000.0) * self.profile.cost_per_1k_input_tokens
            + (output_tokens / 1000.0) * self.profile.cost_per_1k_output_tokens
        )
        latency = latency_override if latency_override is not None else self.profile.base_latency_sec

        self.metrics.total_input_tokens += input_tokens
        self.metrics.total_output_tokens += output_tokens
        self.metrics.total_cost_usd += cost
        self.metrics.active_runtime_sec += latency
        return cost

    def step_reasoning(
        self,
        task_difficulty: float,  # [0.0 - 1.0]
        coordination_noise: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Executes one unit of reasoning/execution work.
        Returns the action outcome, token cost, and potential epistemic assertion.
        """
        self.metrics.total_steps += 1
        self.vector_clock.increment(self.agent_id)

        # Context tokens depend on current context buffer size
        input_tokens = max(500, self.context_buffer.current_token_count)
        output_tokens = random.randint(250, 750)
        self.consume_tokens(input_tokens, output_tokens)

        # Effective problem-solving capability degrades with task difficulty and coordination noise
        effective_capacity = self.profile.reasoning_power * (1.0 - coordination_noise * 0.4)
        
        # Probability of success on this step
        success_prob = max(0.05, min(0.98, effective_capacity / (task_difficulty + 0.2)))
        step_succeeded = random.random() < success_prob

        # Probability of a hallucinated claim (unverified false invariant)
        hallucination_prob = self.profile.hallucination_rate * (1.0 + coordination_noise)
        is_hallucination = random.random() < hallucination_prob

        if step_succeeded:
            self.metrics.successful_steps += 1

        action_event = {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "tier": self.tier.value,
            "succeeded": step_succeeded,
            "is_hallucination": is_hallucination,
            "subtask": self.assigned_subtask,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

        self.context_buffer.add_event(
            event_type="REASONING_STEP",
            content=f"Subtask: {self.assigned_subtask} | Success: {step_succeeded}",
            token_est=output_tokens,
        )

        return action_event
