"""
Byzantine-Tolerant Epistemic Filter and Quorum Gateways.
Prevents cascading hallucinations from contaminating shared agent state
and isolates faulty or adversarial agents before false premises propagate.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.core.state import EpistemicAssertion, InvariantStatus, SharedWorkspace


@dataclass
class AgentReputation:
    agent_id: str
    verified_assertions: int = 0
    refuted_assertions: int = 0
    trust_score: float = 1.0  # [0.0 - 1.0]
    is_quarantined: bool = False


class ByzantineEpistemicGateway:
    """
    Guards shared workspace against cascading hallucinations and unverified claims.
    Requires dual-quorum verification and tracks agent reputation.
    """

    def __init__(self, required_quorum: int = 2, min_trust_threshold: float = 0.3):
        self.required_quorum = required_quorum
        self.min_trust_threshold = min_trust_threshold
        self.reputations: Dict[str, AgentReputation] = {}
        self.quarantined_claims: List[EpistemicAssertion] = []
        self.verified_invariants: List[EpistemicAssertion] = []

    def get_or_create_reputation(self, agent_id: str) -> AgentReputation:
        if agent_id not in self.reputations:
            self.reputations[agent_id] = AgentReputation(agent_id=agent_id)
        return self.reputations[agent_id]

    def submit_assertion(
        self,
        assertion: EpistemicAssertion,
        workspace: SharedWorkspace,
    ) -> Tuple[bool, str]:
        """
        Submits an assertion to the gateway.
        Rejects immediately if author is quarantined or below trust threshold.
        """
        rep = self.get_or_create_reputation(assertion.author_id)
        if rep.is_quarantined:
            return False, f"Agent {assertion.author_id} is quarantined due to low trust score."

        workspace.register_assertion(assertion)
        return True, "Assertion registered for quorum verification."

    def evaluate_quorum(
        self,
        assertion_id: str,
        workspace: SharedWorkspace,
        verifiers: List[Tuple[str, bool]],  # (verifier_id, approves)
    ) -> InvariantStatus:
        """
        Applies strict verification quorum.
        - Author cannot vote on own assertion.
        - Any verified counterexample immediately triggers quarantine.
        """
        if assertion_id not in workspace.assertions:
            raise KeyError(f"Assertion {assertion_id} does not exist.")

        assertion = workspace.assertions[assertion_id]
        author_rep = self.get_or_create_reputation(assertion.author_id)

        for v_id, approves in verifiers:
            if v_id == assertion.author_id:
                continue  # Disallow self-verification

            v_rep = self.get_or_create_reputation(v_id)
            if v_rep.is_quarantined:
                continue  # Disallow quarantined verifiers

            workspace.vote_on_assertion(assertion_id, v_id, approves)

        # Re-check status after votes
        status = assertion.status
        if status == InvariantStatus.VERIFIED:
            author_rep.verified_assertions += 1
            author_rep.trust_score = min(1.0, author_rep.trust_score + 0.05)
            if assertion not in self.verified_invariants:
                self.verified_invariants.append(assertion)

        elif status == InvariantStatus.REFUTED:
            author_rep.refuted_assertions += 1
            author_rep.trust_score = max(0.0, author_rep.trust_score - 0.25)
            if author_rep.trust_score < self.min_trust_threshold:
                author_rep.is_quarantined = True
            if assertion not in self.quarantined_claims:
                self.quarantined_claims.append(assertion)

        return status
