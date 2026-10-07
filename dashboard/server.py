"""
Lightweight Research Dashboard Server.
Serves static dashboard assets and exposes JSON APIs for live experiment interrogation.
"""

from __future__ import annotations
import os
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.allocation.budget_optimizer import ComputeBudgetOptimizer
from src.evaluation.scep_protocol import ScepEvaluationEngine
from src.hardening.chaos_harness import ChaosStressTester
from src.hardening.preflight_orchestrator import HardenedPreFlightOrchestrator
from src.scaling.curve_analyzer import ScalingCurveAnalyzer
from src.scaling.models import MultiAgentScalingModel, ScalingLawParameters
from src.scaling.scaling_engine import BenchmarkTask, ScalingEngine
from src.core.topology import TopologyType

app = FastAPI(title="Anthropic Multi-Agent Scaling & Systems Research Lab")

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = os.path.join(DASHBOARD_DIR, "index.html")
    with open(index_file, "r") as f:
        return f.read()


@app.get("/styles.css")
def serve_css():
    return FileResponse(os.path.join(DASHBOARD_DIR, "styles.css"), media_type="text/css")


@app.get("/app.js")
def serve_js():
    return FileResponse(os.path.join(DASHBOARD_DIR, "app.js"), media_type="application/javascript")


@app.get("/api/scaling")
def get_scaling_data(s: float = 0.15, alpha: float = 0.008, gamma: float = 0.012) -> Dict[str, Any]:
    params = ScalingLawParameters(serial_fraction=s, coordination_alpha=alpha, error_cascade_gamma=gamma)
    model = MultiAgentScalingModel(params)
    inflections = model.find_inflection_points(max_n=64)
    degradation = model.decompose_degradation(n=16)

    # Empirical sweep
    engine = ScalingEngine()
    task = BenchmarkTask(
        task_id="HARD_SYNTHESIS",
        name="Distributed Synthesis",
        difficulty=0.75,
        total_subtasks=40,
        serial_fraction=s,
        byzantine_noise_rate=0.08,
    )
    sweep = engine.run_scaling_sweep(
        team_sizes=[1, 2, 4, 8, 16, 32, 64],
        task=task,
        topology_type=TopologyType.HIERARCHICAL,
    )
    analyzer = ScalingCurveAnalyzer()
    report = analyzer.analyze(sweep)

    return {
        "theoretical_inflections": inflections,
        "degradation_at_n16": degradation,
        "empirical_sweep": [s.__dict__ for s in sweep],
        "analysis_report": report.__dict__,
    }


@app.get("/api/hardening")
def get_hardening_status() -> Dict[str, Any]:
    orchestrator = HardenedPreFlightOrchestrator(num_agents=64, max_horizon=100)
    cert = orchestrator.run_preflight_certification()
    tester = ChaosStressTester()
    stress = tester.run_stress_test(num_agents=64, num_steps=50, chaos_intensity=0.3)
    return {
        "certification": cert.__dict__,
        "chaos_stress_report": stress.__dict__,
    }


@app.get("/api/allocation")
def get_allocation_data(budget: float = 10.0) -> Dict[str, Any]:
    optimizer = ComputeBudgetOptimizer()
    strategies = optimizer.optimize_for_budget(budget_usd=budget)
    return {
        "budget_usd": budget,
        "strategies": [s.__dict__ for s in strategies],
    }


@app.get("/api/scep")
def get_scep_data() -> Dict[str, Any]:
    engine = ScepEvaluationEngine()
    return engine.run_protocol()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
