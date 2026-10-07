"""
Intrinsically Non-Factorable Benchmark Tasks for Multi-Agent Synergy Evaluation.
These tasks are mathematically constructed so that no single agent possessing
only local information can solve the problem alone, requiring genuine inter-agent collaboration.
"""

from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple


@dataclass
class AsymmetricTaskSpec:
    task_id: str
    name: str
    global_objective: str
    num_roles: int
    agent_private_constraints: Dict[str, Dict[str, Any]]
    global_evaluator_code: str
    ground_truth_solution: Dict[str, Any]


class NonFactorableTaskRegistry:
    """
    Supplies evaluation tasks with asymmetric information partitions
    and coupled multi-agent constraint satisfaction.
    """

    @staticmethod
    def get_asymmetric_synthesis_task() -> AsymmetricTaskSpec:
        """
        Asymmetric Multi-Constraint Architectural Synthesis (AMCAS):
        4 agents each receive private, non-overlapping system requirements:
        - Agent 0 (Security Officer): Confidentiality bounds, key rotation, zero-trust auth
        - Agent 1 (Performance Architect): Latency < 15ms, p99 memory < 256MB, zero locks
        - Agent 2 (Reliability Lead): Byzantine fault tolerance, idempotency keys, quorum 3
        - Agent 3 (Compliance Auditor): Audit trails, immutable ledger, GDPR data scrubbing

        A candidate architecture must satisfy ALL joint constraints simultaneously.
        """
        private_constraints = {
            "agent_00": {
                "role": "Security",
                "rules": ["zero_trust_mTLS", "aes_256_gcm", "ephemeral_session_keys"],
                "disallowed": ["plain_jwt", "shared_db_passwords"],
            },
            "agent_01": {
                "role": "Performance",
                "rules": ["lock_free_ring_buffer", "memory_pool_prealloc", "simd_vectorized"],
                "disallowed": ["mutex_locks", "heavy_reflection", "blocking_io"],
            },
            "agent_02": {
                "role": "Reliability",
                "rules": ["raft_consensus_quorum", "idempotency_tokens", "exponential_jitter_retry"],
                "disallowed": ["single_point_of_failure", "silent_drop"],
            },
            "agent_03": {
                "role": "Compliance",
                "rules": ["cryptographic_audit_log", "deterministic_pseudonymization", "immutable_journal"],
                "disallowed": ["unlogged_admin_access", "unencrypted_pii"],
            },
        }

        ground_truth = {
            "architecture_name": "ZeroTrust-LockFree-Raft-Audit-Engine",
            "selected_components": [
                "zero_trust_mTLS", "aes_256_gcm", "ephemeral_session_keys",
                "lock_free_ring_buffer", "memory_pool_prealloc", "simd_vectorized",
                "raft_consensus_quorum", "idempotency_tokens", "exponential_jitter_retry",
                "cryptographic_audit_log", "deterministic_pseudonymization", "immutable_journal"
            ],
            "rejected_components": [
                "plain_jwt", "mutex_locks", "single_point_of_failure", "unlogged_admin_access"
            ]
        }

        return AsymmetricTaskSpec(
            task_id="AMCAS_01",
            name="Asymmetric Multi-Constraint Architectural Synthesis",
            global_objective="Design a high-frequency, fault-tolerant, compliant distributed transaction core.",
            num_roles=4,
            agent_private_constraints=private_constraints,
            global_evaluator_code="verify_joint_constraints",
            ground_truth_solution=ground_truth,
        )

    @staticmethod
    def evaluate_solution(task: AsymmetricTaskSpec, proposed_solution: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Evaluates a candidate solution against all asymmetric private constraints.
        Returns (score in [0.0, 1.0], list of constraint violations).
        """
        selected = set(proposed_solution.get("selected_components", []))
        violations = []
        satisfied_rules = 0
        total_rules = 0

        for aid, c in task.agent_private_constraints.items():
            for rule in c["rules"]:
                total_rules += 1
                if rule in selected:
                    satisfied_rules += 1
                else:
                    violations.append(f"Missing required constraint from {c['role']}: '{rule}'")

            for disallowed in c["disallowed"]:
                if disallowed in selected:
                    violations.append(f"VIOLATION of {c['role']} constraint: included disallowed '{disallowed}'")
                    satisfied_rules = max(0, satisfied_rules - 1)

        score = satisfied_rules / max(1, total_rules)
        return max(0.0, min(1.0, score)), violations
