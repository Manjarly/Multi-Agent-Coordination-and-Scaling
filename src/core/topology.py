"""
Multi-Agent Network Topologies and Communication Graph Models.
Defines flat, hierarchical, star, ring, and dynamic-sparse communication structures,
computing theoretical communication complexity and routing graphs.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple


class TopologyType(str, Enum):
    FLAT = "FLAT"                    # All-to-all broadcast: O(N^2) messages
    HIERARCHICAL = "HIERARCHICAL"    # Tree hierarchy: O(N log N) / O(N) messages
    STAR = "STAR"                    # Centralized orchestrator: O(N) messages, single bottleneck
    RING = "RING"                    # Sequential peer relay: O(N) latency, O(N) messages
    DYNAMIC_SPARSE = "DYNAMIC_SPARSE"# Dynamic topic-based cluster pub/sub


@dataclass
class TopologyConfig:
    topology_type: TopologyType
    branching_factor: int = 4        # For hierarchical trees
    max_peers_per_agent: int = 8     # For dynamic sparse graphs


class TeamTopology:
    """
    Constructs and inspects communication graphs for a team of N agents.
    Provides routing tables, fanout counts, and theoretical communication overhead models.
    """

    def __init__(self, agent_ids: List[str], config: TopologyConfig):
        self.agent_ids = agent_ids
        self.config = config
        self.adjacency: Dict[str, Set[str]] = {aid: set() for aid in agent_ids}
        self.roles_map: Dict[str, str] = {}
        self._build_graph()

    def _build_graph(self) -> None:
        n = len(self.agent_ids)
        if n <= 1:
            return

        if self.config.topology_type == TopologyType.FLAT:
            # Full mesh: every agent connected to every other agent
            for i, aid1 in enumerate(self.agent_ids):
                for j, aid2 in enumerate(self.agent_ids):
                    if i != j:
                        self.adjacency[aid1].add(aid2)

        elif self.config.topology_type == TopologyType.STAR:
            # First agent is hub, all others are spokes
            hub = self.agent_ids[0]
            for spoke in self.agent_ids[1:]:
                self.adjacency[hub].add(spoke)
                self.adjacency[spoke].add(hub)

        elif self.config.topology_type == TopologyType.RING:
            # Ring: aid_i -> aid_{i+1} and vice-versa
            for i in range(n):
                prev_id = self.agent_ids[(i - 1) % n]
                next_id = self.agent_ids[(i + 1) % n]
                self.adjacency[self.agent_ids[i]].add(prev_id)
                self.adjacency[self.agent_ids[i]].add(next_id)

        elif self.config.topology_type == TopologyType.HIERARCHICAL:
            # Tree structure based on branching factor
            b = max(2, self.config.branching_factor)
            for i, aid in enumerate(self.agent_ids):
                parent_idx = (i - 1) // b if i > 0 else None
                if parent_idx is not None:
                    parent_id = self.agent_ids[parent_idx]
                    self.adjacency[aid].add(parent_id)
                    self.adjacency[parent_id].add(aid)

        elif self.config.topology_type == TopologyType.DYNAMIC_SPARSE:
            # Cluster agents into small topical groups
            k = min(self.config.max_peers_per_agent, max(2, int(math.sqrt(n))))
            for i, aid in enumerate(self.agent_ids):
                for offset in range(1, k + 1):
                    neighbor = self.agent_ids[(i + offset) % n]
                    self.adjacency[aid].add(neighbor)
                    self.adjacency[neighbor].add(aid)

    def get_neighbors(self, agent_id: str) -> List[str]:
        return sorted(list(self.adjacency.get(agent_id, set())))

    def get_total_edges(self) -> int:
        return sum(len(neighbors) for neighbors in self.adjacency.values()) // 2

    def compute_communication_overhead_factor(self) -> float:
        """
        Computes the relative coordination friction / cognitive overhead factor.
        In flat broadcast, overhead grows quadratically: O(N^2).
        In hierarchical, overhead grows logarithmically: O(log N).
        In star, bottleneck at the hub caps throughput: O(N) on hub.
        """
        n = len(self.agent_ids)
        if n <= 1:
            return 0.0

        if self.config.topology_type == TopologyType.FLAT:
            # Full mesh: information overload penalty
            # Scaling penalty ~ alpha * N^1.4
            return 0.015 * (n ** 1.35)
        elif self.config.topology_type == TopologyType.STAR:
            # Hub bottleneck penalty
            return 0.03 * (n ** 1.1)
        elif self.config.topology_type == TopologyType.HIERARCHICAL:
            # Tree aggregation penalty
            return 0.02 * math.log2(n + 1)
        elif self.config.topology_type == TopologyType.RING:
            # Latency delay penalty
            return 0.04 * (n ** 0.8)
        elif self.config.topology_type == TopologyType.DYNAMIC_SPARSE:
            return 0.025 * math.sqrt(n)

        return 0.02 * n
