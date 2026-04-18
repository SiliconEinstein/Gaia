# Trace: Gaia

<!-- concepts: legacy-cleanup, documentation-lifecycle -->

## 2026-04-18: Legacy code cleanup

- Part A (disk-only): Removed 13 ghost `__pycache__` dirs, 8 stale worktrees (~1.6 GB), node_modules/egg-info/.coverage
- Part B (git-tracked): Removed 17 obsolete scripts, 4 Typst v4 fixture dirs, 6 orphan fixture dirs, 2 Typst-era docs
- Caught mistake: `hole-bridge-tutorial.md` and `cli-commands.md` are v5 content, not Typst-era — restored them
- User feedback: outdated docs should be marked "Needs upgrade to v5" and upgraded in a follow-up PR, not simply deleted

### EARS — Progress (2026-04-18 10:34)
<!-- concepts: repo-split, lkm-cleanup -->
- LKM code has been split to SiliconEinstein/gaia-lkm repo. Now removing all LKM remnants from main Gaia repo.
- Boundary is clean: gaia.lkm is fully self-contained, zero reverse deps from cli/ir/bp.
- Removing: gaia/lkm/ (44 files), tests/gaia/lkm/ (16 files), frontend/, scripts/, LKM fixtures, LKM docs/plans/specs.
- pyproject.toml: removing `[server]` optional-deps, LKM pytest markers, coverage excludes.

### EARS — Progress (2026-04-18 11:38)
<!-- concepts: ci-fix, review-sidecar-deprecation -->
- PR #441 (`deprecate/review-sidecar`) CI failing: codecov/patch at 0% for `gaia/review/models.py` (6 uncovered lines).
- The 6 lines are: `import warnings`, `_DEPRECATION_MSG` constant, and 4 `warnings.warn()` calls added to ReviewBundle/review_claim/review_generated_claim/review_strategy.
- No existing tests for `gaia/review/` — created `tests/gaia/review/test_deprecation.py` with 4 tests covering all warn sites.

### EARS — Progress (2026-04-18 11:51)
<!-- concepts: review-sidecar-deprecation, test-migration -->
- Converting test fixtures from ReviewBundle/review_claim to priors.py pattern across 3 test locations (test_github_integration x2, test_detailed_reasoning x1).
- Also updating stale code comments and specs docs that still reference review sidecar as current.
- Pattern: priors.py exports `PRIORS: dict = {knowledge_obj: (prior, justification), ...}`, discovered by `apply_package_priors()` at compile time.

### EARS — Progress (2026-04-18 13:43)
<!-- concepts: induction-strategy, composite-strategy, factor-graph -->
Investigating `induction()` composite strategy for correctness. Found a bug: in the correct generative direction (`support([law], obs)`), the premise collection logic only iterates sub-strategy `.premises` (which is `[law]`, filtered out), missing the observations entirely (they're sub-strategy `.conclusion`s). Result: `composite.premises = []`. This doesn't break flat factor graph lowering (pure recursive expansion) but breaks tensor contraction (`contraction.py:411` treats obs as bridge vars) and forces coarsening to use orphan recovery heuristics.

Fix in progress: (1) enforce Mode A direction (law must be premise of support, not conclusion), (2) collect sub-strategy conclusions into composite premises.

### EARS — Progress (2026-04-18 17:20)
<!-- concepts: gaia-lang-v6, dsl-design, knowledge-type-system -->
- Wrote Gaia Lang v6 design spec at `docs/specs/2026-04-18-gaia-lang-v6-design.md`.
- Key design decisions: Knowledge base class + Claim/Setting/Question subclasses, Action = function decorator (Derive/Relate/Observe/Compute/Compose), parameterized Claim subclasses with docstring templates and Python type annotations, InquiryState via `gaia check --inquiry`, warrant review with pre-filled/blind modes.
- Critical insight from brainstorming: all Actions are functions, docstring = warrant, Compute wraps real Python code while others are empty-body. Claim subclasses define parameter schema (like Pydantic models), docstring is `str.format()` template.
- IR layer stays unchanged — everything compiles to existing Strategy + Operator IR.
- Next: user will request thought experiments to validate the spec.

### EARS — Progress (2026-04-18 22:00)
<!-- concepts: gaia-lang-v6, knowledge-type-system, epistemology -->
- Finalized Knowledge type hierarchy through thought experiments.
- Tested H/P/O three-way split — rejected: prediction and hypothesis are roles, not types.
- Tested Law as type — rejected: boundary is degree judgment (social epistemology), not structural.
- Tested Theory as type — accepted: structurally checkable (parameterized, derive premise, not observe-created).
- Final hierarchy: Knowledge > Setting | Claim > Observation, Theory, user-defined | Question
- Key insight: only types with hard structural criteria survive. Roles (hypothesis, prediction, law, fact) determined by graph topology, not type label.

### EARS — Progress (2026-04-18 22:28)
<!-- concepts: gaia-lang-v6, knowledge-type-system -->
- Not stuck. Multiple edits to v6 spec reflect iterative brainstorming with user, not thrashing.
- Key simplification: removed Theory as a type. Final hierarchy is 5 types only: Knowledge, Setting, Claim, Observation, Question.
- First-principles insight: Claim subclass = predicate schema, instance = ground formula. Python class/instance IS predicate logic. No extra concepts needed.
- Action (derive/observe/compute/relate/compose) = inference rules. Separate from predicates.
