# Trace: Gaia

### EARS — Progress (2026-04-20 14:50)
<!-- concepts: compile-time-formalization, support-strategy, hypothesis-testing -->
Found that `support` and `compare` were missing from `_COMPILE_TIME_FORMAL_STRATEGIES` in `compile.py`. Without compile-time formalization, these strategies stay as bare `Strategy` in IR and get lowered as ternary IMPLICATION factors (instead of binary SOFT_ENTAILMENT CPT). The ternary helper claim blocks backward message propagation, preventing hypothesis differentiation in abduction structures. Adding `support` and `compare` to the set fixes lowering → hypothesis_mutation goes from 0.33 to 0.47 in the luria-delbruck package.

### EARS — Progress (2026-04-20 19:15)
<!-- concepts: gaia-lang-v6, likelihood-library, reference-semantics -->
Integrating GPT Pro's v6 IR and Lang design specs into the repo (PR #450). Key design decisions made in this session:

1. **Knowledge object references in parameterized Claims**: Decided that Knowledge-typed parameters (Setting, Claim) use `[@param_name]` reference syntax in docstring templates, while value-typed parameters (int, float, str) use `{param_name}` format substitution. Two syntaxes coexist — compiler resolves `[@...]` first, then applies `str.format()`.

2. **Standard likelihood library**: Instead of requiring users to manually declare 5+ assumption Claims for every AB test, provide `ab_test(counts, target)` one-line helpers that auto-generate standard assumptions (RandomAssignment, ConsistentLogging, NoEarlyStopping) as parameterized Claims referencing the experiment Setting. Users can override via manual `likelihood_from()`.

3. **No `Ref[T]` wrapper**: Considered `Ref[T]` generic type vs direct object passing vs string labels. Chose direct object passing (`experiment: Setting`) — simplest, type-safe, consistent with existing Strategy API where premises are passed as objects.
