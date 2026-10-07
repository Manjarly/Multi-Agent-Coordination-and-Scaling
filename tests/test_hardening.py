"""
Unit and integration tests for Pillar 2: Pre-Flight Hardening & Chaos Testing.
"""

import pytest
from src.core.state import EpistemicAssertion, InvariantStatus, SharedWorkspace, StatePatch, VectorClock
from src.hardening.byzantine_filter import ByzantineEpistemicGateway
from src.hardening.chaos_harness import ChaosStressTester
from src.hardening.context_compactor import HierarchicalContextCompactor
from src.hardening.preflight_orchestrator import HardenedPreFlightOrchestrator


def test_occ_concurrency_and_vector_clocks():
    ws = SharedWorkspace()
    clock1 = VectorClock()
    clock1.increment("agent_01")

    # Patch 1: clean apply
    p1 = StatePatch(
        patch_id="p1",
        agent_id="agent_01",
        base_version=0,
        target_key="config_a",
        operation="set",
        payload={"timeout": 30},
        vector_clock=clock1,
    )
    ok1, _ = ws.propose_patch(p1)
    assert ok1 is True
    assert ws.version == 1
    assert ws.get("config_a") == {"timeout": 30}

    # Patch 2: concurrent conflicting write based on stale base_version=0
    clock2 = VectorClock()
    clock2.increment("agent_02")
    p2 = StatePatch(
        patch_id="p2",
        agent_id="agent_02",
        base_version=0,  # stale!
        target_key="config_a",
        operation="set",
        payload={"timeout": 60},
        vector_clock=clock2,
    )
    ok2, err2 = ws.propose_patch(p2)
    assert ok2 is False
    assert "OCC Conflict" in err2


def test_byzantine_quorum_gateway():
    gateway = ByzantineEpistemicGateway(required_quorum=2)
    ws = SharedWorkspace()

    # Valid assertion
    good = EpistemicAssertion(
        assertion_id="claim_good",
        author_id="agent_01",
        claim_type="lemma",
        content="x > 0",
        confidence=0.9,
    )
    gateway.submit_assertion(good, ws)
    status = gateway.evaluate_quorum("claim_good", ws, [("agent_02", True), ("agent_03", True)])
    assert status == InvariantStatus.VERIFIED

    # Poison assertion refuted by verifier
    poison = EpistemicAssertion(
        assertion_id="claim_poison",
        author_id="agent_04",
        claim_type="lemma",
        content="1 == 0",
        confidence=0.99,
    )
    gateway.submit_assertion(poison, ws)
    status_p = gateway.evaluate_quorum("claim_poison", ws, [("agent_02", False)])
    assert status_p == InvariantStatus.REFUTED
    assert len(gateway.quarantined_claims) == 1


def test_context_compactor():
    compactor = HierarchicalContextCompactor(target_checkpoint_interval=5)
    clock = VectorClock()
    events = [{"type": "STEP", "tokens": 100} for _ in range(10)]
    assertions = [
        EpistemicAssertion("a1", "agent_1", "lemma", "Inv1", 0.9, status=InvariantStatus.VERIFIED),
        EpistemicAssertion("a2", "agent_2", "lemma", "Inv2", 0.9, status=InvariantStatus.REFUTED),
    ]
    milestone = compactor.compact_trajectory(1, 10, events, assertions, clock)
    assert milestone.compression_ratio > 1.0
    assert len(milestone.canonical_invariants) == 1
    assert len(milestone.rejected_hypotheses) == 1


def test_chaos_stress_tester():
    tester = ChaosStressTester(random_seed=42)
    report = tester.run_stress_test(num_agents=16, num_steps=20, chaos_intensity=0.3)
    assert report.system_survived is True
    assert report.state_corruption_detected is False
