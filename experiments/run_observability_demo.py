"""
Experiment 4: Researcher Observability Tooling.
Turns thousands of raw swarm events into an executive researcher briefing in minutes
using Critical Path DAG extraction and Causal Pivot Point attribution.
"""

from __future__ import annotations
import json
import os
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import random

from src.observability.executive_synthesizer import ExecutiveSynthesizer
from src.observability.report_generator import ExecutiveReportGenerator
from src.observability.trajectory_tracer import TrajectoryTracer

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def run():
    print("=" * 70)
    print("PILLAR 4: RESEARCHER SWARM OBSERVABILITY TOOLING")
    print("=" * 70)

    tracer = TrajectoryTracer(run_id="RUN_FRONTIER_EXP_402")
    random.seed(42)

    # Simulate realistic 8-agent swarm run over 45 steps
    print("\n[+] Recording multi-agent execution events...")
    
    # Step 1-4: Architecture and decomposition
    e1 = tracer.record_event(
        step=1, agent_id="agent_00", role="ARCHITECT", event_type="REASONING",
        summary="Decomposing global objective into 4 decoupled submodules with formal contracts",
        latency_sec=1.4, tokens=850,
    )
    e2 = tracer.record_event(
        step=4, agent_id="agent_00", role="ARCHITECT", event_type="MILESTONE",
        summary="Locked Module Contract Specification v1.0",
        parent_event_ids=[e1.event_id], latency_sec=0.8, tokens=600,
    )

    # Step 5-15: Parallel worker execution
    worker_events = []
    for step in range(5, 16):
        aid = f"agent_{random.randint(1, 5):02d}"
        ev = tracer.record_event(
            step=step, agent_id=aid, role="WORKER", event_type="REASONING",
            summary=f"Implementing subtask components for {aid}",
            parent_event_ids=[e2.event_id], latency_sec=0.45, tokens=420,
        )
        worker_events.append(ev)

    # Step 18: Refutation of faulty mutex proposal
    bad_w = tracer.record_event(
        step=17, agent_id="agent_03", role="WORKER", event_type="REASONING",
        summary="Proposing shared mutex ring buffer",
        latency_sec=0.5, tokens=350,
    )
    refutation = tracer.record_event(
        step=18, agent_id="agent_06", role="VERIFIER", event_type="VERIFICATION",
        summary="REFUTED mutex proposal: 3-agent circular deadlock proof constructed",
        parent_event_ids=[bad_w.event_id], latency_sec=0.9, tokens=520,
    )
    tracer.mark_wasted_work({bad_w.event_id})

    # Step 31: OCC conflict replay
    occ_ev = tracer.record_event(
        step=31, agent_id="agent_02", role="WORKER", event_type="CONFLICT",
        summary="Concurrent patch collision on telemetry state; auto-replayed via OCC journal",
        latency_sec=0.4, tokens=280,
    )

    # Step 42: Final Quorum Consensus
    consensus_ev = tracer.record_event(
        step=42, agent_id="agent_07", role="VERIFIER", event_type="MILESTONE",
        summary="Dual-quorum formal verification passed for all joint system invariants",
        parent_event_ids=[refutation.event_id, occ_ev.event_id], latency_sec=1.1, tokens=950,
    )

    # Synthesize
    print("\n[+] Running Executive Synthesis & Causal Pivot Extraction...")
    synthesizer = ExecutiveSynthesizer()
    summary = synthesizer.synthesize(tracer)

    print("\n" + "=" * 50)
    print("RESEARCHER EXECUTIVE SUMMARY:")
    print(f"  Run ID                  : {summary.run_id}")
    print(f"  Total Agents            : {summary.total_agents}")
    print(f"  Total Steps             : {summary.total_steps}")
    print(f"  Total Events Recorded   : {summary.total_events}")
    print(f"  Total Tokens            : {summary.total_tokens:,}")
    print(f"  Critical Path Latency   : {summary.critical_path_latency_sec}s")
    print(f"  Parallel Efficiency     : {summary.parallel_efficiency_pct}%")
    print(f"  Wasted Exploration Spend: {summary.wasted_tokens_pct}%")
    print(f"  Causal Pivots Extracted : {len(summary.causal_pivots)}")
    print("=" * 50)

    # Generate Markdown Report
    report_generator = ExecutiveReportGenerator()
    report_md = report_generator.render_markdown(summary)

    rep_path = os.path.join(RESULTS_DIR, "swarm_executive_briefing.md")
    with open(rep_path, "w") as f:
        f.write(report_md)
    print(f"\n[✓] Saved 1-page researcher briefing to {rep_path}")

    # Export trace JSON
    trace_path = os.path.join(RESULTS_DIR, "swarm_trajectory_events.json")
    with open(trace_path, "w") as f:
        f.write(tracer.export_trace_json())
    print(f"[✓] Saved DAG event trajectory to {trace_path}\n")


if __name__ == "__main__":
    run()
