"""
Unit and integration tests for Pillar 3: Fixed Compute Budget Allocation & Pareto Optimization.
"""

import pytest
from src.allocation.budget_optimizer import ComputeBudgetOptimizer
from src.allocation.stopping_rules import BranchTrajectory, SequentialStoppingEngine
from src.allocation.tiering_model import TieringModelAnalyzer


def test_budget_optimizer_pareto_frontier():
    optimizer = ComputeBudgetOptimizer(task_difficulty=0.75)
    strats = optimizer.optimize_for_budget(budget_usd=10.0)
    assert len(strats) > 0

    # Ensure at least one strategy is Pareto efficient
    pareto_count = sum(1 for s in strats if s.pareto_efficient)
    assert pareto_count >= 1

    # Ensure ranked by velocity score descending
    for i in range(len(strats) - 1):
        assert strats[i].velocity_score >= strats[i + 1].velocity_score


def test_sequential_stopping_sprt():
    engine = SequentialStoppingEngine()
    branch_good = BranchTrajectory(branch_id="good_branch")
    branch_bad = BranchTrajectory(branch_id="bad_branch")

    # Good branch receives repeated success signals
    for _ in range(5):
        engine.evaluate_step(branch_good, step_passed=True, cost_usd=0.01, tokens=200)
    assert branch_good.is_active is True
    assert branch_good.log_likelihood_ratio > 0

    # Bad branch receives repeated failure signals
    pruned = False
    for _ in range(8):
        cont, reason = engine.evaluate_step(branch_bad, step_passed=False, cost_usd=0.01, tokens=200)
        if not cont:
            pruned = True
            break
    assert pruned is True
    assert branch_bad.is_active is False
    assert "PRUNED" in branch_bad.terminated_reason


def test_tiering_model_analyzer():
    compositions = TieringModelAnalyzer.compare_standard_compositions()
    assert len(compositions) == 6
    for c in compositions:
        assert c.effective_team_intelligence > 0.5
        assert c.blended_cost_per_step > 0.0
