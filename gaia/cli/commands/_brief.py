"""gaia check --brief / --show — per-module warrant structure for agent review."""

from __future__ import annotations

from collections import defaultdict

from gaia.cli.commands._classify import classify_ir, node_role


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text with ellipsis."""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"


def _label_of(kid: str, knowledge_by_id: dict[str, dict]) -> str:
    k = knowledge_by_id.get(kid, {})
    return k.get("label") or kid.split("::")[-1]


def _is_helper(label: str | None) -> bool:
    if not label:
        return True
    return label.startswith("__")


def _prior_str(metadata: dict | None) -> str:
    if not metadata:
        return ""
    p = metadata.get("prior")
    if p is not None:
        return f", prior={p}"
    return ""


def _get_prior(metadata: dict | None) -> float | None:
    if not metadata:
        return None
    return metadata.get("prior")


def _strategy_by_id(ir: dict) -> dict[str, dict]:
    """Build strategy_id → strategy dict mapping."""
    result: dict[str, dict] = {}
    for s in ir.get("strategies", []):
        sid = s.get("strategy_id")
        if sid:
            result[sid] = s
    return result


def _strategies_for_conclusion(ir: dict) -> dict[str, dict]:
    """Build conclusion_id → strategy dict mapping.

    When multiple strategies share the same conclusion (e.g. induction wrapping
    two support sub-strategies), prefer the composite strategy so that the
    brief output shows the full reasoning tree rather than a single leaf.
    """
    result: dict[str, dict] = {}
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if not conc:
            continue
        existing = result.get(conc)
        if existing is None:
            result[conc] = s
        elif s.get("sub_strategies") and not existing.get("sub_strategies"):
            # Prefer composite over leaf
            result[conc] = s
    return result


def _module_of(kid: str, knowledge_by_id: dict[str, dict]) -> str | None:
    return knowledge_by_id.get(kid, {}).get("module")


# ── Overview mode ──


def generate_brief_overview(ir: dict) -> list[str]:
    """Per-module compact overview of all non-helper nodes and strategies."""
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    c = classify_ir(ir)
    module_order = ir.get("module_order") or []

    # Group knowledges by module
    by_module: dict[str, list[dict]] = defaultdict(list)
    for k in ir["knowledges"]:
        label = k.get("label", "")
        if _is_helper(label):
            continue
        mod = k.get("module") or "Root"
        by_module[mod].append(k)

    # Group strategies by conclusion's module, skipping sub-strategies of composites
    # and deduplicating per-conclusion (prefer composite > formal > leaf).
    sub_ids: set[str] = set()
    for s in ir.get("strategies", []):
        for sid in s.get("sub_strategies") or []:
            sub_ids.add(sid)

    best_per_conc: dict[str, dict] = {}
    for s in ir.get("strategies", []):
        if s.get("strategy_id") in sub_ids:
            continue  # shown as part of their parent composite
        conc = s.get("conclusion")
        if not conc:
            continue
        existing = best_per_conc.get(conc)
        if existing is None:
            best_per_conc[conc] = s
        elif s.get("sub_strategies") and not existing.get("sub_strategies"):
            best_per_conc[conc] = s
        elif s.get("formal_expr") and not existing.get("formal_expr"):
            best_per_conc[conc] = s

    strat_by_module: dict[str, list[dict]] = defaultdict(list)
    for conc, s in best_per_conc.items():
        conc_label = _label_of(conc, knowledge_by_id)
        if _is_helper(conc_label):
            continue
        mod = _module_of(conc, knowledge_by_id) or "Root"
        strat_by_module[mod].append(s)

    # Group top-level operators by conclusion's module
    op_by_module: dict[str, list[dict]] = defaultdict(list)
    for o in ir.get("operators", []):
        if not o.get("operator_id"):
            continue  # skip embedded formal_expr operators
        conc = o.get("conclusion")
        if not conc:
            continue
        conc_label = _label_of(conc, knowledge_by_id)
        if _is_helper(conc_label):
            continue
        mod = _module_of(conc, knowledge_by_id) or "Root"
        op_by_module[mod].append(o)

    # Determine module iteration order
    modules = []
    for m in module_order:
        if m in by_module or m in strat_by_module or m in op_by_module:
            modules.append(m)
    for m in by_module:
        if m not in modules:
            modules.append(m)

    lines: list[str] = []
    for mod in modules:
        lines.append("")
        lines.append(f"\u2500\u2500 Module: {mod} " + "\u2500" * max(1, 50 - len(mod)))
        lines.append("")

        nodes = by_module.get(mod, [])
        settings = [k for k in nodes if k["type"] == "setting"]
        claims = [k for k in nodes if k["type"] == "claim"]
        questions = [k for k in nodes if k["type"] == "question"]

        if settings:
            lines.append("  Settings:")
            for k in settings:
                label = k.get("label", "?")
                content = _truncate(k.get("content", ""), 60)
                lines.append(f'    {label}: "{content}"')

        if claims:
            lines.append("  Claims:")
            for k in claims:
                label = k.get("label", "?")
                role = node_role(k["id"], "claim", c)
                prior = _get_prior(k.get("metadata"))
                prior_s = f", prior={prior}" if prior is not None else ""
                content = _truncate(k.get("content", ""), 50)
                lines.append(f'    {label} [{role}{prior_s}]: "{content}"')

        if questions:
            lines.append("  Questions:")
            for k in questions:
                label = k.get("label", "?")
                content = _truncate(k.get("content", ""), 60)
                lines.append(f'    {label}: "{content}"')

        strats = strat_by_module.get(mod, [])
        if strats:
            lines.append("  Strategies:")
            for s in strats:
                lines.append(_format_strategy_oneline(s, knowledge_by_id))

        ops = op_by_module.get(mod, [])
        if ops:
            lines.append("  Operators:")
            for o in ops:
                lines.append(_format_operator_oneline(o, knowledge_by_id))

    return lines


def _format_strategy_oneline(s: dict, knowledge_by_id: dict[str, dict]) -> str:
    stype = s.get("type", "?")
    premise_labels = [
        _label_of(p, knowledge_by_id)
        for p in s.get("premises", [])
        if not _is_helper(_label_of(p, knowledge_by_id))
    ]
    conc_label = _label_of(s.get("conclusion", ""), knowledge_by_id)
    meta = s.get("metadata") or {}
    prior = meta.get("prior")
    prior_s = f", prior={prior}" if prior is not None else ""
    reason = meta.get("reason", "")

    line = f"    {stype}([{', '.join(premise_labels)}] \u2192 {conc_label}{prior_s})"
    if reason:
        line += f'\n      reason: "{_truncate(reason, 70)}"'
    return line


def _format_operator_oneline(o: dict, knowledge_by_id: dict[str, dict]) -> str:
    otype = o.get("operator", "?")
    var_labels = [
        _label_of(v, knowledge_by_id)
        for v in o.get("variables", [])
        if not _is_helper(_label_of(v, knowledge_by_id))
    ]
    meta = o.get("metadata") or {}
    prior = meta.get("prior")
    prior_s = f", prior={prior}" if prior is not None else ""
    reason = meta.get("reason", "")

    conc_label = _label_of(o.get("conclusion", ""), knowledge_by_id)
    line = f"    {otype}({', '.join(var_labels)}{prior_s}) \u2192 {conc_label}"
    if reason:
        line += f'\n      reason: "{_truncate(reason, 70)}"'
    return line


# ── Module expansion mode ──


def generate_brief_module(ir: dict, module_name: str) -> list[str]:
    """Expand a module showing full content and recursive warrant trees."""
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    c = classify_ir(ir)
    sid_map = _strategy_by_id(ir)
    conc_map = _strategies_for_conclusion(ir)

    # Filter knowledges for this module
    nodes = [
        k
        for k in ir["knowledges"]
        if k.get("module") == module_name and not _is_helper(k.get("label", ""))
    ]
    if not nodes:
        return [f'No module named "{module_name}" found.']

    lines: list[str] = []
    lines.append("")
    lines.append(f"\u2550\u2550 Module: {module_name} (expanded) " + "\u2550" * 30)
    lines.append("")

    settings = [k for k in nodes if k["type"] == "setting"]
    claims = [k for k in nodes if k["type"] == "claim"]
    questions = [k for k in nodes if k["type"] == "question"]

    if settings:
        lines.append("  Settings:")
        for k in settings:
            label = k.get("label", "?")
            content = k.get("content", "")
            lines.append(f"    {label}:")
            lines.append(f"      {content}")
        lines.append("")

    if questions:
        lines.append("  Questions:")
        for k in questions:
            label = k.get("label", "?")
            content = k.get("content", "")
            lines.append(f"    {label}:")
            lines.append(f"      {content}")
        lines.append("")

    if claims:
        lines.append("  Claims:")
        for k in claims:
            label = k.get("label", "?")
            kid = k["id"]
            role = node_role(kid, "claim", c)
            prior = _get_prior(k.get("metadata"))
            prior_s = f", prior={prior}" if prior is not None else ""
            content = k.get("content", "")
            lines.append(f"    {label} [{role}{prior_s}]:")
            lines.append(f"      {content}")

            # If derived, show strategy tree
            strat = conc_map.get(kid)
            if strat:
                tree_lines = _format_warrant_tree(strat, knowledge_by_id, sid_map, indent=6)
                lines.extend(tree_lines)
        lines.append("")

    # Top-level operators in this module
    ops = [
        o
        for o in ir.get("operators", [])
        if o.get("operator_id")
        and _module_of(o.get("conclusion", ""), knowledge_by_id) == module_name
    ]
    if ops:
        lines.append("  Operators:")
        for o in ops:
            lines.append(_format_operator_expanded(o, knowledge_by_id, indent=4))
        lines.append("")

    return lines


def _format_operator_expanded(o: dict, knowledge_by_id: dict[str, dict], indent: int = 4) -> str:
    pad = " " * indent
    otype = o.get("operator", "?")
    var_labels = [_label_of(v, knowledge_by_id) for v in o.get("variables", [])]
    conc_label = _label_of(o.get("conclusion", ""), knowledge_by_id)
    meta = o.get("metadata") or {}
    prior = meta.get("prior")
    prior_s = f", prior={prior}" if prior is not None else ""
    reason = meta.get("reason", "")

    result = f"{pad}{otype}({', '.join(var_labels)}{prior_s}) \u2192 {conc_label}"
    if reason:
        result += f'\n{pad}  reason: "{reason}"'
    return result


# ── Detail mode (single claim/strategy) ──


def generate_brief_detail(ir: dict, label: str) -> list[str]:
    """Expand the warrant tree for a specific claim or strategy label."""
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    c = classify_ir(ir)
    sid_map = _strategy_by_id(ir)
    conc_map = _strategies_for_conclusion(ir)

    # Find the knowledge node by label
    target = None
    for k in ir["knowledges"]:
        if k.get("label") == label:
            target = k
            break

    if target is None:
        return [f'No claim or strategy with label "{label}" found.']

    kid = target["id"]
    role = node_role(kid, target["type"], c)
    prior = _get_prior(target.get("metadata"))
    prior_s = f", prior={prior}" if prior is not None else ""

    lines: list[str] = []
    lines.append("")
    lines.append(f"  claim: {label} [{role}{prior_s}]")
    lines.append(f"    content: {target.get('content', '')}")

    strat = conc_map.get(kid)
    if strat:
        lines.append("")
        tree_lines = _format_warrant_tree(strat, knowledge_by_id, sid_map, indent=4)
        lines.extend(tree_lines)

        # For composite strategies (abduction/induction), add review notes
        notes = _review_notes(strat, sid_map)
        if notes:
            lines.append("")
            lines.append("    Agent review notes:")
            for note in notes:
                lines.append(f"      {note}")
    elif target["type"] == "claim":
        lines.append("")
        lines.append("    (independent premise \u2014 no derivation strategy)")

    # Show premises with their content and priors
    if strat:
        premise_ids = strat.get("premises", [])
        visible_premises = [p for p in premise_ids if not _is_helper(_label_of(p, knowledge_by_id))]
        if visible_premises:
            lines.append("")
            lines.append("    Premises:")
            for pid in visible_premises:
                pk = knowledge_by_id.get(pid, {})
                p_label = pk.get("label", "?")
                p_role = node_role(pid, pk.get("type", "claim"), c)
                p_prior = _get_prior(pk.get("metadata"))
                p_prior_s = f", prior={p_prior}" if p_prior is not None else ""
                p_content = _truncate(pk.get("content", ""), 70)
                lines.append(f'      {p_label} [{p_role}{p_prior_s}]: "{p_content}"')

    return lines


# ── Warrant tree formatting ──


def _format_warrant_tree(
    strategy: dict,
    knowledge_by_id: dict[str, dict],
    sid_map: dict[str, dict],
    indent: int = 4,
) -> list[str]:
    """Recursively format a strategy's warrant tree."""
    pad = " " * indent
    lines: list[str] = []

    stype = strategy.get("type", "?")
    meta = strategy.get("metadata") or {}
    prior = meta.get("prior")
    prior_s = f", prior={prior}" if prior is not None else ""
    reason = meta.get("reason", "")

    premise_labels = [
        _label_of(p, knowledge_by_id)
        for p in strategy.get("premises", [])
        if not _is_helper(_label_of(p, knowledge_by_id))
    ]
    conc_label = _label_of(strategy.get("conclusion", ""), knowledge_by_id)

    # Check if this is a composite strategy
    sub_ids = strategy.get("sub_strategies")
    formal_expr = strategy.get("formal_expr")

    if sub_ids:
        # CompositeStrategy — recursively expand sub-strategies
        lines.append(f"{pad}\u2190 {stype} (composite, {len(sub_ids)} sub-strategies)")
        if reason:
            lines.append(f'{pad}  reason: "{_truncate(reason, 70)}"')

        for i, sub_id in enumerate(sub_ids):
            sub = sid_map.get(sub_id)
            if not sub:
                lines.append(f"{pad}  \u251c\u2500 (unresolved: {sub_id})")
                continue
            sub_type = sub.get("type", "?")
            sub_meta = sub.get("metadata") or {}
            sub_prior = sub_meta.get("prior")
            sub_prior_s = f", prior={sub_prior}" if sub_prior is not None else ""
            sub_reason = sub_meta.get("reason", "")

            sub_premise_labels = [
                _label_of(p, knowledge_by_id)
                for p in sub.get("premises", [])
                if not _is_helper(_label_of(p, knowledge_by_id))
            ]
            sub_conc_label = _label_of(sub.get("conclusion", ""), knowledge_by_id)

            is_last = i == len(sub_ids) - 1
            prefix = "\u2514\u2500" if is_last else "\u251c\u2500"
            cont = "  " if is_last else "\u2502 "

            lines.append(
                f"{pad}  {prefix} {sub_type}([{', '.join(sub_premise_labels)}]"
                f" \u2192 {sub_conc_label}{sub_prior_s})"
            )
            if sub_reason:
                lines.append(f'{pad}  {cont}  reason: "{_truncate(sub_reason, 60)}"')

            # Show warrant helpers for sub-strategy's formal_expr
            sub_formal = sub.get("formal_expr")
            if sub_formal:
                for op in sub_formal.get("operators", []):
                    op_conc = op.get("conclusion", "")
                    helper = knowledge_by_id.get(op_conc, {})
                    h_prior = _get_prior(helper.get("metadata"))
                    if h_prior is not None:
                        h_name = (helper.get("metadata") or {}).get(
                            "canonical_name", op_conc.split("::")[-1]
                        )
                        lines.append(f"{pad}  {cont}  warrant: {h_name} (prior={h_prior})")

    elif formal_expr:
        # FormalStrategy — show operator skeleton + warrant priors
        lines.append(
            f"{pad}\u2190 {stype}([{', '.join(premise_labels)}] \u2192 {conc_label}{prior_s})"
        )
        if reason:
            lines.append(f'{pad}  reason: "{_truncate(reason, 70)}"')

        for op in formal_expr.get("operators", []):
            op_type = op.get("operator", "?")
            op_vars = [_label_of(v, knowledge_by_id) for v in op.get("variables", [])]
            op_conc_id = op.get("conclusion", "")
            op_conc_label = _label_of(op_conc_id, knowledge_by_id)

            helper = knowledge_by_id.get(op_conc_id, {})
            h_prior = _get_prior(helper.get("metadata"))
            h_prior_s = f" (prior={h_prior})" if h_prior is not None else ""

            lines.append(
                f"{pad}  {op_type}([{', '.join(op_vars)}] \u2192 {op_conc_label}{h_prior_s})"
            )

    else:
        # Leaf strategy (infer)
        lines.append(
            f"{pad}\u2190 {stype}([{', '.join(premise_labels)}] \u2192 {conc_label}{prior_s})"
        )
        if reason:
            lines.append(f'{pad}  reason: "{_truncate(reason, 70)}"')
        if stype == "infer":
            n_premises = len(strategy.get("premises", []))
            lines.append(f"{pad}  (requires 2^{n_premises} CPT entries in review)")

    return lines


# ── Review notes for composites ──


def _review_notes(strategy: dict, sid_map: dict[str, dict]) -> list[str]:
    """Generate agent review notes for composite strategies."""
    stype = strategy.get("type", "")
    sub_ids = strategy.get("sub_strategies")
    if not sub_ids:
        return []

    notes: list[str] = []

    if stype == "abduction":
        # Compare support_h vs support_alt priors
        priors: list[tuple[str, float | None]] = []
        for sub_id in sub_ids:
            sub = sid_map.get(sub_id, {})
            sub_type = sub.get("type", "?")
            sub_prior = (sub.get("metadata") or {}).get("prior")
            priors.append((sub_type, sub_prior))

        support_priors = [(t, p) for t, p in priors if t == "support" and p is not None]
        if len(support_priors) >= 2:
            p_h = support_priors[0][1]
            p_alt = support_priors[1][1]
            if p_h is not None and p_alt is not None:
                gap = abs(p_h - p_alt)
                if gap < 0.2:
                    notes.append(
                        f"\u26a0 support_h.prior ({p_h}) vs support_alt.prior ({p_alt})"
                        f" \u2014 gap is small ({gap:.2f}), abduction provides weak"
                        " discrimination"
                    )
                else:
                    notes.append(
                        f"support_h.prior ({p_h}) vs support_alt.prior ({p_alt})"
                        f" \u2014 gap={gap:.2f}"
                    )

    elif stype == "induction":
        # Check consistency of support sub-strategy priors
        sub_priors: list[float] = []
        for sub_id in sub_ids:
            sub = sid_map.get(sub_id, {})
            p = (sub.get("metadata") or {}).get("prior")
            if p is not None:
                sub_priors.append(p)
        if sub_priors:
            min_p = min(sub_priors)
            max_p = max(sub_priors)
            if max_p - min_p > 0.15:
                notes.append(
                    f"\u26a0 Support priors vary: {sub_priors}"
                    " \u2014 check if observations have equal evidential weight"
                )
            else:
                notes.append(f"Support priors consistent: {sub_priors}")

    return notes


# ── Dispatch for --show ──


def dispatch_show(ir: dict, value: str) -> list[str]:
    """Dispatch --show value to module expansion or label detail."""
    module_order = ir.get("module_order") or []
    if value in module_order:
        return generate_brief_module(ir, value)

    # Also check module names that might have been supplied without the module prefix
    # Try matching against knowledge labels
    for k in ir["knowledges"]:
        if k.get("label") == value:
            return generate_brief_detail(ir, value)

    # Check if it's a module name not in module_order but present in knowledges
    modules_in_ir = {k.get("module") for k in ir["knowledges"] if k.get("module")}
    if value in modules_in_ir:
        return generate_brief_module(ir, value)

    return [f'No module or label matching "{value}" found.']
