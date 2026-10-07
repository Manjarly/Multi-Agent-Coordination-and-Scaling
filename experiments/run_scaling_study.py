"""
Experiment 1: Multi-Agent Scaling Laws on Hard Problems.
Measures performance scaling with N, computes inflection points (N_knee, N_peak),
decomposes degradation mechanisms, and exports empirical data and plots.
"""

from __future__ import annotations
import json
import os
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from src.core.topology import TopologyType
from src.scaling.curve_analyzer import ScalingCurveAnalyzer
from src.scaling.models import MultiAgentScalingModel, ScalingLawParameters
from src.scaling.scaling_engine import BenchmarkTask, ScalingEngine

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def run():
    print("=" * 70)
    print("PILLAR 1: MULTI-AGENT SCALING LAWS EXPERIMENT")
    print("=" * 70)

    engine = ScalingEngine(random_seed=42)
    task = BenchmarkTask(
        task_id="HARD_FORMAL_SYNTHESIS",
        name="Distributed Architectural Synthesis & Verification",
        difficulty=0.80,
        total_subtasks=50,
        serial_fraction=0.15,
        byzantine_noise_rate=0.08,
    )

    team_sizes = [1, 2, 4, 8, 16, 32, 64]

    # Run sweeps for Hierarchical vs Flat topologies
    print("\n[+] Running empirical sweep for HIERARCHICAL topology...")
    hier_results = engine.run_scaling_sweep(team_sizes, task, topology_type=TopologyType.HIERARCHICAL)

    print("\n[+] Running empirical sweep for FLAT BROADCAST topology...")
    flat_results = engine.run_scaling_sweep(team_sizes, task, topology_type=TopologyType.FLAT)

    analyzer = ScalingCurveAnalyzer()
    hier_report = analyzer.analyze(hier_results)
    flat_report = analyzer.analyze(flat_results)

    print("\n" + "=" * 50)
    print("SCALING ANALYSIS RESULTS (HIERARCHICAL):")
    print(f"  Knee of Curve (N_knee) : {hier_report.n_knee}")
    print(f"  Peak Speedup (N*)      : {hier_report.n_peak} (Max Speedup: {hier_report.max_observed_speedup}x)")
    print(f"  Collapse Threshold     : {hier_report.n_collapse}")
    print(f"  Degradation Breakdown  : Amdahl={hier_report.serial_bottleneck_pct}%, Comm={hier_report.communication_overhead_pct}%, Error={hier_report.hallucination_cascade_pct}%")
    print("=" * 50)

    # Save JSON data
    payload = {
        "hierarchical_sweep": [r.__dict__ for r in hier_results],
        "flat_sweep": [r.__dict__ for r in flat_results],
        "hierarchical_report": hier_report.__dict__,
        "flat_report": flat_report.__dict__,
    }
    json_path = os.path.join(RESULTS_DIR, "scaling_laws_data.json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\n[✓] Saved raw data to {json_path}")

    # Plot figure
    plt.figure(figsize=(10, 6), dpi=150)
    ns = [r.team_size for r in hier_results]
    s_hier = [r.effective_speedup for r in hier_results]
    s_flat = [r.effective_speedup for r in flat_results]

    plt.plot(ns, s_hier, 'o-', color='#6366f1', linewidth=2.5, label='Hierarchical Tree Topology')
    plt.plot(ns, s_flat, 's--', color='#ec4899', linewidth=2.0, label='Flat All-to-All Broadcast Topology')
    
    # Amdahl theoretical bound
    ideal_amdahl = [1.0 / (0.15 + (1.0 - 0.15) / n) for n in ns]
    plt.plot(ns, ideal_amdahl, 'k:', alpha=0.5, label="Amdahl Ceiling (s=0.15, Zero Overhead)")

    plt.axvline(x=hier_report.n_knee, color='#10b981', linestyle='--', alpha=0.8, label=f"N_knee = {hier_report.n_knee}")
    plt.axvline(x=hier_report.n_peak, color='#f59e0b', linestyle='--', alpha=0.8, label=f"N* (Peak) = {hier_report.n_peak}")

    plt.title("Multi-Agent Scaling Laws: Speedup S(N) vs Team Size N", fontsize=14, fontweight='bold', pad=12)
    plt.xlabel("Team Size (Number of Coordinated Agents N)", fontsize=11)
    plt.ylabel("Effective Speedup Relative to Single Agent", fontsize=11)
    plt.grid(True, alpha=0.25)
    plt.legend(frameon=True, facecolor='#f8fafc', edgecolor='#cbd5e1')
    plt.tight_layout()

    plot_path = os.path.join(RESULTS_DIR, "scaling_curves.png")
    plt.savefig(plot_path)
    plt.close()
    print(f"[✓] Saved scaling plot to {plot_path}")

    # Render Markdown Report
    report_md = f"""# Empirical Scaling Laws for Multi-Agent Systems on Hard Problems

## Executive Summary
This empirical study measures how collaborative performance scales as team size $N$ increases from 1 to 64 agents on a complex formal synthesis task. We identify the exact points where the scaling curve bends and breaks down, and provide a mathematical and physical decomposition of the underlying bottlenecks.

---

## 1. Key Inflection Points

| Metric | Hierarchical Topology | Flat Broadcast Topology | Physical Significance |
| :--- | :--- | :--- | :--- |
| **Knee of Curve ($N_{{knee}}$)** | **{hier_report.n_knee} agents** | **{flat_report.n_knee} agents** | Point of maximum marginal efficiency. Beyond this, adding agents yields diminishing returns. |
| **Peak Throughput ($N^*$)** | **{hier_report.n_peak} agents** | **{flat_report.n_peak} agents** | Optimal team size for minimum wall-clock latency ($S_{{max}} = {hier_report.max_observed_speedup:.2f}\\times$). |
| **Collapse Threshold** | **{hier_report.n_collapse} agents** | **{flat_report.n_collapse} agents** | Beyond this size, coordination tax and error cascades cause speedup to drop below single-agent baseline. |

---

## 2. Why the Curve Bends: Causal Attribution

The performance scaling curve exhibits three distinct thermodynamic regimes:
1. **Linear High-Yield Regime ($N \\le {hier_report.n_knee}$)**: Parallelizable subtasks are eagerly solved with minimal synchronization drag.
2. **Diminishing Returns Regime (${hier_report.n_knee} < N \\le {hier_report.n_peak}$)**: Amdahl's serial barrier (s=0.15) imposes an asymptotic limit of $1/s = 6.67\\times$, while message verification volume creates cognitive drag.
3. **Coordination Collapse Regime ($N > {hier_report.n_peak}$)**: Communication chatter and cascading unverified assertions dominate. In flat broadcast networks, $O(N^2)$ message saturation causes collapse at $N={flat_report.n_collapse}$.

### Penalty Decomposition at $N=16$:
- **Amdahl Serial Bottleneck**: {hier_report.serial_bottleneck_pct}% of performance loss.
- **Inter-Agent Communication Overhead**: {hier_report.communication_overhead_pct}% of performance loss.
- **Cascading Hallucination / Byzantine Rework**: {hier_report.hallucination_cascade_pct}% of performance loss.
- **Concurrency / OCC Conflicts**: {hier_report.concurrency_conflict_pct}% of performance loss.

---

## 3. Engineering Recommendations for Launch
1. **Topology Enforcement**: Never deploy teams larger than $N=4$ in flat broadcast mode. Use hierarchical tree structures with branching factor $b=4$.
2. **Team Sizing Guideline**:
   - For cost-optimal operation: Deploy **$N={int(hier_report.n_knee)}$ agents**.
   - For fastest wall-clock solution: Deploy **$N={int(hier_report.n_peak)}$ agents**.
   - Avoid teams exceeding $N=16$ unless subproblems are embarrassingly parallel.
"""
    rep_path = os.path.join(RESULTS_DIR, "scaling_laws_report.md")
    with open(rep_path, "w") as f:
        f.write(report_md)
    print(f"[✓] Saved comprehensive report to {rep_path}\n")


if __name__ == "__main__":
    run()
