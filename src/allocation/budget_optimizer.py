"""
Fixed Compute Budget Allocation Optimizer and Pareto Frontier Solver.
Maximizes problem-solving velocity (Success Rate / Wall-Clock Latency)
subject to hard token and dollar constraints.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np


@dataclass
class AllocationStrategy:
    strategy_id: str
    name: str
    team_size: int
    tier_composition: str
    plan_budget_ratio: float      # r_plan
    exec_budget_ratio: float      # r_exec
    verify_budget_ratio: float    # r_verify
    estimated_cost_usd: float
    wall_clock_time_sec: float
    success_probability: float
    velocity_score: float         # Success Probability / Wall-Clock Time
    pareto_efficient: bool = False


class ComputeBudgetOptimizer:
    """
    Optimizes compute allocation across multi-agent teams for fastest problem resolution.
    Finds the Pareto-optimal frontier across budget constraints.
    """

    def __init__(self, task_difficulty: float = 0.75, problem_entropy: float = 0.65):
        self.task_difficulty = task_difficulty
        self.problem_entropy = problem_entropy

    def evaluate_strategy(
        self,
        strategy_id: str,
        name: str,
        team_size: int,
        tier_composition: str,
        plan_ratio: float,
        exec_ratio: float,
        verify_ratio: float,
        budget_usd: float,
    ) -> AllocationStrategy:
        """
        Simulates and scores an allocation configuration.
        """
        # Enforce ratio sum = 1.0
        total_ratio = plan_ratio + exec_ratio + verify_ratio
        r_p = plan_ratio / total_ratio
        r_e = exec_ratio / total_ratio
        r_v = verify_ratio / total_ratio

        # Strategic planning penalty / reward:
        # Too little planning (< 15%) leads to redundant work and dead-ends.
        # Too much planning (> 45%) leads to analysis paralysis.
        planning_multiplier = math.exp(-((r_p - 0.25) ** 2) / 0.05)

        # Verification penalty / reward:
        # Too little verification (< 10%) permits hallucination cascades.
        # Too much verification (> 40%) consumes too much execution budget.
        verification_multiplier = math.exp(-((r_v - 0.20) ** 2) / 0.04)

        # Execution volume capacity:
        exec_capacity = r_e * (budget_usd / 0.02)

        # Effective Team Intelligence based on tier composition:
        if "Frontier" in tier_composition and "Worker" in tier_composition:
            base_intel = 0.94  # Heterogeneous tiered
            base_agent_latency = 0.55
        elif "Frontier" in tier_composition:
            base_intel = 0.92  # All Frontier
            base_agent_latency = 1.20
        else:
            base_intel = 0.75  # All Fast
            base_agent_latency = 0.35

        # Coordination drag (hierarchical vs flat)
        coord_drag = 1.0 + 0.02 * math.log2(team_size + 1)

        # Wall clock time = (Total steps required) / (Parallelism factor) * Agent latency
        effective_work_needed = 25.0 * self.task_difficulty
        parallel_speedup = min(team_size * 0.7, team_size / coord_drag)
        wall_clock = max(2.0, (effective_work_needed / parallel_speedup) * base_agent_latency * (1.0 + (1.0 - r_p) * 0.5))

        # Success Probability:
        # Function of budget, intelligence, planning, verification, and difficulty
        raw_prob = (
            base_intel
            * planning_multiplier
            * verification_multiplier
            * min(1.0, math.sqrt(budget_usd / 5.0))
            / (self.task_difficulty + 0.15)
        )
        success_prob = min(0.99, max(0.05, raw_prob))

        # Velocity Score = Success Probability / Wall-Clock Latency (solutions per second)
        velocity = success_prob / wall_clock

        actual_cost = min(budget_usd, budget_usd * (0.85 + 0.15 * (team_size / 16.0)))

        return AllocationStrategy(
            strategy_id=strategy_id,
            name=name,
            team_size=team_size,
            tier_composition=tier_composition,
            plan_budget_ratio=round(r_p, 2),
            exec_budget_ratio=round(r_e, 2),
            verify_budget_ratio=round(r_v, 2),
            estimated_cost_usd=round(actual_cost, 2),
            wall_clock_time_sec=round(wall_clock, 2),
            success_probability=round(success_prob, 3),
            velocity_score=round(velocity, 4),
        )

    def optimize_for_budget(self, budget_usd: float) -> List[AllocationStrategy]:
        """
        Generates candidate strategies across the design space and flags Pareto-optimal solutions.
        """
        candidates = [
            self.evaluate_strategy("strat_1", "Single Frontier Sequential", 1, "1 Frontier", 0.30, 0.50, 0.20, budget_usd),
            self.evaluate_strategy("strat_2", "Flat Fast Swarm (N=8)", 8, "8 Fast", 0.10, 0.75, 0.15, budget_usd),
            self.evaluate_strategy("strat_3", "Heterogeneous Tiered (1 Arch + 4 Workers)", 5, "1 Frontier + 4 Fast", 0.25, 0.55, 0.20, budget_usd),
            self.evaluate_strategy("strat_4", "Heterogeneous Tiered (1 Arch + 8 Workers)", 9, "1 Frontier + 8 Fast", 0.25, 0.55, 0.20, budget_usd),
            self.evaluate_strategy("strat_5", "Heterogeneous Balanced (1 Arch + 6 Workers + 2 Verifiers)", 9, "1 Frontier + 6 Fast + 2 Verifier", 0.25, 0.50, 0.25, budget_usd),
            self.evaluate_strategy("strat_6", "Heavy Planning Asymmetric (2 Arch + 4 Workers)", 6, "2 Frontier + 4 Fast", 0.45, 0.40, 0.15, budget_usd),
            self.evaluate_strategy("strat_7", "Ultra-Parallel Swarm (1 Arch + 16 Workers)", 17, "1 Frontier + 16 Fast", 0.20, 0.60, 0.20, budget_usd),
        ]

        # Identify Pareto front: (minimize latency, maximize success_prob)
        # Point A dominates Point B if latency_A <= latency_B and success_A >= success_B (with at least one strict)
        for i, c1 in enumerate(candidates):
            dominated = False
            for j, c2 in enumerate(candidates):
                if i != j:
                    if (c2.wall_clock_time_sec <= c1.wall_clock_time_sec and
                        c2.success_probability >= c1.success_probability and
                        (c2.wall_clock_time_sec < c1.wall_clock_time_sec or c2.success_probability > c1.success_probability)):
                        dominated = True
                        break
            c1.pareto_efficient = not dominated

        return sorted(candidates, key=lambda x: x.velocity_score, reverse=True)
