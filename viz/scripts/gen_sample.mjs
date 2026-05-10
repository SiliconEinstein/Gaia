#!/usr/bin/env node
// Synthesizes a plausible sample graph fixture for dev mode.
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const out = resolve(__dirname, '..', 'public', 'sample-graph.json');

const N_KNOWLEDGE = 80;
const N_STRATEGIES = 18;
const N_OPERATORS = 6;
const MODULES = ['core', 'metaphysics', 'epistemics', 'ethics'];
const TYPES = ['claim', 'question', 'setting', 'background'];
const STRAT_TYPES = ['deduction', 'abduction', 'induction'];
const OPER_TYPES = ['contradiction', 'equivalence', 'composition'];

function rand(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function maybeBelief() {
  // ~75% have a belief
  if (Math.random() < 0.25) return null;
  // bias slightly toward extremes for visibility
  const r = Math.random();
  if (r < 0.3) return Math.random() * 0.3;
  if (r > 0.7) return 0.7 + Math.random() * 0.3;
  return 0.3 + Math.random() * 0.4;
}

const nodes = [];
const edges = [];

for (let i = 0; i < N_KNOWLEDGE; i++) {
  const t = rand(TYPES);
  nodes.push({
    id: `k_${i}`,
    label: `${t}_${i}`,
    title: `${t} ${i}`,
    type: t,
    module: rand(MODULES),
    content: `Sample ${t} content for node ${i}. This represents a knowledge node in the gaia reasoning graph.`,
    prior: Math.random() < 0.5 ? Math.random() : null,
    belief: maybeBelief(),
    exported: Math.random() < 0.1,
    metadata: {},
  });
}

for (let i = 0; i < N_STRATEGIES; i++) {
  const concIdx = Math.floor(Math.random() * N_KNOWLEDGE);
  const conc = `k_${concIdx}`;
  const sid = `strat_${i}`;
  const concMod = nodes[concIdx].module;
  nodes.push({
    id: sid,
    type: 'strategy',
    strategy_type: rand(STRAT_TYPES),
    module: concMod,
    reason: `derived via ${rand(STRAT_TYPES)}`,
  });
  // 2-3 premises
  const np = 2 + Math.floor(Math.random() * 2);
  const used = new Set([concIdx]);
  for (let j = 0; j < np; j++) {
    let p;
    do { p = Math.floor(Math.random() * N_KNOWLEDGE); } while (used.has(p));
    used.add(p);
    edges.push({ source: `k_${p}`, target: sid, role: 'premise' });
  }
  // optional background
  if (Math.random() < 0.4) {
    let b;
    do { b = Math.floor(Math.random() * N_KNOWLEDGE); } while (used.has(b));
    edges.push({ source: `k_${b}`, target: sid, role: 'background' });
  }
  edges.push({ source: sid, target: conc, role: 'conclusion' });
}

for (let i = 0; i < N_OPERATORS; i++) {
  const concIdx = Math.floor(Math.random() * N_KNOWLEDGE);
  const conc = `k_${concIdx}`;
  const oid = `oper_${i}`;
  nodes.push({
    id: oid,
    type: 'operator',
    operator_type: rand(OPER_TYPES),
    module: nodes[concIdx].module,
  });
  const nv = 1 + Math.floor(Math.random() * 2);
  const used = new Set([concIdx]);
  for (let j = 0; j < nv; j++) {
    let v;
    do { v = Math.floor(Math.random() * N_KNOWLEDGE); } while (used.has(v));
    used.add(v);
    edges.push({ source: `k_${v}`, target: oid, role: 'variable' });
  }
  edges.push({ source: oid, target: conc, role: 'conclusion' });
}

const moduleMap = {};
for (const m of MODULES) moduleMap[m] = { nodes: 0, strats: 0 };
for (const n of nodes) {
  if (!n.module) continue;
  if (n.type === 'strategy') moduleMap[n.module].strats++;
  else if (n.type !== 'operator') moduleMap[n.module].nodes++;
}

const data = {
  modules: MODULES.map((m, i) => ({
    id: m,
    order: i,
    node_count: moduleMap[m].nodes,
    strategy_count: moduleMap[m].strats,
  })),
  cross_module_edges: [],
  nodes,
  edges,
};

writeFileSync(out, JSON.stringify(data, null, 2));
console.log(`wrote ${out} — ${nodes.length} nodes, ${edges.length} edges`);
