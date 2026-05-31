# Gaia Inquiry Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `gaia inquiry context` as a read-only, focus-centered Markdown context packet plus JSON envelope with a Gaia IR slice.

**Architecture:** Keep the feature in the existing inquiry CLI surface. Enrich the existing inquiry tree edge model with the small amount of route metadata needed by context rendering, then add a focused `gaia.cli.commands._context` helper for trajectory selection, IR slicing, Markdown rendering, and JSON serialization. Wire the public Typer command in `gaia/cli/commands/inquiry.py`; do not run inference, save inquiry state, append tactic events, or create a new graph schema.

**Tech Stack:** Python 3.12, Typer, Pydantic-backed Gaia IR dicts, existing Gaia package compiler helpers, pytest with `CliRunner`, existing `uv run --project . python -m pytest tests/cli/test_inquiry_context.py -q` workflow.

---

## File Structure

- Modify `gaia/cli/commands/_inquiry.py`
  - Add optional metadata fields to `InquiryEdge` so context can reuse the current goal-tree traversal without reparsing strategies.
  - Preserve existing `render_inquiry` output.
- Create `gaia/cli/commands/_context.py`
  - Owns context packet dataclasses, trajectory enumeration, structural uncertainty scoring, IR slice construction, Markdown rendering, and JSON dict output.
- Modify `gaia/cli/commands/inquiry.py`
  - Add the public `gaia inquiry context` command.
  - Keep it read-only: no `save_state` and no `append_tactic_event`.
- Create `tests/cli/test_inquiry_context.py`
  - Covers CLI Markdown, JSON, trajectory selectors, focus defaults, and no state mutation.
- Modify `docs/reference/cli/inquiry.md`
  - Document the new command and its read-only default Markdown behavior.
- Modify `docs/for-users/cli-commands.md`
  - Add the command to the user-facing CLI command list.

---

### Task 1: Add Failing CLI Tests For Context Output

**Files:**
- Create: `tests/cli/test_inquiry_context.py`

- [ ] **Step 1: Write the failing test module**

Create `tests/cli/test_inquiry_context.py` with:

```python
"""CLI tests for gaia inquiry context."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _write_context_package(pkg_dir) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "context-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "context_demo"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / "context_demo"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim, derive, note\n\n"
        'galileo_setting = note("Galilean free-fall setup used as background context.")\n\n'
        'coupled_body = claim("The coupled heavy-light body argument makes proportional-speed scaling internally unstable.")\n'
        'coupled_body.label = "coupled_body"\n\n'
        'obs_fall = claim("Observed falling bodies do not separate enough to support proportional-speed scaling.")\n'
        'obs_fall.label = "obs_fall"\n\n'
        'reject_prop_speed = claim("The proportional-speed law for falling bodies is not a reliable account of free fall.")\n'
        'reject_prop_speed.label = "reject_prop_speed"\n\n'
        "speed_refutation = derive(\n"
        "    reject_prop_speed,\n"
        "    given=(coupled_body,),\n"
        '    rationale="Observation and internal argument point against proportional-speed scaling.",\n'
        '    label="reject_prop_speed_route",\n'
        ")\n\n"
        "observation_refutation = derive(\n"
        "    reject_prop_speed,\n"
        "    given=(obs_fall,),\n"
        '    rationale="",\n'
        '    label="observation_route",\n'
        ")\n\n"
        'pendulum_timing = claim("Pendulum timing suggests short arcs are approximately isochronous.")\n'
        'pendulum_timing.label = "pendulum_timing"\n\n'
        'acceleration_inquiry = claim("Early Galilean reasoning favors acceleration-based inquiry over proportional-speed law.")\n'
        'acceleration_inquiry.label = "acceleration_inquiry"\n\n'
        "acceleration_case = derive(\n"
        "    acceleration_inquiry,\n"
        "    given=(reject_prop_speed, pendulum_timing),\n"
        "    background=[galileo_setting],\n"
        '    rationale="The refutation of proportional-speed scaling and pendulum regularity motivate a different inquiry target.",\n'
        '    label="acceleration_route",\n'
        ")\n\n"
        '__all__ = ["acceleration_inquiry"]\n',
        encoding="utf-8",
    )


def test_context_markdown_uses_focus_why_and_references(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    result = runner.invoke(
        app,
        ["inquiry", "context", str(pkg), "--focus", "acceleration_inquiry"],
    )

    assert result.exit_code == 0, result.output
    assert "## Focus" in result.output
    assert "### `acceleration_inquiry`" in result.output
    assert "Early Galilean reasoning favors acceleration-based inquiry" in result.output
    assert "## Why This Claim" in result.output
    assert "### Why `acceleration_inquiry`?" in result.output
    assert "**Because**" in result.output
    assert "The refutation of proportional-speed scaling and pendulum regularity" in result.output
    assert "**Given**" in result.output
    assert "`reject_prop_speed`:" in result.output
    assert "`pendulum_timing`:" in result.output
    assert "**Background**" in result.output
    assert "`galileo_setting`" in result.output
    assert "## References" in result.output
    assert "### `reject_prop_speed`" in result.output
    assert "The proportional-speed law for falling bodies is not a reliable account of free fall." in result.output
    assert "### `galileo_setting`" in result.output
    assert "Galilean free-fall setup used as background context." in result.output
    assert "C1" not in result.output
    assert "B1" not in result.output
    assert "belief" not in result.output.lower()


def test_context_json_is_envelope_with_ir_slice(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    result = runner.invoke(
        app,
        ["inquiry", "context", str(pkg), "--focus", "acceleration_inquiry", "--json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["context_schema_version"] == 1
    assert data["focus"]["label"] == "acceleration_inquiry"
    assert data["selection"] == {"trajectory": "most_uncertain", "order": "backward"}
    assert data["why_route"]
    assert data["why_route"][0]["edge_kind"] == "strategy"
    assert data["why_route"][0]["label"] == "acceleration_route"
    assert "ir" in data
    expected_ir_keys = {
        "namespace",
        "package_name",
        "scope",
        "knowledges",
        "strategies",
        "operators",
        "composes",
        "formula_graphs",
    }
    assert expected_ir_keys.issubset(data["ir"])
    assert "ir_hash" not in data["ir"]
    rendered_labels = {item.get("label") for item in data["ir"]["knowledges"]}
    assert {"acceleration_inquiry", "reject_prop_speed", "pendulum_timing", "galileo_setting"}.issubset(rendered_labels)
    assert "belief_report" not in data
    assert "beliefs" not in json.dumps(data)


def test_context_uses_current_focus_without_mutating_state(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    focus = runner.invoke(app, ["inquiry", "focus", "acceleration_inquiry", "--path", str(pkg)])
    assert focus.exit_code == 0, focus.output
    state_path = pkg / ".gaia" / "inquiry" / "state.json"
    before = state_path.read_text(encoding="utf-8")

    result = runner.invoke(app, ["inquiry", "context", str(pkg)])

    assert result.exit_code == 0, result.output
    assert "### `acceleration_inquiry`" in result.output
    after = state_path.read_text(encoding="utf-8")
    assert after == before


def test_context_shortest_and_most_uncertain_can_choose_different_routes(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    shortest = runner.invoke(
        app,
        [
            "inquiry",
            "context",
            str(pkg),
            "--focus",
            "acceleration_inquiry",
            "--trajectory",
            "shortest",
            "--json",
        ],
    )
    uncertain = runner.invoke(
        app,
        [
            "inquiry",
            "context",
            str(pkg),
            "--focus",
            "acceleration_inquiry",
            "--trajectory",
            "most_uncertain",
            "--json",
        ],
    )

    assert shortest.exit_code == 0, shortest.output
    assert uncertain.exit_code == 0, uncertain.output
    shortest_labels = [step["label"] for step in json.loads(shortest.output)["why_route"]]
    uncertain_labels = [step["label"] for step in json.loads(uncertain.output)["why_route"]]
    assert shortest_labels == ["acceleration_route"]
    assert uncertain_labels == ["acceleration_route", "observation_route"]


def test_context_missing_focus_exits_2(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    result = runner.invoke(app, ["inquiry", "context", str(pkg)])

    assert result.exit_code == 2
    assert "No inquiry focus set" in result.output
    assert "gaia inquiry focus <claim>" in result.output
```

- [ ] **Step 2: Run tests and verify the command is missing**

Run:

```bash
uv run --project . python -m pytest tests/cli/test_inquiry_context.py -q
```

Expected: FAIL. The first failures should report that Typer has no `context` command under `gaia inquiry`.

- [ ] **Step 3: Commit the failing tests**

Run:

```bash
git add tests/cli/test_inquiry_context.py
git commit -m "test: cover inquiry context cli"
```

---

### Task 2: Enrich Inquiry Tree Edges With Route Metadata

**Files:**
- Modify: `gaia/cli/commands/_inquiry.py`
- Test: `tests/cli/test_inquiry.py`

- [ ] **Step 1: Add metadata fields and rationale helper**

Modify `InquiryEdge` and add `_strategy_rationale` near the existing label helpers:

```python
@dataclass
class InquiryEdge:
    kind: str
    label: str
    target_id: str | None
    status: str | None
    inputs: list[InquiryNode] = field(default_factory=list)
    conclusion_id: str | None = None
    premise_ids: list[str] = field(default_factory=list)
    background_ids: list[str] = field(default_factory=list)
    rationale: str | None = None


def _strategy_rationale(strategy: dict[str, Any]) -> str | None:
    parts: list[str] = []
    for step in strategy.get("steps", []) or []:
        if isinstance(step, dict):
            reasoning = step.get("reasoning")
            if isinstance(reasoning, str) and reasoning.strip():
                parts.append(reasoning.strip())
    if parts:
        return "\n\n".join(parts)
    return None
```

- [ ] **Step 2: Populate strategy edge fields**

Change `_append_strategy_edges` so it computes premises/background/rationale before constructing `InquiryEdge`:

```python
    for strategy in indexes.strategies_by_conclusion.get(knowledge_id, []):
        strategy_id = strategy.get("strategy_id")
        premises = [premise for premise in strategy.get("premises", []) if premise]
        background = [ref for ref in strategy.get("background", []) if ref]
        node.incoming.append(
            InquiryEdge(
                kind="strategy",
                label=_action_label(strategy.get("metadata"), strategy_id or "strategy"),
                target_id=strategy_id,
                status=_review_status(review_manifest, strategy_id),
                inputs=[
                    _build_goal_node(premise, next_seen, indexes, review_manifest)
                    for premise in premises
                ],
                conclusion_id=knowledge_id,
                premise_ids=list(premises),
                background_ids=list(background),
                rationale=_strategy_rationale(strategy),
            )
        )
```

- [ ] **Step 3: Populate non-strategy edge identity fields without changing rendering**

For operator, compose, observe, and scaffold edge constructors, set `conclusion_id=knowledge_id`, `premise_ids` or direct input ids, and `background_ids=[]`. For candidate relations, leave `kind="candidate_relation"` and set direct input ids from the scaffold claims list. Keep `render_inquiry` unchanged.

- [ ] **Step 4: Run existing inquiry tests**

Run:

```bash
uv run --project . python -m pytest tests/cli/test_inquiry.py -q
```

Expected: PASS. Existing `build check --inquiry` text output must not change.

- [ ] **Step 5: Commit metadata enrichment**

Run:

```bash
git add gaia/cli/commands/_inquiry.py
git commit -m "refactor: carry inquiry route metadata"
```

---

### Task 3: Add Context Packet Builder And Trajectory Selection

**Files:**
- Create: `gaia/cli/commands/_context.py`
- Test: `tests/cli/test_inquiry_context.py`

- [ ] **Step 1: Create context data structures**

Create `gaia/cli/commands/_context.py` with these imports and dataclasses:

```python
"""Context packet builder for gaia inquiry context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from gaia.cli.commands._inquiry import InquiryEdge, InquiryNode, build_goal_trees
from gaia.engine.inquiry.focus import FocusBinding, resolve_focus_target
from gaia.engine.inquiry.review_manifest import load_or_generate_review_manifest
from gaia.engine.inquiry.state import InquiryState, load_state
from gaia.engine.packaging import (
    apply_package_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)

TrajectorySelector = Literal["most_uncertain", "shortest"]
RenderOrder = Literal["backward", "forward"]


@dataclass(frozen=True)
class ContextRouteStep:
    edge_kind: str
    target_id: str | None
    label: str
    status: str | None
    conclusion_id: str
    premise_ids: list[str]
    background_ids: list[str]
    rationale: str | None


@dataclass(frozen=True)
class ContextPacket:
    focus: FocusBinding
    trajectory: TrajectorySelector
    order: RenderOrder
    route: list[ContextRouteStep]
    ir: dict[str, Any]
    source_ir: dict[str, Any]
    state: InquiryState
```

- [ ] **Step 2: Add package compile and focus resolution**

Add:

```python
def build_context_packet(
    path: str | Path,
    *,
    focus_override: str | None,
    trajectory: TrajectorySelector,
    order: RenderOrder,
) -> ContextPacket:
    pkg_path = Path(path).resolve()
    state = load_state(pkg_path)
    focus_raw = focus_override if focus_override is not None else state.focus
    if focus_raw is None:
        raise ValueError("No inquiry focus set; pass --focus or run gaia inquiry focus <claim>.")

    ensure_package_env(pkg_path)
    loaded = load_gaia_package(str(pkg_path))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    graph = compiled.graph
    review_manifest = load_or_generate_review_manifest(loaded.pkg_path, compiled)

    focus = resolve_focus_target(focus_raw, graph)
    if focus.resolved_id is None or focus.kind != "claim":
        raise ValueError(f"Focus {focus_raw!r} did not resolve to a claim.")

    source_ir = compiled.to_json()
    trees = build_goal_trees(
        source_ir,
        review_manifest,
        exported_ids={focus.resolved_id},
        formalization_manifest=compiled.formalization_manifest,
    )
    if not trees:
        route: list[ContextRouteStep] = []
    else:
        routes = _enumerate_routes(trees[0])
        route = _select_route(routes, trajectory, state, source_ir)

    return ContextPacket(
        focus=focus,
        trajectory=trajectory,
        order=order,
        route=route,
        ir=_build_ir_slice(source_ir, route, focus.resolved_id),
        source_ir=source_ir,
        state=state,
    )
```

- [ ] **Step 3: Add route enumeration and selector**

Add:

```python
def _route_step(edge: InquiryEdge, conclusion_id: str) -> ContextRouteStep:
    return ContextRouteStep(
        edge_kind=edge.kind,
        target_id=edge.target_id,
        label=edge.label,
        status=edge.status,
        conclusion_id=edge.conclusion_id or conclusion_id,
        premise_ids=list(edge.premise_ids),
        background_ids=list(edge.background_ids),
        rationale=edge.rationale,
    )


def _enumerate_routes(node: InquiryNode) -> list[list[ContextRouteStep]]:
    if not node.incoming:
        return [[]]
    routes: list[list[ContextRouteStep]] = []
    for edge in node.incoming:
        step = _route_step(edge, node.knowledge_id)
        if not edge.inputs:
            routes.append([step])
            continue
        for child in edge.inputs:
            for child_route in _enumerate_routes(child):
                routes.append([step, *child_route])
    return routes


def _select_route(
    routes: list[list[ContextRouteStep]],
    trajectory: TrajectorySelector,
    state: InquiryState,
    ir: dict[str, Any],
) -> list[ContextRouteStep]:
    if not routes:
        return []
    if trajectory == "shortest":
        return min(routes, key=lambda route: (len(route), _route_key(route)))
    return sorted(
        routes,
        key=lambda route: (-_uncertainty_score(route, state, ir), len(route), _route_key(route)),
    )[0]


def _route_key(route: list[ContextRouteStep]) -> tuple[str, ...]:
    return tuple(step.target_id or step.label for step in route)
```

- [ ] **Step 4: Add structural uncertainty score**

Add:

```python
def _known_knowledge_ids(ir: dict[str, Any]) -> set[str]:
    return {item["id"] for item in ir.get("knowledges", []) if item.get("id")}


def _uncertainty_score(
    route: list[ContextRouteStep],
    state: InquiryState,
    ir: dict[str, Any],
) -> int:
    known = _known_knowledge_ids(ir)
    obligation_targets = {item.target_qid for item in state.synthetic_obligations}
    rejected_targets = {item.target_strategy for item in state.synthetic_rejections}
    score = 0
    for step in route:
        if step.target_id in rejected_targets:
            score += 6
        if step.target_id in obligation_targets or step.conclusion_id in obligation_targets:
            score += 4
        if step.status == "rejected":
            score += 6
        elif step.status == "needs_inputs":
            score += 5
        elif step.status == "unreviewed":
            score += 2
        if not step.rationale:
            score += 2
        for ref in [*step.premise_ids, *step.background_ids, step.conclusion_id]:
            if ref and ref not in known:
                score += 5
    if route:
        last_premises = route[-1].premise_ids
        if last_premises and any(ref in known for ref in last_premises):
            score += 1
    return score
```

This first score intentionally uses only structural information. It does not read `.gaia/beliefs.json` and does not call inference.

- [ ] **Step 5: Add IR slice builder**

Add:

```python
def _build_ir_slice(
    ir: dict[str, Any],
    route: list[ContextRouteStep],
    focus_id: str,
) -> dict[str, Any]:
    knowledge_ids = {focus_id}
    strategy_ids: set[str] = set()
    for step in route:
        knowledge_ids.add(step.conclusion_id)
        knowledge_ids.update(step.premise_ids)
        knowledge_ids.update(step.background_ids)
        if step.edge_kind == "strategy" and step.target_id:
            strategy_ids.add(step.target_id)

    knowledges = [
        item
        for item in ir.get("knowledges", [])
        if item.get("id") in knowledge_ids
    ]
    strategies = [
        item
        for item in ir.get("strategies", [])
        if item.get("strategy_id") in strategy_ids
    ]

    return {
        "namespace": ir.get("namespace"),
        "package_name": ir.get("package_name"),
        "scope": ir.get("scope", "local"),
        "knowledges": knowledges,
        "strategies": strategies,
        "operators": [],
        "composes": [],
        "formula_graphs": [],
    }
```

- [ ] **Step 6: Run context tests and verify renderers are still missing**

Run:

```bash
uv run --project . python -m pytest tests/cli/test_inquiry_context.py -q
```

Expected: FAIL because `_context.py` has no Markdown/JSON renderer and the CLI command is not wired yet.

- [ ] **Step 7: Commit context builder**

Run:

```bash
git add gaia/cli/commands/_context.py
git commit -m "feat: build inquiry context packet"
```

---

### Task 4: Add Markdown And JSON Renderers

**Files:**
- Modify: `gaia/cli/commands/_context.py`
- Test: `tests/cli/test_inquiry_context.py`

- [ ] **Step 1: Add lookup and preview helpers**

Append to `_context.py`:

```python
def _knowledge_by_id(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in ir.get("knowledges", []) if item.get("id")}


def _display_label(knowledge: dict[str, Any] | None, qid: str) -> str:
    if knowledge is not None and knowledge.get("label"):
        return str(knowledge["label"])
    tail = qid.rsplit("::", 1)[-1]
    return tail or qid


def _content(knowledge: dict[str, Any] | None) -> str:
    if knowledge is None:
        return ""
    return str(knowledge.get("content") or "")


def _preview(text: str, limit: int = 96) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _ordered_steps(packet: ContextPacket) -> list[ContextRouteStep]:
    if packet.order == "forward":
        return list(reversed(packet.route))
    return list(packet.route)
```

- [ ] **Step 2: Add Markdown renderer**

Append:

```python
def render_context_markdown(packet: ContextPacket) -> str:
    k_by_id = _knowledge_by_id(packet.ir)
    focus_id = packet.focus.resolved_id or ""
    focus_k = k_by_id.get(focus_id)
    focus_label = packet.focus.resolved_label or _display_label(focus_k, focus_id)
    lines: list[str] = [
        "## Focus",
        "",
        f"### `{focus_label}`",
        "",
        _content(focus_k),
        "",
        "## Why This Claim",
        "",
    ]

    references: list[str] = []
    seen_refs: set[str] = set()

    if not packet.route:
        lines.extend(["No supporting trajectory was found.", ""])
    else:
        for step in _ordered_steps(packet):
            conclusion = k_by_id.get(step.conclusion_id)
            conclusion_label = _display_label(conclusion, step.conclusion_id)
            lines.extend(
                [
                    f"### Why `{conclusion_label}`?",
                    "",
                    "**Claim**",
                    _content(conclusion),
                    "",
                ]
            )
            if step.rationale:
                lines.extend(["**Because**", step.rationale, ""])
            if step.premise_ids:
                lines.append("**Given**")
                for premise_id in step.premise_ids:
                    premise = k_by_id.get(premise_id)
                    label = _display_label(premise, premise_id)
                    lines.append(f"- `{label}`: {_preview(_content(premise))}")
                    if premise_id not in seen_refs:
                        references.append(premise_id)
                        seen_refs.add(premise_id)
                lines.append("")
            if step.background_ids:
                lines.append("**Background**")
                for background_id in step.background_ids:
                    background = k_by_id.get(background_id)
                    label = _display_label(background, background_id)
                    title = background.get("title") if isinstance(background, dict) else None
                    suffix = f": {title}" if title else ""
                    lines.append(f"- `{label}`{suffix}")
                    if background_id not in seen_refs:
                        references.append(background_id)
                        seen_refs.add(background_id)
                lines.append("")

    if references:
        lines.extend(["## References", ""])
        for ref in references:
            item = k_by_id.get(ref)
            label = _display_label(item, ref)
            lines.extend([f"### `{label}`", _content(item), ""])

    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 3: Add JSON renderer**

Append:

```python
def context_to_json_dict(packet: ContextPacket) -> dict[str, Any]:
    return {
        "context_schema_version": 1,
        "focus": {
            "id": packet.focus.resolved_id,
            "label": packet.focus.resolved_label,
        },
        "selection": {
            "trajectory": packet.trajectory,
            "order": packet.order,
        },
        "why_route": [
            {
                "edge_kind": step.edge_kind,
                "target_id": step.target_id,
                "label": step.label,
                "status": step.status,
                "conclusion": step.conclusion_id,
                "premises": list(step.premise_ids),
                "background": list(step.background_ids),
            }
            for step in _ordered_steps(packet)
        ],
        "ir": packet.ir,
    }
```

- [ ] **Step 4: Run direct module import check**

Run:

```bash
uv run --project . python -c "from gaia.cli.commands._context import build_context_packet, render_context_markdown, context_to_json_dict; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 5: Commit renderers**

Run:

```bash
git add gaia/cli/commands/_context.py
git commit -m "feat: render inquiry context packet"
```

---

### Task 5: Wire The Public CLI Command

**Files:**
- Modify: `gaia/cli/commands/inquiry.py`
- Test: `tests/cli/test_inquiry_context.py`

- [ ] **Step 1: Import context helpers**

At the top of `gaia/cli/commands/inquiry.py`, add:

```python
from typing import cast

from gaia.cli.commands._context import (
    RenderOrder,
    TrajectorySelector,
    build_context_packet,
    context_to_json_dict,
    render_context_markdown,
)
```

- [ ] **Step 2: Add `context` command before the review command**

Insert before the `# review` section:

```python
@inquiry_app.command("context")
def context_command(
    path: str = typer.Argument(".", help="Package path."),
    focus_: str | None = typer.Option(None, "--focus"),
    trajectory: str = typer.Option("most_uncertain", "--trajectory"),
    order: str = typer.Option("backward", "--order"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Render a focus-centered context packet for the current inquiry claim."""
    if trajectory not in {"most_uncertain", "shortest"}:
        typer.echo(
            "Error: --trajectory must be one of: most_uncertain, shortest.",
            err=True,
        )
        raise typer.Exit(2)
    if order not in {"backward", "forward"}:
        typer.echo("Error: --order must be one of: backward, forward.", err=True)
        raise typer.Exit(2)

    try:
        packet = build_context_packet(
            path,
            focus_override=focus_,
            trajectory=cast(TrajectorySelector, trajectory),
            order=cast(RenderOrder, order),
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    if json_out:
        typer.echo(json.dumps(context_to_json_dict(packet), ensure_ascii=False, indent=2))
    else:
        typer.echo(render_context_markdown(packet), nl=False)
```

- [ ] **Step 3: Run the context CLI tests**

Run:

```bash
uv run --project . python -m pytest tests/cli/test_inquiry_context.py -q
```

Expected: PASS.

- [ ] **Step 4: Run focused existing inquiry tests**

Run:

```bash
uv run --project . python -m pytest tests/cli/test_inquiry.py tests/inquiry/test_state.py tests/inquiry/test_focus.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit CLI wiring**

Run:

```bash
git add gaia/cli/commands/inquiry.py tests/cli/test_inquiry_context.py
git commit -m "feat: add inquiry context command"
```

---

### Task 6: Update CLI Documentation

**Files:**
- Modify: `docs/reference/cli/inquiry.md`
- Modify: `docs/for-users/cli-commands.md`

- [ ] **Step 1: Update inquiry reference**

In `docs/reference/cli/inquiry.md`, add `context` to the command list and table:

```markdown
gaia inquiry context [path]                Render focus-centered agent context
```

Add this table row:

```markdown
| `context` | Render a read-only focus-centered context packet as Markdown, or a JSON envelope with an IR slice |
```

Add a short section before `## Implementation`:

```markdown
## Context packets

`gaia inquiry context` renders the current focus claim and the selected reasoning
trajectory behind it. Markdown is the default because the output is intended for
agent context. Use `--json` for tools; the JSON output is a thin envelope whose
`ir` field is a Gaia IR-shaped slice.

```bash
gaia inquiry focus acceleration_inquiry
gaia inquiry context .
gaia inquiry context . --trajectory shortest
gaia inquiry context . --focus acceleration_inquiry --json
```

The command is read-only: it does not save inquiry state, append tactic events,
run inference, or display beliefs.
```

- [ ] **Step 2: Update user-facing CLI list**

Find the inquiry command section in `docs/for-users/cli-commands.md` and add:

```markdown
- `gaia inquiry context [path] [--focus CLAIM] [--trajectory most_uncertain|shortest] [--order backward|forward] [--json]`
  - Renders a read-only context packet for the current focus claim.
```

- [ ] **Step 3: Run docs grep sanity check**

Run:

```bash
rg -n "inquiry context|most_uncertain|Why This Claim" docs/reference/cli/inquiry.md docs/for-users/cli-commands.md
```

Expected: both documentation files mention `inquiry context`; `most_uncertain` appears in the user-facing command list.

- [ ] **Step 4: Commit docs**

Run:

```bash
git add docs/reference/cli/inquiry.md docs/for-users/cli-commands.md
git commit -m "docs: document inquiry context command"
```

---

### Task 7: Final Verification

**Files:**
- No source changes expected in this task.

- [ ] **Step 1: Run the full focused test slice**

Run:

```bash
uv run --project . python -m pytest tests/cli/test_inquiry_context.py tests/cli/test_inquiry.py tests/inquiry/test_review.py tests/inquiry/test_state.py tests/inquiry/test_focus.py -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting and lint checks for touched files**

Run:

```bash
uv run --project . ruff format --check gaia/cli/commands/_context.py gaia/cli/commands/_inquiry.py gaia/cli/commands/inquiry.py tests/cli/test_inquiry_context.py
uv run --project . ruff check gaia/cli/commands/_context.py gaia/cli/commands/_inquiry.py gaia/cli/commands/inquiry.py tests/cli/test_inquiry_context.py
```

Expected: both commands PASS.

- [ ] **Step 3: Manually smoke the CLI on a temporary package**

Run:

```bash
tmpdir=$(mktemp -d)
uv run --project . gaia pkg scaffold --target "$tmpdir/context-demo-gaia" --name context-demo-gaia --no-check
uv run --project . gaia author claim "Observed falling bodies do not separate enough to support proportional-speed scaling." --target "$tmpdir/context-demo-gaia" --dsl-binding-name obs_fall --label obs_fall --no-check
uv run --project . gaia author claim "The proportional-speed law for falling bodies is not a reliable account of free fall." --target "$tmpdir/context-demo-gaia" --dsl-binding-name reject_prop_speed --label reject_prop_speed --no-check
uv run --project . gaia author derive --conclusion reject_prop_speed --given obs_fall --target "$tmpdir/context-demo-gaia" --dsl-binding-name observation_refutation --label observation_route --rationale "The observation pressures proportional-speed scaling." --no-check
uv run --project . gaia inquiry focus reject_prop_speed --path "$tmpdir/context-demo-gaia"
uv run --project . gaia inquiry context "$tmpdir/context-demo-gaia"
uv run --project . gaia inquiry context "$tmpdir/context-demo-gaia" --json
```

Expected: Markdown output contains `## Focus`, `## Why This Claim`, and `## References`; JSON output parses and contains `context_schema_version`.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short --branch
```

Expected: clean branch with the implementation commits from Tasks 1 through 6.
