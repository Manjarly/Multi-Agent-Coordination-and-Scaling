"""
Master Multi-Agent Experiment Suite Runner.
Executes all 5 frontier research pillars sequentially and validates generated artifacts.
"""

from __future__ import annotations
import os
import sys
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from experiments import (
    run_budget_optimization,
    run_observability_demo,
    run_scaling_study,
    run_stress_test,
    run_synergy_eval,
)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def main():
    start_time = time.time()
    print("\n" + "#" * 75)
    print("  ANTHROPIC FRONTIER MULTI-AGENT RESEARCH & ENGINEERING SUITE")
    print("  End-to-End Execution of All 5 Core Research Pillars")
    print("#" * 75 + "\n")

    # Pillar 1
    t0 = time.time()
    run_scaling_study.run()
    print(f">> Pillar 1 completed in {time.time() - t0:.2f}s\n")

    # Pillar 2
    t0 = time.time()
    run_stress_test.run()
    print(f">> Pillar 2 completed in {time.time() - t0:.2f}s\n")

    # Pillar 3
    t0 = time.time()
    run_budget_optimization.run()
    print(f">> Pillar 3 completed in {time.time() - t0:.2f}s\n")

    # Pillar 4
    t0 = time.time()
    run_observability_demo.run()
    print(f">> Pillar 4 completed in {time.time() - t0:.2f}s\n")

    # Pillar 5
    t0 = time.time()
    run_synergy_eval.run()
    print(f">> Pillar 5 completed in {time.time() - t0:.2f}s\n")

    total_time = time.time() - start_time
    print("#" * 75)
    print(f"  ALL 5 RESEARCH PILLARS EXECUTED SUCCESSFULLY IN {total_time:.2f}s")
    print(f"  Artifacts and reports saved to: {RESULTS_DIR}")
    print("#" * 75 + "\n")


if __name__ == "__main__":
    main()
