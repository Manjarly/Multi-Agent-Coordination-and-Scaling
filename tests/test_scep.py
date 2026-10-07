"""
Unit and integration tests for Pillar 5: SCEP Novel Teamwork Synergy Evaluation.
"""

import pytest
from src.evaluation.metrics import SynergyEvaluationResult, SynergyMetricsCalculator
from src.evaluation.scep_protocol import ScepEvaluationEngine
from src.evaluation.tasks import AsymmetricTaskSpec, NonFactorableTaskRegistry


def test_asymmetric_task_registry_and_evaluation():
    task = NonFactorableTaskRegistry.get_asymmetric_synthesis_task()
    assert task.num_roles == 4
    assert len(task.agent_private_constraints) == 4

    # Perfect solution achieves 1.0
    perfect = task.ground_truth_solution
    score, violations = NonFactorableTaskRegistry.evaluate_solution(task, perfect)
    assert score == 1.0
    assert len(violations) == 0

    # Partial solution achieves lower score
    partial = {"selected_components": ["zero_trust_mTLS", "aes_256_gcm"]}
    p_score, p_violations = NonFactorableTaskRegistry.evaluate_solution(task, partial)
    assert 0.0 < p_score < 0.5
    assert len(p_violations) > 0


def test_synergy_metrics_calculator():
    # Case 1: Genuine synergy (Coop dominates all baselines)
    res_synergy = SynergyMetricsCalculator.calculate(
        score_coop=0.92,
        score_ensemble=0.35,
        score_single_iso=0.30,
        score_scrambled=0.25,
        baseline_single_shot=0.20,
    )
    assert res_synergy.true_synergy_delta > 0.5
    assert res_synergy.is_statistically_significant is True
    assert "GENUINE_TEAMWORK_SYNERGY" in res_synergy.verdict

    # Case 2: Ensembling artifact (Pass@k explains almost all apparent gain)
    res_artifact = SynergyMetricsCalculator.calculate(
        score_coop=0.88,
        score_ensemble=0.86,
        score_single_iso=0.85,
        score_scrambled=0.82,
        baseline_single_shot=0.70,
    )
    assert res_artifact.true_synergy_delta <= 0.03
    assert res_artifact.ensembling_confounder_fraction > 0.8
    assert "EQUIVALENT_TO_COUNTERFACTUALS" in res_artifact.verdict


def test_scep_protocol_execution():
    engine = ScepEvaluationEngine(random_seed=42)
    eval_res = engine.run_protocol()
    assert "non_factorable_benchmark" in eval_res
    assert "factorable_benchmark" in eval_res
    assert eval_res["non_factorable_benchmark"].true_synergy_delta > 0.4
    assert eval_res["factorable_benchmark"].ensembling_confounder_fraction > 0.8
