"""The self-contained survey procedure baked into every emitted task.

CLIENT.md "no skill": the ``gaia-lkm-explorer`` agent skill is retired, and its
survey procedure — the turn-loop semantics, ``survey-one-contact``, the
``mapping-contract`` rules, and the five step docs — is **absorbed here** so the
task envelope is self-contained. An agent reading *only* the task can survey
correctly and re-invoke the client.

The text is intentionally complete prose (not a pointer to a registered skill):
it carries the "LLM proposes / engine adjudicates" integrity contract, the v1
limits, the per-contact survey procedure, the LKM-specific mapping rules
(evidence-status vocabulary, support discipline, open-question-first
contradiction handling), the authoring surface (Tier 1 direct SDK / Tier 2 ``gaia
author``), and the re-invocation handshake.

Build 8 (CLIENT.md): the logging/bookkeeping *ceremony* was trimmed — the
forced-provenance ``**metadata`` mandate (provenance kwargs are now merely
available/encouraged), the hard ">=2 distinct support-channel queries per target"
mandate, the ``support_not_found`` recording clause, and the scratch-note
recording requirements are gone. The scientific-integrity *mapping* rules are
untouched: the evidence-status taxonomy, the self-contained-claim rule, "don't
invent premises/support", open-question-first contradiction handling, the
LLM-proposes/engine-adjudicates contract + v1 limits, and the API-correctness
notes (``register_prior(...)`` not ``prior=``; no ``metadata=`` kwarg on
contradict/derive/equal; ``gaia author depends-on`` rejecting unmaterialized
targets) all survive.
"""

from __future__ import annotations

# The integrity contract + honest v1 limits (absorbed from SKILL.md "Mission" /
# "Honest v1 limits"). These set what the loop can and cannot show.
_CONTRACT = """\
# Exploration survey task — self-contained

You are the *thin agent* in a fog-of-war exploration of human scientific
knowledge. The `gaia-lkm-explore` orchestrator has already run the deterministic
engine for this turn and emitted this task. Your job is the **fuzzy survey
only**: read messy LKM evidence, propose claims + priors + relations, and
materialize them into the Gaia package. The engine then adjudicates the
*consequence* (belief propagation) — you never decide what is true.

> Integrity contract — LLM proposes, engine adjudicates.
> - You (the agent) do the fuzzy work: read LKM evidence, propose claims/relations,
>   map them onto Gaia primitives.
> - The Gaia engine does the rigorous work: propagate belief, surface which
>   contradictions fire and whose belief falls — as a consequence of the math,
>   not your opinion. That happens when you re-invoke `gaia-lkm-explore turn` (it
>   compiles + infers + rounds).

## Honest v1 limits (read before surveying)

- Contradictions are LLM-authored; the engine adjudicates the *consequence*, not
  the *existence*. You hand-author `contradict(A, B)`; the checkpoint reports the
  consequence (whose belief dropped).
- The frontier grows primarily from `lkm_related` contacts. Each survey's
  `gaia search lkm` returns related papers you haven't pulled; feeding that JSON
  to `gaia-lkm-explore observe` records them as `lkm_related` paper-contacts — the
  primary expansion signal. `depends_on` contacts (from a pulled paper's
  formalization manifest) are a secondary, intra-survey signal. If you neither
  observe related papers nor pull a paper, the frontier can go empty — expected,
  not a bug. So observe every search, and pull at least one paper per turn.
- Live scorer features: `belief_entropy` (uncertainty), `closeness_to_seed`
  (relevance), `new_territory` (coverage; live for lkm contacts only), and
  `survey_cost`. `tension_potential` / `bridge_potential` are 0.0 slots, so the
  `Inquisitor` doctrine is currently inert; prefer `Surveyor` / `Cartographer`.
"""

# The per-contact survey procedure (absorbed from survey-one-contact.md + the
# five step docs + mapping-contract.md), and the LKM/authoring specifics.
_SURVEY_PROCEDURE = """\
## How to survey

You survey the contacts listed in this task (round 0: survey the seed(s) instead
— see `seed_survey`). For EACH contact (or seed), run this inner procedure:

1. Pull LKM evidence for the contact's target.
   - `gaia search lkm knowledge "<query>" --limit 8` for recall, and
     `gaia search lkm reasoning "<query>"` / `gaia search lkm reasoning
     --claim-id <id>` for chains.
   - Anchor queries on the contact's `ref.value` and its `sources` (the
     surveyed nodes that reach it). Save the DEFAULT-format JSON (`--format
     gaia-json`, the default) — `observe` reads that normalized envelope, not
     `--format raw-json`. Its shape is `{schema_version, query, results: [...]}`;
     each result carries `id`, `kind`, `rank.score`, `gaia.{qid,object_kind}`,
     `source.{paper_id,paper_title,doi,role,has_reasoning,has_evidence,
     conclusion_id,has_factors,can_compile}`, `actions[]`, and `raw.payload`
     (the verbatim upstream node/chain, the only place factor detail survives).

2. RECORD unpulled related papers as frontier contacts — REQUIRED, the primary
   growth path. Pipe each search's JSON to:
       gaia-lkm-explore observe <pkg> --source <this-contact-or-seed-qid> \\
           --query "<query>" --search-json /tmp/leads.json
   Every result whose paper is not materialized becomes an `lkm_related`
   paper-contact, ranked next round. Do this for EVERY survey query.

3. PULL the top related paper(s) to open new territory:
       gaia pkg add --lkm-paper <paper_id>
   This scaffolds the paper as an editable `-gaia` dependency sub-package and
   writes its `depends_on` scaffolds; it (a) promotes that paper's `lkm_related`
   contact to surveyed and (b) adds intra-survey `depends_on` contacts.
   Do NOT use `gaia author depends-on` for an unmaterialized target — it rejects
   an unresolved `--given` by design (that core validation must not be weakened).

4. AUTHOR the science onto Gaia DSL primitives, classifying each LKM result by
   evidence status (mapping contract). Read the status straight off the default
   envelope — there is no `total_chains` field; a result is chain-backed iff the
   normalizer says so:
   - Chain-backed claim — a `reasoning` result (`kind == "reasoning_chain"`) with
     `source.can_compile == true` / `source.has_factors == true` (equivalently
     `gaia.object_kind == "derive"`), or a `knowledge` claim with
     `source.has_reasoning == true` (its `inspect` action gives the
     `gaia search lkm reasoning --claim-id <id>` to fetch the chain). Emit
     `claim(...)` for the conclusion + each usable premise, and one
     factor-derived `derive(conclusion, given=[premises],
     rationale="<numbered LKM steps>", label="<factor_id>")` per factor in
     `raw.payload.factors[]` (LKM factor ids are `lfac_*`; use that id as the
     label).
   - LKM source claim — no compilable chain (a `knowledge` claim with
     `source.has_reasoning == false`, or a `reasoning_chain` with
     `source.can_compile == false`): emit a leaf/source `claim(...)` with
     `provenance_source="lkm_no_chain"` and the preserved `lkm_id` (the result's
     `id`); do not invent premises, factors, or derives.
   - Search lead — a `question` result, or any result with insufficient
     content/provenance: do not emit.
   - Make every claim self-contained (system/material, method, quantity, value,
     conditions) so it is judgeable true/false without the LKM payload.
   - Supports: `derive(target, given=[U], rationale="...", label="...")` is
     directional (U supports target). Do not fabricate support.
       If two supports share a common factor, extract it as a shared-factor claim
       and route both through it (avoids double-counting in BP).
   - Contradictions (open-question-first): for a tension, first name the
     field-facing open problem. Promote to `contradict(A, B)` only when it is an
     adjudicable scientific conflict; label it `<side_a>_vs_<side_b>` and put the
     `open_problem:` clause + warrant intent in `rationale=` (no `metadata=`
     kwarg on `contradict`/`derive`/`equal`). Otherwise keep it as an inquiry
     hypothesis: `gaia inquiry hypothesis add "<open problem>" --scope <ns>::<label>`.
   - Priors: never pass a `prior=` kwarg on `claim(...)`; leaf priors are
     `register_prior(...)` records in `priors.py`.

## Authoring surface (one model, two tiers)

Run `gaia sdk --out ./gaia-sdk` once and read its `CHEATSHEET.md` — the documented
first move and the live DSL surface.
- Tier 1 (primary): write DSL directly into the package source —
  `from gaia.engine.lang import claim, derive, contradict, equal, exclusive,
  note, question, register_prior, ...` in `src/<import>/__init__.py` (+ siblings).
  Provenance kwargs (`provenance_source`, `lkm_id`, originating `query`/node id)
  are available and encouraged as `**metadata` on `claim(...)` (only `claim`
  accepts `**metadata`; warrant intent for `derive`/`contradict`/`equal` goes in
  their `rationale=`).
- Tier 2 (optional convenience): `gaia author claim|note|question|derive|
  contradict|equal|exclusive|register-prior` writes the SAME DSL into
  `src/<import>/authored/` (re-exported from the package root), with machine
  checks. Use it when you want guarded appends; write Python directly otherwise.
"""

# The re-invocation handshake (absorbed from SKILL.md §5/§6 + survey-one-contact
# "after surveying all contacts"). This is what makes the loop resumable.
_HANDOFF = """\
## When you are done surveying

1. Write the result manifest to the `result_path` named in this task, a minimal
   JSON envelope:
       {"surveyed_qids": ["<qid you materialized>", ...]}
   List the QIDs you actually authored/materialized this turn — that is the only
   thing the client needs. The discovery report (from the checkpoint) is the
   human-facing output, and the client owns the durable record, so you keep no
   log.

2. Re-invoke the orchestrator to checkpoint:
       gaia-lkm-explore turn <pkg>
   It detects the result manifest, then (via the SDK) compiles + infers + runs
   `explore round` — recomputing belief and emitting the discovery report
   (contradiction / keystone / settled_core) — and returns to IDLE. You do NOT
   run compile/infer/round yourself, and you do NOT edit `turn_phase` by hand.

3. The orchestrator stops for human review. The human re-dials the doctrine (if
   desired) and the next `gaia-lkm-explore turn <pkg>` opens turn n+1.

Do not run a standalone end-of-run report — the checkpoint's discovery report is
the per-turn hand-off.
"""


def build_survey_instructions(*, seed_survey: bool) -> str:
    """Return the full self-contained survey procedure for a task envelope.

    Args:
        seed_survey: ``True`` for the round-0 seed-survey task (no frontier yet)
            — the agent surveys the seed(s); ``False`` for a normal turn where the
            agent surveys the ranked frontier contacts in the task.

    Returns:
        Markdown prose carrying the integrity contract, v1 limits, the per-contact
        survey procedure, the authoring surface, and the re-invocation handshake —
        everything an agent needs to survey without any external skill.
    """
    if seed_survey:
        round_note = (
            "## This is round 0 (survey the seed)\n\n"
            "The frontier is empty — there is nothing materialized yet. Survey the "
            "SEED(S) named in this task's `contacts` (each carries the seed text in "
            "its `survey_brief`). Surveying a seed = running the per-contact "
            "procedure below with the seed text as your initial LKM query; "
            "`gaia-lkm-explore observe` on that survey is what seeds round 1's frontier "
            "with `lkm_related` paper-contacts.\n"
        )
    else:
        round_note = (
            "## This is a frontier turn\n\n"
            "Survey the ranked `contacts` in this task (the engine already chose the "
            "top-k for the round's doctrine). Each contact's `survey_brief` says what "
            "it is, how it is reached (`sources`), and the concrete next command "
            "(e.g. the `gaia pkg add --lkm-paper` pull line for a paper-contact).\n"
        )
    return "\n".join([_CONTRACT, round_note, _SURVEY_PROCEDURE, _HANDOFF])


__all__ = ["build_survey_instructions"]
