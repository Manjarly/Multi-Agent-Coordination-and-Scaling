"""
Unit and integration tests for Pillar 4: Researcher Swarm Observability Tooling.
"""

import pytest
from src.observability.executive_synthesizer import ExecutiveSynthesizer
from src.observability.report_generator import ExecutiveReportGenerator
from src.observability.trajectory_tracer import TrajectoryTracer


def test_trajectory_tracer_and_critical_path():
    tracer = TrajectoryTracer(run_id="test_run_01")
    e1 = tracer.record_event(1, "agent_00", "ARCHITECT", "REASONING", "Root decomposition", latency_sec=1.0)
    e2 = tracer.record_event(2, "agent_01", "WORKER", "REASONING", "Child execution", parent_event_ids=[e1.event_id], latency_sec=2.0)
    e3 = tracer.record_event(3, "agent_02", "VERIFIER", "MILESTONE", "Verification", parent_event_ids=[e2.event_id], latency_sec=1.5)

    crit_path = tracer.compute_critical_path()
    assert len(crit_path) >= 2
    assert any(e.is_critical_path for e in tracer.events)


def test_executive_synthesizer_and_report_generator():
    tracer = TrajectoryTracer(run_id="test_run_02")
    e1 = tracer.record_event(1, "agent_00", "ARCHITECT", "MILESTONE", "Architecture locked", latency_sec=1.0, tokens=500)
    e2 = tracer.record_event(2, "agent_01", "WORKER", "CONFLICT", "OCC write conflict", latency_sec=0.5, tokens=200)
    e3 = tracer.record_event(3, "agent_02", "VERIFIER", "VERIFICATION", "REFUTED deadlock branch", latency_sec=0.8, tokens=300)

    synthesizer = ExecutiveSynthesizer()
    summary = synthesizer.synthesize(tracer)

    assert summary.total_agents == 3
    assert len(summary.causal_pivots) == 3
    assert summary.critical_path_latency_sec > 0

    report_md = ExecutiveReportGenerator.render_markdown(summary)
    assert "# Executive Run Briefing" in report_md
    assert "mermaid" in report_md
