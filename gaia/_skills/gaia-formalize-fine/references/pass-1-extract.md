# Pass 1 — Extract knowledge nodes

Load this file when starting Pass 1. When the pass is complete, run the
compile + check inner loop (see `../SKILL.md` → "Inner loop") and then load
`pass-2-connect.md`.

Read the source **section by section**. For each section, identify:

| Type | Criterion | Examples | Author verb |
|------|-----------|---------|---|
| **note** | Background facts that cannot be questioned | Mathematical definitions, formal setups, fundamental principles | `gaia author note` |
| **claim** | Propositions that can be questioned or falsified | Computation results, theoretical derivations, predictions, experimental observations | `gaia author claim` |
| **question** | Open research questions | Driving questions for the source | `gaia author question` |

### Organize by module

Each source section corresponds to one Gaia module (Python file):

- Introduction → `motivation.py`
- Section II → `s2_xxx.py`
- ...

The module's docstring serves as the section heading. Each knowledge node should have a `title` parameter. Add modules with `gaia pkg add-module` (see `../SKILL.md` → "CLI invocations").

### Place knowledge in the earliest module

Each knowledge node belongs in the module corresponding to the section where it **first appears** in the source. Content from the Introduction goes into `motivation.py`. Claims in `motivation.py` can be freely referenced as premises or background by later modules — they are not restricted by module membership. Notes and questions are typically referenced via `background=`.

### `note` vs `claim` classification guide

**Principle: when in doubt between `note` and `claim`, mark it as `claim`.**

| Category | Type | Examples |
|----------|------|---------|
| Mathematical definitions / formal setups | **note** | Coordinate system choice, variable decomposition definitions, mathematical form of potentials |
| Established fundamental principles | **note** | Conservation laws, exclusion principle, laws of thermodynamics |
| Standard approximation / method definitions (without applicability assertions) | **note** | Mathematical expression of an approximation (definition only, not asserting applicability) |
| Whether applicability conditions hold | **claim** | Whether an approximation applies to a specific system |
| Theoretical frameworks dependent on conditions | **claim** | "Theorem B holds when A is satisfied" |
| Theoretical derivation results | **claim** | Renormalization relations, scaling laws, asymptotic behaviour |
| Numerical computation results | **claim** | Values from computational methods |
| Experimental observations | **claim** | Measured quantities |

**Key criterion:** can this proposition be questioned? If yes → `claim`. Only mathematical definitions and formal setups qualify as notes.

**Distinguish definitions from assertions.** The mathematical definition of an approximation is a note; "this approximation is unreliable under certain conditions" is a claim. "Decompose the variable into high- and low-frequency parts" is a note (mathematical operation), but "the contribution of the high-frequency part is negligible" is a claim (physical assertion).

**Dependency chains.** If A is a note and B depends on A being true while containing a physical assertion — B is typically a claim.

Content that the source itself derives — even when the derivation is rigorous — should be a claim, because the derivation process itself may contain errors.

### Shared extraction methodology

The rules for writing claim content — content format, **atomicity**, figures
and tables transcribed as prose, self-contained bodies — are shared with
`gaia-formalize-coarse` and live in `_shared/`. Load and apply both:

- [`../../_shared/formalize-extract-conclusions.md`](../../_shared/formalize-extract-conclusions.md)
  — fidelity to the source, self-contained claim bodies, content format
  (Markdown tables, `$...$` math, lists), figures and tables transcribed as
  prose, the no-paper-internal-pointer rule, the `refs` whitelist, and
  citation form. It also states the rule to **extract both sides of a
  theory-vs-experiment comparison** and **every observation in a
  repeated-observation set** as separate claims, so Pass 2 can wire them
  (`infer` for theory-vs-experiment; `derive` over the observations for a
  generalisation — see Pass 2 and Pass 4).
- [`../../_shared/formalize-atomicity.md`](../../_shared/formalize-atomicity.md)
  — one claim = one citable question, the theory/experiment and
  method/result separation corollaries, the under-splitting traps, the split
  and standalone-citation tests.

Fine-specific points beyond the shared rules:

- The `note` vs `claim` classification above is unique to this skill;
  `gaia-formalize-coarse` emits no `note`.
- Artifact file paths for rendering
  (`metadata={"figure": "...", "caption": "..."}`) are added in Pass 6, not
  here — see [`pass-6-polish.md`](pass-6-polish.md). They complement the
  shared `refs` whitelist: `refs` records provenance pointers,
  `metadata.figure` records the artifact path the renderer needs.

### Pass 1 reflection

After extracting all modules, ask yourself:

- **Theory vs experiment separated?** For every result where the source compares theory to experiment, do I have separate claims for the theoretical prediction and the experimental measurement? If mixed in one claim, Pass 2 cannot wire them with `infer`.
- **Figures and tables transcribed?** Are all key numerical values from figures and tables written into claim content (not just referenced)?
- **Each claim independently judgeable?** Can a reviewer assess each claim without reading any other claim?
- **Contradictory claims identified?** When the source argues "A succeeds where B fails," or compares competing methods / hypotheses, have I extracted both sides as separate claims? These pairs become `contradict(...)` operators in Pass 2, providing strong BP constraints.

### Marking exported conclusions

The source's **core contributions** (new theoretical results, new numerical computation results, new experimental findings, key arguments) should be marked as exported conclusions in `__all__`. These are this knowledge package's external interface — other packages can reference them.

Criterion: if this result were removed from the source, the source would lose its core value.

When you use `gaia author claim` / `gaia author derive` / etc., the verbs default to `--export` on every Knowledge-producing call; explicitly pass `--no-export` for an internal-only binding.

### Pass 1 deliverable

One claim / note / question list per module.

Pass 1 only extracts atomic, self-contained knowledge nodes. **Do not prejudge which are "derived conclusions"** — whether a claim is an independent premise or a derived one depends on how reasoning connections are established in Pass 2, not on the claim itself.
