# Evidence-based argument structuring

This guide covers how to use Gaia DSL to build a well-structured argument from
partial, proxy, or contested evidence. The product is a Gaia knowledge package
whose source DSL spells out the argument's logical skeleton: which claims
compete, which observations bear on which, what premises are missing, how
reliable each source is. The structure stands on its own — a reviewer can read
the source and form a judgment without ever running `gaia run infer`.

Probabilistic inference (Gaia BP) is an **optional** second step that
quantifies the structure. Many domains — legal evidence reasoning, qualitative
scientific argumentation, normative debate — do not afford honestly-calibrable
probabilities; the structure alone is the deliverable.

## Principle

**Logical structure is primary; probability is secondary.**

The numeric belief that `gaia run infer` produces is one signal alongside the
structural signals already in the source. Do not collapse the structural
reading into a threshold rule on the belief.

## 1. Read

- The task prompt: the claim to be supported, refuted, or judged uncertain,
  plus the available evidence.
- The Gaia cheat sheet at the path printed by `gaia sdk --out ./gaia-sdk`.

Use only `gaia.engine.lang` — the cheat sheet's import block.

## 2. Build the logical structure (no probability yet)

Scaffold a Gaia package and author `src/<name>/__init__.py`. Before writing any
concrete claim, work through these five structural questions. Each answer
points to a DSL pattern.

### Q1 — Relevance: does the evidence TYPE match the claim TYPE?

If the prompt reports a behaviour but the claim is about an outcome; a
correlation but the claim is about causation; a frequency in a sample but the
claim is about a mechanism; a measurement under conditions A but the claim is
about conditions B — the evidence does not address the claim.

**Pattern: declare the observation but do NOT link it to the hypothesis.**

```python
obs = observe("...")
# No infer / equal / contradict from obs to H_main.
# The observation stays in the source for the audit trail; the hypothesis
# stays at baseline because the evidence does not bear on it.

q_relevance = question(
    "What evidence TYPE would actually address this claim?",
    rationale="The available evidence is descriptive / proxy / out-of-scope "
              "for what the claim asks.",
)
```

### Q2 — Completeness: what premise(s) does the claim additionally require?

If the available evidence supports a sub-claim but the main claim requires
more — e.g. "X is independent of Y" entails non-redundancy, not superiority;
"X correlates with Y" entails association, not causation — those extra
requirements are missing premises.

**Pattern: decompose the claim, surface the gap as a low-prior premise.**

```python
H_main = claim("...")           # the main claim
H_sub = claim("...")            # what the evidence DOES support
H_missing = claim("...")        # what the evidence does NOT supply
register_prior(
    H_missing,
    value=0.3,
    justification="Absent from the available evidence.",
)

derive(H_main, given=[H_sub, H_missing])
```

The argument is now explicit: H_main rests on H_sub AND H_missing. A reviewer
can locate which premise is shaky to one line.

### Q3 — Alternatives: could the same evidence equally support a competing claim?

If H ("X causes Y") and H_alt ("Y causes X" / "common cause Z" / "alternative
explanation" / "the apparent pattern is artefact") are both consistent with
the observation, the evidence does not discriminate.

**Pattern: declare both claims and the structural constraint between them.**

```python
H = claim("...")
H_alt = claim("...")
exclusive(H, H_alt, rationale="Competing readings of the same evidence.")
```

The structural constraint stands whether or not you later attach
probabilities. If you do attach them, the constraint propagates through BP;
if you do not, a reviewer still sees that both readings are live.

### Q4 — Independence: do the evidence pieces actually count separately?

If three "studies" come from the same team / instrument / sample, or five
measurements come from the same protocol, or two analyses depend on a shared
assumption — they share a confound. Treating them as independent inflates the
apparent weight of the argument.

**Pattern: consolidate, or name the shared cause as its own claim.**

```python
# Option A — fold into one program-level observation:
obs_program = observe(
    "Across N sub-studies within one program (same authors / instrument / "
    "sample), the effect is consistently observed.",
    rationale="A single program-level observation, not N independent observations.",
)

# Option B — name the shared cause and gate every downstream inference through it:
shared_design = claim("All observations share design D.")
register_prior(
    shared_design,
    value=0.5,
    justification="The shared design may or may not generalise.",
)
```

### Q5 — Provenance: how reliable is the source of each piece of evidence?

A piece of evidence may pass Q1-Q4 (relevant, sufficient, discriminating,
independent) and still come from an unreliable source — a single
un-replicated experiment, an authority with known bias, a measurement tool of
poor calibration, an anonymous account, a retracted publication. The
argument's strength is bounded above by the weakest source.

**Pattern: surface provenance as a claim that gates the evidence's contribution.**

```python
obs = observe("...")

source_reliable = claim("The source of obs is well-calibrated and unbiased.")
register_prior(
    source_reliable,
    value=0.5,
    justification="Single-team result with no independent replication.",
)

# Downstream inference is gated through source_reliable as a scope claim:
infer(
    obs,
    hypothesis=H,
    given=[source_reliable],
    p_e_given_h=...,
    p_e_given_not_h=...,
)
```

A high-trust source (independent replication, well-audited dataset, peer review
by adversarial reviewers) gets a high prior on `source_reliable`; a
single-source or untested source gets a low one. The reviewer can locate the
trust assumption to one line in the source.

### A note on coherence

A sixth check — do the evidence pieces mutually support or contradict each
other — falls out naturally from Q1-Q5 because each piece is modelled
atomically and its relationship to the hypothesis is explicit. Mutually
contradictory evidence shows up as opposite-direction `infer` factors or as a
`contradict` relation. You do not need a separate Q for it.

## 3. Attach probabilities (optional)

If your domain calls for quantification, go back through what you wrote in §2
and attach:

- `register_prior(claim, value, justification=...)` for each claim whose
  baseline plausibility is uncertain.
- `p_e_given_h` / `p_e_given_not_h` on each `infer` factor.
- `bayes.compare` only if you have a genuinely parametric distributional
  hypothesis pair. See [Bayes hypothesis types](bayes-hypothesis-types.md) for
  when point-vs-composite distinctions matter.

**This step is optional.** Many domains do not have honestly-calibrable
probabilities. In those domains, leave priors and likelihoods unset —
`gaia build check` will report the structural properties (boundary premises,
derived conclusions, orphans, open questions) without inference, and that
report is the deliverable.

## 4. Review (before compiling)

Re-read your `__init__.py` and verify five properties:

- **Atomicity** — every `claim` / `observe` text is one proposition. No
  `"vs"`, `"compared to"`, `"more than"` inside the text — those go in the
  relations layer.
- **Coverage** — every substantive piece of evidence in the prompt is either
  modelled or has a defensible reason to be excluded.
- **Question completeness** — every gap surfaced in Q1 / Q2 has a
  corresponding `question()` claim recording what evidence would close it.
- **Provenance visibility** — every non-trivially-trusted observation has its
  source-reliability claim (Q5) attached.
- **No misuse of `bayes.compare`** — only use it when the hypothesis genuinely
  predicts a parametric distribution over a measurable observable. For
  comparative, normative, classifier-utility, descriptive, or differential
  claims, use `derive`, `exclusive`, or unlinked observations.

## 5. Compile and (optionally) infer

```bash
gaia build compile ./<name>-gaia
gaia build check   ./<name>-gaia       # the STRUCTURAL report — read this first
gaia run   infer   ./<name>-gaia       # only if you attached probabilities in §3
```

`gaia build check` is the structural deliverable. Its output enumerates:

- **Boundary premises** — claims with external priors.
- **Derived conclusions** — claims whose belief is propagated through the graph.
- **Orphans** — claims that participate in no relation. They should be
  intentional (e.g. an observation deliberately unlinked from H per Q1).
- **Open questions** — inquiry obligations from Q1, Q2, or Q5.

This report stands on its own. If the structure is incomplete or wrong, fix
it BEFORE attaching probabilities — running BP over a broken structure does
not fix it, it hides it under numbers.

## 6. Read the structure first; the belief is one signal

The numeric belief on the main hypothesis is one signal alongside the
structural signals already in the source. The structural signals are:

| Signal in the source DSL                                          | What the reviewer reads                                          |
|---|---|
| `exclusive(H, H_alt)` with neither side dominantly supported       | Evidence does not disambiguate competing readings.               |
| `question()` claim left open                                       | Decisive evidence is absent.                                     |
| `derive(...)` with a low-prior premise in `given=`                 | The chain depends on something not in evidence.                  |
| Observation declared but not linked to the hypothesis              | Concept mismatch — evidence does not address claim.              |
| Atomic observations with matched opposite-direction `infer` factors | Bilateral partial coverage cancels.                              |
| `source_reliable` claim with low prior gating an `infer` factor    | Evidence's effective weight is bounded by source reliability.    |

If any of these fire, the answer is **uncertain** independent of any computed
belief. If none fire and the structure plus probabilities point in one
direction, report `yes` / `no`. Apply a domain-specific decision threshold
only if your domain has a calibrated one; do not invent one.

**Belief is computed; judgment is read from the structure.** Probability
quantifies the argument; it does not replace it.

## 7. Write the result

A reproducible result record should include:

- The claim in affirmative form.
- The predicted answer (`yes` / `no` / `uncertain`).
- The Gaia package path (so reviewers can re-compile and re-infer).
- The numeric `gaia_posterior`, if probabilities were attached in §3.
- The list of fired structural signals from §6 and why each one points to
  the chosen answer.
- A short reasoning paragraph explaining which of Q1-Q5 applied, which
  patterns you used, and how the structural signals (and belief, if
  attached) support the answer.

## Constraints

- Use only `gaia.engine.lang`. Do not import from `gaia.engine.bp.*` (engine
  internals).
- Probability attachment (§3) is optional. The structural deliverable (§2 →
  §5 `gaia build check`) is load-bearing.

## When to use this guide vs. the other authoring docs

- For everyday authoring of a knowledge package where the structure is
  straightforward and probability calibration is routine, follow the
  [authoring workflow](authoring-workflow.md).
- For the choice of distribution within a `bayes.compare` (point vs.
  composite hypothesis), see [Bayes hypothesis types](bayes-hypothesis-types.md).
- **This guide is for when the evidence is partial, proxy, or contested and
  the right answer requires structured judgment** — when "what is missing"
  and "what alternative explanations remain" are first-class parts of the
  argument, not afterthoughts.
