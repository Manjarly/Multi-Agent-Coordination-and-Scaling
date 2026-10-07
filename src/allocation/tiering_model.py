"""
Agent Tiering and Heterogeneous Team Composition Models.
Analyzes cost-performance trade-offs between homogeneous frontier swarms
and heterogeneous tiered architectures (e.g., 1 Frontier Lead + K Fast Workers).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.core.agent import ModelTier, TIER_PROFILES


@dataclass
class TeamTieringConfig:
    name: str
    frontier_agents: int
    fast_agents: int
    lightweight_agents: int
    total_agents: int
    blended_cost_per_step: float
    effective_team_intelligence: float
    parallel_execution_speed: float


class TieringModelAnalyzer:
    """
    Evaluates heterogeneous vs. homogeneous team allocations under compute budgets.
    """

    @staticmethod
    def calculate_configuration(
        name: str,
        frontier: int,
        fast: int,
        lightweight: int,
        branching_entropy: float = 0.7,
    ) -> TeamTieringConfig:
        n = frontier + fast + lightweight
        p_front = TIER_PROFILES[ModelTier.FRONTIER]
        p_fast = TIER_PROFILES[ModelTier.FAST]
        p_light = TIER_PROFILES[ModelTier.LIGHTWEIGHT]

        # Cost per step assuming 1k input, 500 output tokens per agent
        cost_step = (
            frontier * (1.0 * p_front.cost_per_1k_input_tokens + 0.5 * p_front.cost_per_1k_output_tokens)
            + fast * (1.0 * p_fast.cost_per_1k_input_tokens + 0.5 * p_fast.cost_per_1k_output_tokens)
            + lightweight * (1.0 * p_light.cost_per_1k_input_tokens + 0.5 * p_light.cost_per_1k_output_tokens)
        )

        # Team intelligence model:
        # High-tier architect acts as cognitive multiplier on worker throughput
        if frontier >= 1:
            # Heterogeneous: Architect provides strategic guidance, workers provide volume
            arch_bonus = 0.35 * (1.0 + branching_entropy)
            worker_power = (fast * p_fast.reasoning_power + lightweight * p_light.reasoning_power)
            intel = min(0.99, p_front.reasoning_power + arch_bonus * (worker_power / max(1, n)))
        elif fast >= 1:
            intel = min(0.85, p_fast.reasoning_power + 0.1 * (fast / max(1, n)))
        else:
            intel = min(0.65, p_light.reasoning_power)

        # Parallel speed (considering latency profile)
        # Frontier model latency is higher (1.2s vs 0.35s)
        avg_latency = (
            (frontier * p_front.base_latency_sec + fast * p_fast.base_latency_sec + lightweight * p_light.base_latency_sec)
            / max(1, n)
        )
        speed = 1.0 / max(0.1, avg_latency)

        return TeamTieringConfig(
            name=name,
            frontier_agents=frontier,
            fast_agents=fast,
            lightweight_agents=lightweight,
            total_agents=n,
            blended_cost_per_step=round(cost_step, 4),
            effective_team_intelligence=round(intel, 3),
            parallel_execution_speed=round(speed, 2),
        )

    @classmethod
    def compare_standard_compositions(cls) -> List[TeamTieringConfig]:
        """Compares homogeneous frontier vs homogeneous fast vs heterogeneous tiered architectures."""
        return [
            cls.calculate_configuration("Single Frontier Agent", frontier=1, fast=0, lightweight=0),
            cls.calculate_configuration("Homogeneous Frontier Swarm (N=4)", frontier=4, fast=0, lightweight=0),
            cls.calculate_configuration("Homogeneous Fast Swarm (N=8)", frontier=0, fast=8, lightweight=0),
            cls.calculate_configuration("Heterogeneous Tiered (1 Frontier + 6 Fast)", frontier=1, fast=6, lightweight=0),
            cls.calculate_configuration("Heterogeneous Tiered (1 Frontier + 12 Fast)", frontier=1, fast=12, lightweight=0),
            cls.calculate_configuration("Heterogeneous Tiered (2 Frontier + 8 Fast + 6 Light)", frontier=2, fast=8, lightweight=6),
        ]
