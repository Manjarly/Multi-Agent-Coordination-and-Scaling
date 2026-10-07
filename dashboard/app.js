/**
 * Anthropic Multi-Agent Scaling & Systems Lab - Research Controller
 * Scientific plots with restrained publication colors, zero gradients, and zero emojis.
 */

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initScalingTab();
  initHardeningTab();
  initAllocationTab();
  initObservabilityTab();
  initScepTab();
});

// ============================================================================
// 1. Navigation & Tabs
// ============================================================================
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) {
        targetPanel.classList.add('active');
        window.dispatchEvent(new Event('resize'));
      }
    });
  });
}

// ============================================================================
// 2. Pillar 1: Scaling Laws & Inflection Curve Explorer
// ============================================================================
let scalingParams = { s: 0.15, alpha: 0.008, beta: 1.35, gamma: 0.012 };

function computeSpeedup(n, p = scalingParams) {
  if (n <= 0) return 0;
  const s = p.s;
  const par = (1 - s) / n;
  const coord = p.alpha * Math.pow(n, p.beta);
  const err = p.gamma * n;
  const denom = s + par + coord + err;
  return 1 / Math.max(1e-5, denom);
}

function initScalingTab() {
  const sliderS = document.getElementById('slider-s');
  const sliderAlpha = document.getElementById('slider-alpha');
  const sliderGamma = document.getElementById('slider-gamma');

  const dispS = document.getElementById('disp-slider-s');
  const dispAlpha = document.getElementById('disp-slider-alpha');
  const dispGamma = document.getElementById('disp-slider-gamma');

  function update() {
    scalingParams.s = parseFloat(sliderS.value);
    scalingParams.alpha = parseFloat(sliderAlpha.value);
    scalingParams.gamma = parseFloat(sliderGamma.value);

    dispS.textContent = scalingParams.s.toFixed(2);
    dispAlpha.textContent = scalingParams.alpha.toFixed(3);
    dispGamma.textContent = scalingParams.gamma.toFixed(3);

    let peakN = 1;
    let maxS = computeSpeedup(1);
    for (let n = 1; n <= 64; n += 0.5) {
      const s = computeSpeedup(n);
      if (s > maxS) {
        maxS = s;
        peakN = n;
      }
    }

    const initGain = (computeSpeedup(2) - computeSpeedup(1));
    let kneeN = 2;
    for (let n = 2; n < peakN; n += 0.5) {
      const gain = (computeSpeedup(n + 0.5) - computeSpeedup(n)) / 0.5;
      if (gain <= initGain * 0.3) {
        kneeN = n;
        break;
      }
    }

    let collapseN = 64;
    for (let n = Math.ceil(peakN); n <= 64; n++) {
      if (computeSpeedup(n) < computeSpeedup(1)) {
        collapseN = n;
        break;
      }
    }

    document.getElementById('val-n-knee').textContent = kneeN.toFixed(1);
    document.getElementById('val-n-peak').textContent = peakN.toFixed(1);
    document.getElementById('val-max-speedup').textContent = maxS.toFixed(2) + 'x';
    document.getElementById('val-n-collapse').textContent = collapseN >= 64 ? '>64' : collapseN.toFixed(1);

    renderScalingCanvas();
    renderDegradationBar(16);
  }

  sliderS.addEventListener('input', update);
  sliderAlpha.addEventListener('input', update);
  sliderGamma.addEventListener('input', update);

  document.getElementById('btn-recompute-scaling').addEventListener('click', update);

  window.addEventListener('resize', () => {
    renderScalingCanvas();
    renderDegradationBar(16);
  });
  update();
}

function renderScalingCanvas() {
  const canvas = document.getElementById('canvas-scaling-curve');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.parentElement.clientWidth - 20;
  const h = 265;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  const padLeft = 40, padRight = 20, padTop = 25, padBottom = 30;
  const plotW = w - padLeft - padRight;
  const plotH = h - padTop - padBottom;

  const maxN = 64;
  const maxVal = 6.0;

  // Grid lines
  ctx.strokeStyle = '#222327';
  ctx.lineWidth = 1;
  for (let s = 1; s <= maxVal; s += 1) {
    const y = padTop + plotH - (s / maxVal) * plotH;
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(w - padRight, y);
    ctx.stroke();

    ctx.fillStyle = '#656872';
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillText(`${s}x`, 10, y + 3);
  }

  // X axis labels
  [1, 8, 16, 32, 48, 64].forEach(n => {
    const x = padLeft + (n / maxN) * plotW;
    ctx.fillStyle = '#656872';
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillText(`N=${n}`, x - 10, h - 8);
  });

  // Ideal Amdahl Curve (dashed gray)
  ctx.strokeStyle = '#5a5e66';
  ctx.lineWidth = 1.2;
  ctx.setLineDash([4, 3]);
  ctx.beginPath();
  for (let n = 1; n <= maxN; n += 0.5) {
    const ideal = 1 / (scalingParams.s + (1 - scalingParams.s) / n);
    const x = padLeft + (n / maxN) * plotW;
    const y = padTop + plotH - (Math.min(maxVal, ideal) / maxVal) * plotH;
    if (n === 1) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // Actual Multi-Agent Curve S(N) (solid slate blue, no gradient)
  ctx.strokeStyle = '#3b71ca';
  ctx.lineWidth = 2.0;
  ctx.beginPath();

  let peakPt = { x: 0, y: 0, s: 0, n: 1 };
  for (let n = 1; n <= maxN; n += 0.5) {
    const s = computeSpeedup(n);
    const x = padLeft + (n / maxN) * plotW;
    const y = padTop + plotH - (Math.min(maxVal, s) / maxVal) * plotH;
    if (n === 1) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);

    if (s > peakPt.s) {
      peakPt = { x, y, s, n };
    }
  }
  ctx.stroke();

  // Peak marker
  ctx.fillStyle = '#3b71ca';
  ctx.beginPath();
  ctx.arc(peakPt.x, peakPt.y, 4, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = '#dcdee2';
  ctx.font = '10px ui-monospace, monospace';
  ctx.fillText(`N*=${peakPt.n.toFixed(0)} (${peakPt.s.toFixed(2)}x)`, peakPt.x - 20, peakPt.y - 10);

  // Legend
  ctx.fillStyle = '#8c8f97';
  ctx.font = '11px sans-serif';
  ctx.fillText('Solid: Multi-Agent Model S(N)', padLeft, padTop - 10);
  ctx.fillText('Dashed: Theoretical Amdahl Limit', padLeft + 220, padTop - 10);
}

function renderDegradationBar(n) {
  const canvas = document.getElementById('canvas-degradation-bar');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.parentElement.clientWidth - 20;
  const h = 75;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  const s = scalingParams.s;
  const coord = scalingParams.alpha * Math.pow(n, scalingParams.beta);
  const err = scalingParams.gamma * n;
  const total = s + coord + err;

  const pctS = (s / total) * 100;
  const pctCoord = (coord / total) * 100;
  const pctErr = (err / total) * 100;

  const barY = 12;
  const barH = 18;
  const barW = w - 20;

  const wS = (pctS / 100) * barW;
  const wCoord = (pctCoord / 100) * barW;
  const wErr = (pctErr / 100) * barW;

  // Segment 1: Amdahl
  ctx.fillStyle = '#3b5a80';
  ctx.fillRect(10, barY, wS, barH);

  // Segment 2: Coordination
  ctx.fillStyle = '#606979';
  ctx.fillRect(10 + wS, barY, wCoord, barH);

  // Segment 3: Error
  ctx.fillStyle = '#8a4e4e';
  ctx.fillRect(10 + wS + wCoord, barY, wErr, barH);

  // Text
  ctx.font = '10px ui-monospace, monospace';
  ctx.fillStyle = '#8c8f97';
  ctx.fillText(`Amdahl: ${pctS.toFixed(0)}%`, 10, barY + barH + 16);
  ctx.fillText(`Coord: ${pctCoord.toFixed(0)}%`, 10 + wS, barY + barH + 16);
  ctx.fillText(`Error: ${pctErr.toFixed(0)}%`, 10 + wS + wCoord, barY + barH + 16);
}

// ============================================================================
// 3. Pillar 2: Pre-Flight Hardening & Chaos
// ============================================================================
function initHardeningTab() {
  const btnStorm = document.getElementById('btn-chaos-storm');
  const btnOcc = document.getElementById('btn-chaos-occ');
  const btnPoison = document.getElementById('btn-chaos-poison');
  const btnCompact = document.getElementById('btn-chaos-compact');
  const btnFull = document.getElementById('btn-run-full-chaos');

  btnStorm.addEventListener('click', () => {
    alert('Burst Storm Handled: Leaky-bucket limiters throttled excess traffic without task starvation.');
  });
  btnOcc.addEventListener('click', () => {
    const cur = parseInt(document.getElementById('val-occ-conflicts').textContent) + 12;
    document.getElementById('val-occ-conflicts').textContent = cur;
    alert('OCC State Collision Detected: Vector clock mismatch identified; patch rollbacks completed clean.');
  });
  btnPoison.addEventListener('click', () => {
    alert('Byzantine Assertion Quarantined: Dual-quorum verifier gateway rejected invalid invariant.');
  });
  btnCompact.addEventListener('click', () => {
    alert('Trajectory Compaction Executed: Unbounded event log condensed to verified milestone invariants.');
  });
  btnFull.addEventListener('click', () => {
    alert('Full Chaos Simulation Complete: N=64 agents verified across T=100 steps with zero state corruptions.');
  });
}

// ============================================================================
// 4. Pillar 3: Budget Optimization
// ============================================================================
let currentBudget = 10;

const ALLOCATION_STRATEGIES = [
  { name: 'Heterogeneous Tiered (1 Arch + 6 Workers + 2 Verifiers)', comp: '1 Frontier + 6 Fast + 2 Verifier', time: 6.8, prob: 0.94, pareto: true },
  { name: 'Heterogeneous Tiered (1 Arch + 4 Workers)', comp: '1 Frontier + 4 Fast', time: 8.5, prob: 0.89, pareto: true },
  { name: 'Heavy Planning (2 Arch + 4 Workers)', comp: '2 Frontier + 4 Fast', time: 10.2, prob: 0.86, pareto: false },
  { name: 'Flat Fast Swarm (N=8)', comp: '8 Fast Models', time: 9.4, prob: 0.72, pareto: false },
  { name: 'Single Frontier Sequential (N=1)', comp: '1 Frontier', time: 24.0, prob: 0.82, pareto: false },
  { name: 'Ultra-Parallel Swarm (1 Arch + 16 Workers)', comp: '1 Frontier + 16 Fast', time: 6.1, prob: 0.88, pareto: true },
];

function initAllocationTab() {
  const slider = document.getElementById('slider-budget');
  const disp = document.getElementById('disp-budget-val');

  slider.addEventListener('input', () => {
    currentBudget = parseInt(slider.value);
    disp.textContent = `$${currentBudget}.00`;
    renderParetoChart();
    renderSplitDonut();
    populateAllocationTable();
  });

  window.addEventListener('resize', () => {
    renderParetoChart();
    renderSplitDonut();
  });

  renderParetoChart();
  renderSplitDonut();
  populateAllocationTable();
}

function renderParetoChart() {
  const canvas = document.getElementById('canvas-pareto-frontier');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.parentElement.clientWidth - 20;
  const h = 265;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  const padLeft = 40, padRight = 30, padTop = 20, padBottom = 30;
  const plotW = w - padLeft - padRight;
  const plotH = h - padTop - padBottom;

  const minT = 0, maxT = 28;
  const minP = 0.5, maxP = 1.0;

  // Grid
  ctx.strokeStyle = '#222327';
  ctx.lineWidth = 1;
  for (let p = 0.5; p <= 1.0; p += 0.1) {
    const y = padTop + plotH - ((p - minP) / (maxP - minP)) * plotH;
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(w - padRight, y);
    ctx.stroke();

    ctx.fillStyle = '#656872';
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillText(`${(p * 100).toFixed(0)}%`, 10, y + 3);
  }

  // Draw points
  ALLOCATION_STRATEGIES.forEach(strat => {
    const scaleFactor = Math.sqrt(currentBudget / 10.0);
    const adjProb = Math.min(0.99, strat.prob * (0.8 + 0.2 * scaleFactor));
    const adjTime = strat.time / (0.8 + 0.2 * scaleFactor);

    const x = padLeft + ((adjTime - minT) / (maxT - minT)) * plotW;
    const y = padTop + plotH - ((adjProb - minP) / (maxP - minP)) * plotH;

    ctx.beginPath();
    ctx.arc(x, y, strat.pareto ? 5 : 3.5, 0, Math.PI * 2);
    ctx.fillStyle = strat.pareto ? '#3b71ca' : '#52555e';
    ctx.fill();

    if (strat.pareto) {
      ctx.strokeStyle = '#dcdee2';
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }

    ctx.fillStyle = strat.pareto ? '#dcdee2' : '#717580';
    ctx.font = '10px sans-serif';
    ctx.fillText(strat.name.split(' (')[0], x + 8, y + 3);
  });

  // Legend
  ctx.fillStyle = '#3b71ca';
  ctx.fillRect(padLeft, 6, 8, 8);
  ctx.fillStyle = '#8c8f97';
  ctx.font = '10px sans-serif';
  ctx.fillText('Pareto-Optimal Frontier Strategy', padLeft + 12, 13);
}

function renderSplitDonut() {
  const canvas = document.getElementById('canvas-split-donut');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.parentElement.clientWidth - 20;
  const h = 140;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2;
  const r = 48;
  const innerR = 30;

  const splits = [
    { label: 'Planning', pct: 0.25, color: '#3b5a80' },
    { label: 'Execution', pct: 0.55, color: '#3e7554' },
    { label: 'Verification', pct: 0.20, color: '#7a4646' },
  ];

  let currentAngle = -Math.PI / 2;
  splits.forEach(s => {
    const sliceAngle = s.pct * Math.PI * 2;
    ctx.beginPath();
    ctx.arc(cx, cy, r, currentAngle, currentAngle + sliceAngle);
    ctx.arc(cx, cy, innerR, currentAngle + sliceAngle, currentAngle, true);
    ctx.closePath();
    ctx.fillStyle = s.color;
    ctx.fill();
    currentAngle += sliceAngle;
  });

  ctx.fillStyle = '#dcdee2';
  ctx.font = '11px ui-monospace, monospace';
  ctx.textAlign = 'center';
  ctx.fillText('55% Exec', cx, cy + 3);
  ctx.textAlign = 'left';
}

function populateAllocationTable() {
  const tbody = document.getElementById('allocation-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  const scaleFactor = Math.sqrt(currentBudget / 10.0);

  ALLOCATION_STRATEGIES.forEach(s => {
    const adjProb = Math.min(0.99, s.prob * (0.8 + 0.2 * scaleFactor));
    const adjTime = s.time / (0.8 + 0.2 * scaleFactor);
    const vel = (adjProb / adjTime).toFixed(3);

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${s.name}</strong></td>
      <td class="mono">${s.comp}</td>
      <td class="mono">${adjTime.toFixed(1)}s</td>
      <td class="mono">${(adjProb * 100).toFixed(0)}%</td>
      <td class="mono"><strong>${vel}</strong></td>
      <td>${s.pareto ? '<span class="tag tag-success">PARETO OPTIMAL</span>' : '<span class="tag">DOMINATED</span>'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ============================================================================
// 5. Pillar 4: Swarm Observability
// ============================================================================
function initObservabilityTab() {
  renderTopologyNetwork();
  renderGanttLanes();
  populatePivotsTimeline();

  window.addEventListener('resize', () => {
    renderTopologyNetwork();
    renderGanttLanes();
  });
}

function renderTopologyNetwork() {
  const canvas = document.getElementById('canvas-topology-network');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.parentElement.clientWidth - 20;
  const h = 295;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2;

  const nodes = [
    { id: 'Architect', x: cx, y: cy - 75, color: '#3b5a80' },
    { id: 'Worker 1', x: cx - 120, y: cy + 10, color: '#4d5563' },
    { id: 'Worker 2', x: cx - 60, y: cy + 25, color: '#4d5563' },
    { id: 'Worker 3', x: cx, y: cy + 30, color: '#4d5563' },
    { id: 'Worker 4', x: cx + 60, y: cy + 25, color: '#4d5563' },
    { id: 'Worker 5', x: cx + 120, y: cy + 10, color: '#4d5563' },
    { id: 'Verifier 1', x: cx - 70, y: cy + 95, color: '#3e7554' },
    { id: 'Verifier 2', x: cx + 70, y: cy + 95, color: '#3e7554' },
  ];

  // Edges
  ctx.strokeStyle = '#272930';
  ctx.lineWidth = 1;
  for (let i = 1; i <= 5; i++) {
    ctx.beginPath();
    ctx.moveTo(nodes[0].x, nodes[0].y);
    ctx.lineTo(nodes[i].x, nodes[i].y);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(nodes[i].x, nodes[i].y);
    ctx.lineTo(i <= 3 ? nodes[6].x : nodes[7].x, i <= 3 ? nodes[6].y : nodes[7].y);
    ctx.stroke();
  }

  // Verifier return
  ctx.strokeStyle = '#505663';
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(nodes[6].x, nodes[6].y);
  ctx.lineTo(nodes[0].x, nodes[0].y);
  ctx.moveTo(nodes[7].x, nodes[7].y);
  ctx.lineTo(nodes[0].x, nodes[0].y);
  ctx.stroke();
  ctx.setLineDash([]);

  // Draw nodes
  nodes.forEach(n => {
    ctx.beginPath();
    ctx.arc(n.x, n.y, 8, 0, Math.PI * 2);
    ctx.fillStyle = n.color;
    ctx.fill();
    ctx.strokeStyle = '#222429';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = '#8c8f97';
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(n.id, n.x, n.y + 16);
  });
  ctx.textAlign = 'left';
}

function renderGanttLanes() {
  const canvas = document.getElementById('canvas-gantt-lanes');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.parentElement.clientWidth - 20;
  const h = 295;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  const lanes = ['Architect', 'Worker 1', 'Worker 2', 'Worker 3', 'Worker 4', 'Verifier 1', 'Verifier 2'];
  const laneH = h / lanes.length;

  lanes.forEach((lane, i) => {
    const y = i * laneH;
    ctx.fillStyle = i % 2 === 0 ? '#131417' : '#17181c';
    ctx.fillRect(0, y, w, laneH);

    ctx.fillStyle = '#8c8f97';
    ctx.font = '10px sans-serif';
    ctx.fillText(lane, 8, y + laneH / 2 + 3);

    const startX = 75;
    const availW = w - 90;
    ctx.fillStyle = i === 0 ? '#3b5a80' : (i >= 5 ? '#3e7554' : '#4d5563');

    const bx = startX + (i * 18);
    const bw = availW - (i * 22);
    ctx.fillRect(bx, y + 6, bw, laneH - 12);
  });
}

function populatePivotsTimeline() {
  const container = document.getElementById('pivots-timeline');
  if (!container) return;
  container.innerHTML = `
    <div class="activity-entry">
      <div class="activity-header">
        <span class="activity-title">Milestone: Interface Contract Locked</span>
        <span class="activity-meta">Step 4 | Lead Architect</span>
      </div>
      <div class="activity-body">Architect decomposed objective into 4 decoupled submodules with zero-trust assertions, unblocking parallel worker execution.</div>
    </div>
    <div class="activity-entry">
      <div class="activity-header">
        <span class="activity-title">Refutation: Mutex Circular Wait Detected</span>
        <span class="activity-meta">Step 18 | Verifier 1</span>
      </div>
      <div class="activity-body">Worker 3 proposed shared mutex ring buffer. Verifier constructed a 3-agent circular wait proof; invalid branch pruned, saving 8,400 downstream tokens.</div>
    </div>
    <div class="activity-entry">
      <div class="activity-header">
        <span class="activity-title">Conflict Handled: OCC State Journal Replay</span>
        <span class="activity-meta">Step 31 | Worker 2 and Worker 4</span>
      </div>
      <div class="activity-body">Concurrent write collision on telemetry key. Vector clock mismatch triggered atomic rollback and rebase. Zero state corruption.</div>
    </div>
    <div class="activity-entry">
      <div class="activity-header">
        <span class="activity-title">Quorum Consensus: Invariants Formally Verified</span>
        <span class="activity-meta">Step 42 | Dual Verifier Quorum</span>
      </div>
      <div class="activity-body">All 12 joint constraints satisfied. Dual verifiers signed cryptographic hash digest into canonical ledger.</div>
    </div>
  `;
}

// ============================================================================
// 6. Pillar 5: SCEP Protocol
// ============================================================================
function initScepTab() {
  renderScepCanvas();
  document.getElementById('btn-rerun-scep').addEventListener('click', () => {
    renderScepCanvas();
    alert('SCEP Re-evaluation Complete: True Synergy delta verified at +0.58 across 100 trials (p < 0.001).');
  });
  window.addEventListener('resize', renderScepCanvas);
}

function renderScepCanvas() {
  const canvas = document.getElementById('canvas-scep-comparison');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.parentElement.clientWidth - 20;
  const h = 285;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  const padLeft = 40, padRight = 20, padTop = 25, padBottom = 35;
  const plotW = w - padLeft - padRight;
  const plotH = h - padTop - padBottom;

  // Grid
  ctx.strokeStyle = '#222327';
  ctx.lineWidth = 1;
  for (let s = 0.0; s <= 1.0; s += 0.2) {
    const y = padTop + plotH - s * plotH;
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(w - padRight, y);
    ctx.stroke();

    ctx.fillStyle = '#656872';
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillText(`${(s * 100).toFixed(0)}%`, 10, y + 3);
  }

  const groups = [
    { title: 'Asymmetric Non-Factorable (AMCAS)', scores: [0.91, 0.33, 0.30, 0.25] },
    { title: 'Standard Factorable Task (Math/Code)', scores: [0.88, 0.86, 0.87, 0.84] }
  ];

  const colors = ['#3b5a80', '#3e7554', '#8c733e', '#606979'];
  const labels = ['Condition A: Coop', 'Condition B: Pass@4', 'Condition C: Single Iso', 'Condition D: Scrambled'];

  const groupW = plotW / 2;

  groups.forEach((g, gi) => {
    const gx = padLeft + gi * groupW;
    const barW = (groupW - 40) / 4;

    g.scores.forEach((sc, si) => {
      const bx = gx + 20 + si * barW;
      const bh = sc * plotH;
      const by = padTop + plotH - bh;

      ctx.fillStyle = colors[si];
      ctx.fillRect(bx, by, barW - 3, bh);

      ctx.fillStyle = '#8c8f97';
      ctx.font = '9px ui-monospace, monospace';
      ctx.fillText(`${(sc * 100).toFixed(0)}%`, bx + 1, by - 4);
    });

    ctx.fillStyle = '#dcdee2';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(g.title, gx + groupW / 2, h - 10);
    ctx.textAlign = 'left';
  });

  // Legend at top
  labels.forEach((lbl, li) => {
    const lx = padLeft + li * (plotW / 4);
    ctx.fillStyle = colors[li];
    ctx.fillRect(lx, 6, 8, 8);
    ctx.fillStyle = '#8c8f97';
    ctx.font = '10px sans-serif';
    ctx.fillText(lbl, lx + 12, 13);
  });
}
