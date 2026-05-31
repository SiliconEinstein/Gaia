#!/usr/bin/env node
import fs from "node:fs/promises";

function usage() {
  console.log("Usage: check_dot_cycles.mjs graph.dot");
}

const path = process.argv[2];
if (!path || process.argv.includes("--help")) {
  usage();
  process.exit(path ? 0 : 1);
}

const dot = await fs.readFile(path, "utf8");
const edges = [...dot.matchAll(/"([^"]+)"\s*->\s*"([^"]+)"/g)].map((match) => [match[1], match[2]]);
const adj = new Map();
for (const [from, to] of edges) {
  if (!adj.has(from)) adj.set(from, []);
  if (!adj.has(to)) adj.set(to, []);
  adj.get(from).push(to);
}

const seen = new Set();
const stack = new Set();
const cycles = [];

function dfs(node, pathStack) {
  seen.add(node);
  stack.add(node);
  pathStack.push(node);
  for (const next of adj.get(node) || []) {
    if (!seen.has(next)) {
      dfs(next, pathStack);
    } else if (stack.has(next)) {
      cycles.push([...pathStack.slice(pathStack.indexOf(next)), next]);
    }
  }
  stack.delete(node);
  pathStack.pop();
}

for (const node of adj.keys()) {
  if (!seen.has(node)) dfs(node, []);
}

console.log(JSON.stringify({ nodes: adj.size, edges: edges.length, cycles }, null, 2));
process.exit(cycles.length ? 2 : 0);
