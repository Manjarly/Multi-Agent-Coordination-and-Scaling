"""
Swarm Trajectory Tracer and Critical Path Dependency Analyzer.
Captures fine-grained agent events and computes the critical path of actions
that determined total execution time and solution discovery.
"""

from __future__ import annotations
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx


@dataclass
class SwarmEvent:
    event_id: str
    step: int
    timestamp: float
    agent_id: str
    role: str
    event_type: str         # 'REASONING', 'TOOL_CALL', 'ASSERTION', 'VERIFICATION', 'CONFLICT', 'MILESTONE'
    summary: str
    details: Dict[str, Any]
    parent_event_ids: List[str] = field(default_factory=list)
    latency_sec: float = 0.5
    tokens: int = 150
    is_critical_path: bool = False
    is_wasted_work: bool = False


class TrajectoryTracer:
    """
    Records swarm execution graphs and computes DAG metrics,
    critical path latency, and wasted work percentages.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: List[SwarmEvent] = []
        self.events_by_id: Dict[str, SwarmEvent] = {}
        self.dep_graph = nx.DiGraph()

    def record_event(
        self,
        step: int,
        agent_id: str,
        role: str,
        event_type: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
        parent_event_ids: Optional[List[str]] = None,
        latency_sec: float = 0.5,
        tokens: int = 150,
    ) -> SwarmEvent:
        event_id = f"ev_{len(self.events):04d}"
        ev = SwarmEvent(
            event_id=event_id,
            step=step,
            timestamp=time.time(),
            agent_id=agent_id,
            role=role,
            event_type=event_type,
            summary=summary,
            details=details or {},
            parent_event_ids=parent_event_ids or [],
            latency_sec=latency_sec,
            tokens=tokens,
        )
        self.events.append(ev)
        self.events_by_id[event_id] = ev

        # Add node to dependency graph
        self.dep_graph.add_node(event_id, weight=latency_sec, data=ev)
        for parent_id in ev.parent_event_ids:
            if parent_id in self.events_by_id:
                self.dep_graph.add_edge(parent_id, event_id, weight=latency_sec)

        return ev

    def compute_critical_path(self) -> List[SwarmEvent]:
        """
        Computes the longest latency path (critical path) through the DAG.
        Marks events as is_critical_path = True.
        """
        if not nx.is_directed_acyclic_graph(self.dep_graph) or len(self.dep_graph) == 0:
            # Fallback for empty or cyclic graphs
            return self.events[:5]

        try:
            # nx.dag_longest_path finds path with maximum number of nodes or weighted
            crit_ids = nx.dag_longest_path(self.dep_graph, weight="weight")
            for cid in crit_ids:
                if cid in self.events_by_id:
                    self.events_by_id[cid].is_critical_path = True
            return [self.events_by_id[cid] for cid in crit_ids]
        except Exception:
            return self.events[:5]

    def mark_wasted_work(self, dead_end_event_ids: Set[str]) -> None:
        """Marks branches that were pruned or refuted as wasted work."""
        for eid in dead_end_event_ids:
            if eid in self.events_by_id:
                self.events_by_id[eid].is_wasted_work = True
                # Propagate to descendants
                try:
                    descendants = nx.descendants(self.dep_graph, eid)
                    for desc_id in descendants:
                        if desc_id in self.events_by_id:
                            self.events_by_id[desc_id].is_wasted_work = True
                except Exception:
                    pass

    def export_trace_json(self) -> str:
        return json.dumps([asdict(e) for e in self.events], indent=2)
