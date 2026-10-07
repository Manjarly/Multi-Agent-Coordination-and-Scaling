"""
Unit and integration tests for Pillar 1: Scaling Laws & Inflection Curve Models.
"""

import pytest
from src.core.topology import TopologyType
from src.scaling.curve_analyzer import ScalingCurveAnalyzer
from src.scaling.models import MultiAgentScalingModel, ScalingLawParameters
from src.scaling.scaling_engine import BenchmarkTask, ScalingEngine


def test_scaling_model_inflection_points():
    params = ScalingLawParameters(serial_fraction=0.15, coordination_alpha=0.008, error_cascade_gamma=0.012)
    model = MultiAgentScalingModel(params)
    
    # Speedup at N=1 should be ~1.0
    s1 = model.effective_speedup(1.0)
    assert 0.95 <= s1 <= 1.05

    inflections = model.find_inflection_points(max_n=64)
    assert inflections["n_knee"] >= 2.0
    assert inflections["n_peak"] >= inflections["n_knee"]
    assert inflections["max_speedup"] > 1.5


def test_degradation_decomposition():
    params = ScalingLawParameters(serial_fraction=0.15, coordination_alpha=0.008, error_cascade_gamma=0.012)
    model = MultiAgentScalingModel(params)
    decomp = model.decompose_degradation(n=16)
    
    total = decomp["amdahl_serial_pct"] + decomp["coordination_pct"] + decomp["error_cascade_pct"]
    assert 99.0 <= total <= 101.0


def test_empirical_scaling_engine_and_analyzer():
    engine = ScalingEngine(random_seed=42)
    task = BenchmarkTask(
        task_id="TEST_TASK",
        name="Test Task",
        difficulty=0.5,
        total_subtasks=20,
        serial_fraction=0.1,
        byzantine_noise_rate=0.05,
    )
    results = engine.run_scaling_sweep([1, 2, 4, 8], task, topology_type=TopologyType.HIERARCHICAL)
    assert len(results) == 4
    assert results[0].team_size == 1
    assert results[-1].team_size == 8

    analyzer = ScalingCurveAnalyzer()
    report = analyzer.analyze(results)
    assert report.n_knee >= 1.0
    assert report.max_observed_speedup > 1.0
    assert len(report.actionable_recommendations) > 0
