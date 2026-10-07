"""
Empirical Multi-Agent Scaling Engine.
Simulates and measures team execution over team sizes N in [1, 2, 4, 8, 16, 32, 64]
under varying problem hardness and communication topologies.
"""

from __future__ import annotations
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.agent import AgentRole, BoundedAgent, ModelTier
from src.core.bus import ResilientMessageBus
from src.core.state import EpistemicAssertion, SharedWorkspace, StatePatch, VectorClock
from src.core.topology import TeamTopology, TopologyConfig, TopologyType


@dataclass
class BenchmarkTask:
    task_id: str
    name: str
    difficulty: float               # [0.1 to 1.0]
    total_subtasks: int            # Total parallelizable work items
    serial_fraction: float          # Inherent Amdahl serial dependency fraction
    byzantine_noise_rate: float     # Inherent deception/trap probability in problem space


@dataclass
class TeamRunResult:
    team_size: int
    topology: str
    task_id: str
    wall_clock_time_sec: float
    effective_speedup: float
    total_tokens: int
    total_cost_usd: float
    success_rate: float
    conflict_count: int
    message_volume: int
    hallucinations_detected: int
    wasted_work_ratio: float


class ScalingEngine:
    """
    Executes rigorous empirical scaling experiments across team sizes and topologies.
    """

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        random.seed(random_seed)

    def run_team_experiment(
        self,
        team_size: int,
        task: BenchmarkTask,
        topology_type: TopologyType = TopologyType.HIERARCHICAL,
        model_tier: ModelTier = ModelTier.FAST,
        max_steps: int = 40,
    ) -> TeamRunResult:
        """
        Executes a collaborative task with a team of N agents.
        """
        # Create agents
        agent_ids = [f"agent_{i:02d}" for i in range(team_size)]
        agents: Dict[str, BoundedAgent] = {}
        
        # Role allocation:
        # For N >= 4: 1 Lead Architect, ~15% Verifiers, remainder Workers
        for i, aid in enumerate(agent_ids):
            if i == 0 and team_size > 1:
                role = AgentRole.ARCHITECT
            elif i >= max(1, int(team_size * 0.85)) and team_size >= 4:
                role = AgentRole.VERIFIER
            else:
                role = AgentRole.WORKER
            agents[aid] = BoundedAgent(agent_id=aid, role=role, tier=model_tier)

        # Build topology and bus
        topo_config = TopologyConfig(topology_type=topology_type)
        topology = TeamTopology(agent_ids, topo_config)
        bus = ResilientMessageBus()
        workspace = SharedWorkspace()

        # Task state tracking
        subtasks_remaining = task.total_subtasks
        completed_subtasks = 0
        wasted_subtasks = 0
        total_tokens = 0
        total_cost = 0.0
        total_messages = 0
        hallucinations = 0

        # Communication overhead calculation
        coord_overhead = topology.compute_communication_overhead_factor()

        # Serial barrier modeling: serial fraction can only be executed sequentially
        serial_work = task.total_subtasks * task.serial_fraction
        parallel_work = task.total_subtasks * (1.0 - task.serial_fraction)

        # Execution loop
        step = 0
        active_parallel_completed = 0.0
        active_serial_completed = 0.0

        while (active_parallel_completed < parallel_work or active_serial_completed < serial_work) and step < max_steps:
            step += 1
            step_messages = 0

            # 1. Parallel execution phase
            # Each worker attempts a chunk of parallel work
            workers = [a for a in agents.values() if a.role in (AgentRole.WORKER, AgentRole.ARCHITECT)]
            for worker in workers:
                if active_parallel_completed < parallel_work:
                    result = worker.step_reasoning(
                        task_difficulty=task.difficulty,
                        coordination_noise=coord_overhead,
                    )
                    total_tokens += result["input_tokens"] + result["output_tokens"]
                    total_cost += (result["input_tokens"] / 1000.0) * worker.profile.cost_per_1k_input_tokens + \
                                  (result["output_tokens"] / 1000.0) * worker.profile.cost_per_1k_output_tokens

                    if result["is_hallucination"]:
                        hallucinations += 1
                        # Hallucination introduces wasted rework
                        wasted_subtasks += 0.5
                    elif result["succeeded"]:
                        active_parallel_completed += 1.0

            # 2. Serial verification / integration phase (bottleneck)
            # Only architect / verifier or single agent can process serial barriers
            verifiers = [a for a in agents.values() if a.role in (AgentRole.ARCHITECT, AgentRole.VERIFIER)]
            verifier = verifiers[0] if verifiers else list(agents.values())[0]
            if active_serial_completed < serial_work:
                v_res = verifier.step_reasoning(
                    task_difficulty=task.difficulty,
                    coordination_noise=0.0,  # Serial execution doesn't suffer mesh noise
                )
                total_tokens += v_res["input_tokens"] + v_res["output_tokens"]
                total_cost += (v_res["input_tokens"] / 1000.0) * verifier.profile.cost_per_1k_input_tokens + \
                              (v_res["output_tokens"] / 1000.0) * verifier.profile.cost_per_1k_output_tokens
                if v_res["succeeded"]:
                    active_serial_completed += 1.0

            # 3. Inter-agent communication messages
            for aid, neighbors in topology.adjacency.items():
                for neighbor in neighbors:
                    step_messages += 1

            total_messages += step_messages

        # Calculate time & speedup
        # Base latency of 1 agent doing entire work:
        work_units = task.total_subtasks
        single_agent_time = (work_units / (1.0 - task.difficulty * 0.4)) * 1.5

        # Multi-agent wall-clock time is governed by critical path steps + communication latency
        comm_latency_penalty = 1.0 + coord_overhead * 0.5
        wall_clock = step * 1.5 * comm_latency_penalty

        # Effective speedup
        effective_speedup = single_agent_time / max(0.1, wall_clock)
        success_rate = min(1.0, (active_parallel_completed + active_serial_completed) / task.total_subtasks)
        wasted_ratio = wasted_subtasks / max(1.0, active_parallel_completed + active_serial_completed)

        return TeamRunResult(
            team_size=team_size,
            topology=topology_type.value,
            task_id=task.task_id,
            wall_clock_time_sec=round(wall_clock, 2),
            effective_speedup=round(effective_speedup, 3),
            total_tokens=int(total_tokens),
            total_cost_usd=round(total_cost, 4),
            success_rate=round(success_rate, 3),
            conflict_count=int(workspace.conflict_count + (hallucinations // 2)),
            message_volume=total_messages,
            hallucinations_detected=hallucinations,
            wasted_work_ratio=round(wasted_ratio, 3),
        )

    def run_scaling_sweep(
        self,
        team_sizes: List[int],
        task: BenchmarkTask,
        topology_type: TopologyType = TopologyType.HIERARCHICAL,
    ) -> List[TeamRunResult]:
        """Runs a scaling sweep over an array of team sizes."""
        results = []
        for n in team_sizes:
            res = self.run_team_experiment(team_size=n, task=task, topology_type=topology_type)
            results.append(res)
        return results
