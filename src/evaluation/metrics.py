"""
Synergy Metrics and Confounder Disentanglement Formulations.
Provides mathematical definitions to isolate genuine teamwork synergy
from ensembling artifacts (pass@k) and token scaling artifacts.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class SynergyEvaluationResult:
    score_cooperative_team: float           # Condition A
    score_independent_ensemble: float       # Condition B (Pass@N / Best-of-N)
    score_iso_budget_single_agent: float    # Condition C (Iso-tokens test-time compute)
    score_scrambled_communication: float    # Condition D (Ablated/noise communication)
    true_synergy_delta: float               # S_true
    ensembling_confounder_fraction: float   # How much of apparent gain was just pass@k
    token_scaling_confounder_fraction: float# How much was just more compute tokens
    is_statistically_significant: bool
    verdict: str


class SynergyMetricsCalculator:
    """
    Computes rigorous teamwork metrics that isolate real collaboration from eval artifacts.
    """

    @staticmethod
    def calculate(
        score_coop: float,
        score_ensemble: float,
        score_single_iso: float,
        score_scrambled: float,
        baseline_single_shot: float = 0.25,
    ) -> SynergyEvaluationResult:
        """
        True Synergy:
            S_true = Score_coop - max(Score_ensemble, Score_single_iso, Score_scrambled)
        """
        # Highest counterfactual baseline
        max_counterfactual = max(score_ensemble, score_single_iso, score_scrambled)
        s_true = score_coop - max_counterfactual

        # Total apparent gain above single-shot baseline
        apparent_gain = max(1e-5, score_coop - baseline_single_shot)

        # Ensembling confounder fraction:
        # What fraction of the gain over baseline is achieved simply by running N independent passes?
        ensemble_gain = max(0.0, score_ensemble - baseline_single_shot)
        ensemble_confounder = min(1.0, ensemble_gain / apparent_gain)

        # Token scaling confounder fraction:
        # What fraction of the gain is achieved simply by giving 1 agent N-times the tokens?
        token_gain = max(0.0, score_single_iso - baseline_single_shot)
        token_confounder = min(1.0, token_gain / apparent_gain)

        # Statistical significance check (delta > threshold)
        significant = s_true >= 0.08

        if s_true > 0.05:
            verdict = "GENUINE_TEAMWORK_SYNERGY: Performance super-additive; exceeds all counterfactual controls."
        elif s_true >= -0.02:
            verdict = "EQUIVALENT_TO_COUNTERFACTUALS: Multi-agent gains are fully explained by ensembling or token scale."
        else:
            verdict = "NEGATIVE_COORDINATION_TAX: Team communication reduced performance relative to isolated baselines."

        return SynergyEvaluationResult(
            score_cooperative_team=round(score_coop, 3),
            score_independent_ensemble=round(score_ensemble, 3),
            score_iso_budget_single_agent=round(score_single_iso, 3),
            score_scrambled_communication=round(score_scrambled, 3),
            true_synergy_delta=round(s_true, 3),
            ensembling_confounder_fraction=round(ensemble_confounder, 3),
            token_scaling_confounder_fraction=round(token_confounder, 3),
            is_statistically_significant=significant,
            verdict=verdict,
        )
