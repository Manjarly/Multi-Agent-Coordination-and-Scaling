"""
Dynamic Early Stopping and Sequential Branch Pruning (Wald's SPRT).
Prevents compute wastage on unproductive or hallucinated exploration branches
by dynamically reallocating remaining budget to high-probability solution paths.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class BranchTrajectory:
    branch_id: str
    steps_taken: int = 0
    tokens_consumed: int = 0
    cumulative_cost_usd: float = 0.0
    verified_invariants: int = 0
    refutations_encountered: int = 0
    log_likelihood_ratio: float = 0.0
    is_active: bool = True
    terminated_reason: Optional[str] = None


class SequentialStoppingEngine:
    """
    Implements Sequential Probability Ratio Test (SPRT) with dynamic thresholds.
    Terminates dead-end agent reasoning paths and reclaims compute budget.
    """

    def __init__(
        self,
        alpha_type1_error: float = 0.05,  # False positive threshold (pruning a good branch)
        beta_type2_error: float = 0.10,   # False negative threshold (keeping a bad branch)
        p0_bad_branch_success: float = 0.20,
        p1_good_branch_success: float = 0.75,
    ):
        self.upper_bound_A = math.log((1.0 - beta_type2_error) / alpha_type1_error)
        self.lower_bound_B = math.log(beta_type2_error / (1.0 - alpha_type1_error))
        self.p0 = p0_bad_branch_success
        self.p1 = p1_good_branch_success

    def evaluate_step(
        self,
        branch: BranchTrajectory,
        step_passed: bool,
        cost_usd: float,
        tokens: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Updates branch likelihood ratio and decides whether to CONTINUE, ACCEPT, or PRUNE.
        Returns (should_continue, termination_reason).
        """
        if not branch.is_active:
            return False, branch.terminated_reason

        branch.steps_taken += 1
        branch.tokens_consumed += tokens
        branch.cumulative_cost_usd += cost_usd

        # Sequential log-likelihood ratio update
        if step_passed:
            branch.verified_invariants += 1
            llr_step = math.log(self.p1 / self.p0)
        else:
            branch.refutations_encountered += 1
            llr_step = math.log((1.0 - self.p1) / (1.0 - self.p0))

        branch.log_likelihood_ratio += llr_step

        # Decision rules
        if branch.log_likelihood_ratio <= self.lower_bound_B:
            # Reached lower rejection threshold: prune branch
            branch.is_active = False
            branch.terminated_reason = "PRUNED_BY_SPRT_LOW_CONFIDENCE"
            return False, "PRUNED_BY_SPRT_LOW_CONFIDENCE"

        if branch.steps_taken >= 15 and branch.verified_invariants == 0:
            # Hard horizon timeout for unproductive paths
            branch.is_active = False
            branch.terminated_reason = "PRUNED_HARD_TIMEOUT_ZERO_PROGRESS"
            return False, "PRUNED_HARD_TIMEOUT_ZERO_PROGRESS"

        return True, None
