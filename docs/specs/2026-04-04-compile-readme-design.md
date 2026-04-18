# Design: `gaia compile --readme`

**Status:** Target design
**Date:** 2026-04-04

> **Note (2026-04-18):** References to `.gaia/reviews/*/` paths and review sidecars in this spec are outdated. Since gaia-lang 0.4.2, priors are assigned via `priors.py`; beliefs output to `.gaia/beliefs.json`. See `docs/foundations/gaia-lang/package.md`.

## Goal

`gaia compile --readme` generates a `README.md` at the package root that serves as the GitHub landing page for a Gaia knowledge package. The README presents the knowledge graph as a navigable, narrative document with a Mermaid diagram, full node content, reasoning chains, and optional inference results.

## Trigger

```bash
gaia compile [path] --readme
```

Compiles the package as usual (`.gaia/ir.json`, `.gaia/ir_hash`), then generates `README.md` at the package root.

## Output

`{package_root}/README.md`

## Data Sources

| Data | Source | Required |
|------|--------|----------|
| Package metadata | `pyproject.toml` (`[project]`, `[tool.gaia]`) | Yes |
| Knowledge graph | `.gaia/ir.json` (just compiled) | Yes |
| Priors | `.gaia/reviews/*/parameterization.json` | No |
| Beliefs | `.gaia/reviews/*/beliefs.json` | No |

If multiple reviews exist, use the most recently modified one.

## README Structure

```
# {Package Name}
{description}

## Knowledge Graph          ← Mermaid diagram
## Knowledge Nodes          ← Full content, narrative order
  ### Settings
  ### Claims
  ### Questions
## Inference Results        ← Only if beliefs exist
```

## Section 1: Knowledge Graph (Mermaid)

A `graph TD` Mermaid diagram showing all nodes and edges.

**Nodes:**
- Settings: grey, rectangle, label only
- Independent premise claims: blue, label + belief (if available)
- Derived conclusion claims: green, label + belief
- Questions: orange, label only
- Helper claims (`__` prefix): hidden (omit from diagram)

**Edges:**
- Strategy: solid arrow from each premise to conclusion, labeled with strategy type
- Operator: dotted bidirectional edge, labeled with operator type (contradiction, equivalence, etc.)
- Background: omitted from diagram (not part of the reasoning graph)

**Node labels:** Use the Knowledge `label` field (snake_case). Display belief value if available: `"label (0.85)"`.

## Section 2: Knowledge Nodes (Narrative Order)

### Narrative Ordering Algorithm

The nodes are ordered by topological sort of the reasoning DAG to create a coherent reading experience: premises appear before conclusions.

```
1. Compute topological layers:
   - Layer 0: all nodes with no incoming strategy/operator edges (settings, independent premises, questions)
   - Layer N: nodes whose all premise dependencies are in layers < N
   
2. Within layer 0, order by type: Settings first, then Claims, then Questions

3. Within each layer, group by connected component:
   - Nodes that share a common strategy/conclusion are grouped together
   - This keeps related premises adjacent (e.g., all VDiagMC premises together)

4. Questions go at the end (after all claims), regardless of layer
```

### Node Rendering

Each node is an H4 section with anchor for cross-referencing.

**Independent premise (no incoming strategy):**

```markdown
#### adiabatic_approx

在传统金属中，Debye 频率 $\omega_D$ 远小于 Fermi 能量 $E_F$...

**Prior:** 0.95 · **Belief:** 0.88
```

**Derived conclusion (has incoming strategy):**

```markdown
#### downfolded_bse

消去高能模式后，完整的 BSE 可严格降标为仅依赖频率的 Fermi 面方程...

**Derived via:** deduction([pair_propagator_decomposition](#pair_propagator_decomposition), [cross_term_suppressed](#cross_term_suppressed), [adiabatic_approx](#adiabatic_approx))
**Belief:** 0.75
**Reason:** 配对传播子的相干/非相干分解提供了降标的数学基础，交叉项被压制保证了两个通道可独立处理...
```

**Setting:**

```markdown
#### bcs_framework

BCS 理论将传统超导解释为声子交换介导的电子 Cooper 配对...
```

**Rules:**
- All premise labels in "Derived via" are hyperlinks: `[label](#label)`
- Prior/Belief lines only appear when data exists
- Reason only appears for derived conclusions (from strategy metadata or steps)
- Helper claims (`__` prefix labels) are omitted entirely
- Content is rendered in full, no truncation

## Section 3: Inference Results (Optional)

Only generated when `.gaia/reviews/*/beliefs.json` exists.

```markdown
## Inference Results

**Review:** self_review
**BP converged:** True (35 iterations)

| Label | Prior | Belief | Role |
|-------|-------|--------|------|
| adiabatic_approx | 0.95 | 0.88 | independent premise |
| downfolded_bse | — | 0.75 | derived conclusion |
| ... | ... | ... | ... |
```

Sorted by belief ascending (most uncertain conclusions first — draws attention to where the argument is weakest).

## Implementation Notes

### Where the code lives

New module: `gaia/cli/commands/_readme.py` (private, called from compile command).

Single public function:

```python
def generate_readme(
    ir: dict,
    pkg_metadata: dict,       # from pyproject.toml
    pkg_path: Path,
    beliefs_path: Path | None,
    parameterization_path: Path | None,
) -> str:
    """Generate README.md content from compiled IR and optional inference results."""
```

### Integration with compile command

In `gaia/cli/commands/compile.py`, add `--readme` flag:

```python
@app.command()
def compile(
    path: ...
    readme: bool = typer.Option(False, "--readme", help="Generate README.md"),
):
    ...  # existing compile logic
    if readme:
        from gaia.cli.commands._readme import generate_readme
        content = generate_readme(ir, pkg_metadata, pkg_path, beliefs_path, param_path)
        (pkg_path / "README.md").write_text(content)
```

### Mermaid generation

Iterate over strategies and operators in the IR to build edges. Skip helper claims (labels starting with `__`). Use Mermaid `classDef` for node styling.

### Topological sort

Use Kahn's algorithm on the strategy premise→conclusion DAG. Nodes with no incoming edges form layer 0. Remove them, repeat for layer 1, etc. Within each layer, sort by connected component (BFS from shared conclusions).

### Belief/Prior lookup

- Beliefs: parse `beliefs.json`, build `{knowledge_id: belief}` map
- Priors: parse `parameterization.json`, extract node priors from the review sidecar's `PriorRecord` entries
- Both keyed by knowledge QID, matched against IR knowledge IDs

## Not in scope

- Mermaid click-to-anchor (GitHub doesn't support `click` directives)
- Multiple review comparison
- Custom templates / theming
- Internationalization
