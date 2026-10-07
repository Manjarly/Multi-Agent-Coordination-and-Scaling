"""
Mathematical Formulation of Multi-Agent Scaling Laws.
Models speedup, coordination friction, cascading hallucinations,
and derives inflection points (N_knee, N_peak).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class ScalingLawParameters:
    serial_fraction: float = 0.15          # Amdahl's serial fraction s in [0, 1]
    coordination_alpha: float = 0.008      # Communication overhead coefficient alpha
    coordination_beta: float = 1.35        # Communication scaling exponent beta (1.0 for star, 2.0 for flat)
    error_cascade_gamma: float = 0.012     # Cascading hallucination / Byzantine corruption coefficient


class MultiAgentScalingModel:
    """
    Generalized Multi-Agent Performance & Speedup Model.

    Effective Speedup:
        S(N) = 1 / [ s + (1 - s)/N + alpha * N^beta + gamma * N ]

    Marginal Efficiency:
        E(N) = S(N) / N

    Cost Function (total token / compute spend):
        C(N) = B_base * (1 + alpha * N^beta) * N
    """

    def __init__(self, params: ScalingLawParameters):
        self.params = params

    def effective_speedup(self, n: float) -> float:
        if n <= 0:
            return 0.0
        s = self.params.serial_fraction
        p = 1.0 - s
        coord_penalty = self.params.coordination_alpha * (n ** self.params.coordination_beta)
        error_penalty = self.params.error_cascade_gamma * n
        denominator = s + (p / n) + coord_penalty + error_penalty
        return 1.0 / max(1e-6, denominator)

    def marginal_speedup(self, n: float, delta: float = 1e-4) -> float:
        """First derivative dS/dN via finite difference."""
        s1 = self.effective_speedup(n - delta)
        s2 = self.effective_speedup(n + delta)
        return (s2 - s1) / (2.0 * delta)

    def curvature(self, n: float, delta: float = 1e-3) -> float:
        """Second derivative d^2S/dN^2."""
        d1 = self.marginal_speedup(n - delta)
        d2 = self.marginal_speedup(n + delta)
        return (d2 - d1) / (2.0 * delta)

    def find_inflection_points(self, max_n: int = 128) -> Dict[str, float]:
        """
        Calculates:
        - N_knee: Point of maximum diminishing returns (curvature elbow)
        - N_peak: Optimal team size where speedup peaks (dS/dN = 0)
        - Collapse_threshold: Point where S(N) drops below S(1) (negative net return)
        """
        best_n = 1
        max_speedup = self.effective_speedup(1)
        peak_found = False
        n_peak = 1.0

        # Scan for peak (dS/dN = 0)
        for n_int in range(1, max_n + 1):
            s = self.effective_speedup(n_int)
            if s > max_speedup:
                max_speedup = s
                best_n = n_int
            elif s < max_speedup and not peak_found:
                n_peak = float(best_n)
                peak_found = True

        if not peak_found:
            n_peak = float(best_n)

        # Scan for knee: where marginal gain drops below 25% of single-agent efficiency
        base_gain = self.marginal_speedup(1.5)
        knee_threshold = base_gain * 0.25
        n_knee = 1.0
        for n_val in [x * 0.25 for x in range(4, int(n_peak * 4) + 1)]:
            if self.marginal_speedup(n_val) <= knee_threshold:
                n_knee = n_val
                break

        # Scan for collapse: where S(N) < S(1)
        s1 = self.effective_speedup(1.0)
        n_collapse = float(max_n)
        for n_val in range(int(n_peak), max_n + 1):
            if self.effective_speedup(n_val) < s1:
                n_collapse = float(n_val)
                break

        return {
            "n_knee": round(n_knee, 2),
            "n_peak": round(n_peak, 2),
            "max_speedup": round(max_speedup, 3),
            "n_collapse": round(n_collapse, 2),
        }

    def decompose_degradation(self, n: float) -> Dict[str, float]:
        """
        Quantifies the percentage contribution of each penalty mechanism at team size N.
        """
        s = self.params.serial_fraction
        p = 1.0 - s
        ideal_denominator = s + (p / n)
        coord_penalty = self.params.coordination_alpha * (n ** self.params.coordination_beta)
        error_penalty = self.params.error_cascade_gamma * n
        total_loss = (s - (1.0 / n if n > 1 else 0)) + coord_penalty + error_penalty

        denom_total = coord_penalty + error_penalty + s
        if denom_total <= 0:
            return {"amdahl_serial_pct": 100.0, "coordination_pct": 0.0, "error_cascade_pct": 0.0}

        return {
            "amdahl_serial_pct": round(100.0 * (s / denom_total), 2),
            "coordination_pct": round(100.0 * (coord_penalty / denom_total), 2),
            "error_cascade_pct": round(100.0 * (error_penalty / denom_total), 2),
        }
