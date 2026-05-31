"""The self-contained survey procedure baked into every emitted task.

CLIENT.md "no skill": the ``gaia-lkm-explorer`` agent skill is retired, and its
survey procedure — the turn-loop semantics, ``survey-one-contact``, the
``mapping-contract`` rules, and the five step docs — is **absorbed here** so the
task envelope is self-contained. An agent reading *only* the task can survey
correctly and re-invoke the client.

The text is intentionally complete prose (not a pointer to a registered skill):
it carries the "LLM proposes / engine adjudicates" integrity contract, the v1
limits, the per-contact survey procedure, the LKM-specific mapping rules
(evidence-status vocabulary, support discipline, composite-proposition
decomposition, candidate-relation pre-marking + adjudicable-conflict
contradiction handling), the authoring surface (Tier 1 direct SDK / Tier 2 ``gaia
author``), and the re-invocation handshake.

Build 8 (CLIENT.md): the logging/bookkeeping *ceremony* was trimmed — the
forced-provenance ``**metadata`` mandate (provenance kwargs are now merely
available/encouraged), the hard ">=2 distinct support-channel queries per target"
mandate, the ``support_not_found`` recording clause, and the scratch-note
recording requirements are gone. The scientific-integrity *mapping* rules are
untouched: the evidence-status taxonomy, the self-contained-claim rule, "don't
invent premises/support", the LLM-proposes/engine-adjudicates contract + v1
limits, and the API-correctness notes (``register_prior(...)`` not ``prior=``;
no ``metadata=`` kwarg on contradict/derive/equal; ``gaia author depends-on``
rejecting unmaterialized targets) all survive.

Build 11 (CLIENT.md steers 1/2/5/6): the authoring section gains a ``decompose``
delegation for composite propositions (steer 1) and a ``candidate_relation``
pre-mark → ``materialize`` scaffold path for tensions (steer 2); contradiction
promotion is re-gated on being an *adjudicable scientific conflict* rather than
forced through an ``open_problem:`` framing — open-problem language and the
``gaia inquiry hypothesis add`` route are reserved for genuinely unresolved
tensions (steer 5); and the ``pkg add --lkm-paper`` step now states it pulls the
paper's whole subgraph (steer 6). Build 11 also strips belief from the
agent-facing surface (steer 4): the live-features list no longer advertises
``belief_entropy`` and the engine's belief ranking stays internal.

Build 12 (CLIENT.md steer 3): the survey procedure gains a "mark obligations"
step — when the survey exposes a gap that must be discharged (missing prior, weak
support, structural hole, focus weakness), the agent records it with ``gaia
inquiry obligation add <target_qid> …`` and closes it with ``gaia inquiry
obligation close <qid>``. Open obligations BOOST matching frontier contacts next
turn (the agent-visible ``obligation_pressure`` scorer term), so marking
obligations steers where exploration goes next.

Build 16 (formalize-after-pull): the inner procedure now makes **formalizing the
pulled paper the primary authoring path** (new step 3b) — bring a pulled paper's
load-bearing claims into the reasoning graph by *referencing them by QID* via
``derive`` / ``depends-on`` / ``materialize`` (a pulled claim is a materialized
target), rather than restating them locally. ``lkm_no_chain`` source claims are
demoted to the explicit fallback for evidence you could not pull or that is
genuinely chain-less. Pairs with the frontier now surfacing a pulled paper's
not-yet-formalized claims as ``depends_on`` contacts (the formalize worklist).

Build 17 (checkpoint-formalize): the v1-limits now state that a pulled paper's
OWN internal reasoning enters BP automatically at the checkpoint — the
orchestrator promotes each pulled-paper ``depends_on`` factor to live ``derive``
and infers over the joint (root + pulled-paper) graph
(:mod:`gaia.lkm_explorer.engine.promote`). Step 3b (connecting a pulled paper UP to
the ROOT reasoning) is unchanged and stays the agent's manual job; the auto-promo
covers only the paper's intra-paper factors.
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
  primary expansion signal. `depends_on` contacts (a pulled paper's claims not yet
  wired into YOUR root reasoning) are a secondary, intra-survey signal. If you
  neither observe related papers nor pull a paper, the frontier can go empty —
  expected, not a bug. So observe every search, and pull at least one paper per turn.
- A pulled paper's OWN internal reasoning goes live automatically. When you
  re-invoke `gaia-lkm-explore turn`, the checkpoint promotes each pulled paper's
  intra-paper `depends_on` factors to live `derive` and infers over the joint
  (root + pulled-paper) graph — so a pulled paper's internal premise→conclusion
  structure enters belief propagation and moves belief on the map without any
  manual step. What still needs YOUR hand (step 3b) is connecting the pulled
  paper UP to your root reasoning — the `depends_on` contacts are that worklist.
- Survey-facing contact signals: `closeness_to_seed` (relevance),
  `new_territory` (coverage; live for BOTH lkm and qid contacts — low for
  intra-paper drilling, higher for opening new territory), `bridge_potential`
  (1.0 iff surveying/wiring the contact would connect an orphan island to the
  core — now live, EXPANSION.md §3.B), `obligation_pressure` (1.0 iff the contact
  discharges an open obligation you marked — see "Mark obligations" below), and
  `survey_cost`. The engine ranks the frontier for you and hands you the
  shortlist already ordered — survey in the order given. `tension_potential` is
  still a 0.0 slot, so the `Inquisitor` doctrine remains inert; prefer
  `Surveyor` / `Cartographer` (bridge-led `Diplomat` is now live too).
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
     conclusion_id,factors}` (where `source.factors` is a per-factor list of
     `{factor_id, premise_count}`), `actions[]`, and `raw.payload`
     (the verbatim upstream node/chain, the only place full factor detail survives).

2. RECORD unpulled related papers as frontier contacts — REQUIRED, the primary
   growth path. Pipe each search's JSON to:
       gaia-lkm-explore observe <pkg> --source <this-contact-or-seed-qid> \\
           --query "<query>" --search-json /tmp/leads.json
   Every result whose paper is not materialized becomes an `lkm_related`
   paper-contact, ranked next round. Do this for EVERY survey query.
   If the original research question is not in English and LKM search metadata
   hydration times out, KEEP the original seed/question but retry the LKM search
   with a faithful English equivalent query; record the actual search string in
   `--query` so the map preserves how the paper frontier was surfaced.

3. PULL the top related paper(s) to open new territory:
       gaia pkg add --lkm-paper <paper_id>
   A paper's claims are strongly inter-related, so this is NOT a single-claim
   pull: it materializes the paper's ENTIRE subgraph — all its claims/questions
   plus their `depends_on` edges — scaffolding the paper as an editable `-gaia`
   dependency sub-package. It (a) promotes that paper's `lkm_related` contact to
   surveyed and (b) adds intra-survey `depends_on` contacts.
   (Optional: preview the subgraph extent first with
   `gaia search lkm package --paper-id <paper_id>` — retrieve-only, counts via
   `source.stats`; it CANNOT materialize, so still run `pkg add --lkm-paper` to pull.)

3b. FORMALIZE what you pulled — the PRIMARY authoring path after a pull. A pulled
   paper's claims are materialized as QIDs `lkm:<paper-package>::<label>`; the
   labels (`p1`, `p10`, …) are opaque, so read their content — each pulled claim
   surfaces as a `depends_on` frontier contact carrying its title (and the joint
   node texts hold the full text). Bring the claims that bear on your question into
   YOUR reasoning graph by REFERENCING them by that QID — do NOT restate them
   locally as fresh leaves:
   - support: `gaia author derive --conclusion <your_claim> --given <pulled_qid>
     --rationale "<why it supports>"` (the pulled claim supports yours);
   - dependency: `gaia author depends-on --conclusion <your_claim>
     --given <pulled_qid>` — a pulled claim is a *materialized* target, exactly the
     case `depends-on` is FOR (it only rejects *unmaterialized* targets);
   - contradiction: pre-mark `candidate_relation(claims=[<your_claim>, <pulled_qid>],
     pattern="contradict")`, then promote with
     `materialize(scaffold, by=[contradict(<your_claim>, <pulled_qid>)])`.
   Formalizing is what folds the pulled paper into what the engine reasons over —
   and what puts it on the map; an unformalized pull is just literature sitting in
   a dependency. Formalize the load-bearing claims (not necessarily all of a
   paper's claims, but the ones that matter to your question) BEFORE moving on to
   the next contact.

   Multi-endpoint papers and meta-analyses need structure, not one giant gate. If
   a paper reports several independent endpoint conclusions (for example benefit,
   null-effect, and harm endpoints), do NOT put every pulled conclusion into one
   all-of `derive` for a single net claim. Author intermediate claims such as
   benefit signal / null-effect signal / harm signal, support each with its own
   relevant pulled conclusions, then connect those intermediate claims to the
   higher-level net-benefit interpretation. This avoids making belief hinge on an
   overly strict conjunction of unrelated endpoints.

4. AUTHOR remaining evidence from search results — for leads you surfaced via
   `gaia search lkm` but did not pull (or that have no compilable chain),
   classifying each LKM result by evidence status (mapping contract). Read the
   status straight off the default
   envelope — there is no `total_chains` field; a result is chain-backed iff the
   normalizer says so:
   - Chain-backed claim — a `reasoning` result (`kind == "reasoning_chain"`) with
     at least one factor whose `source.factors[].premise_count > 0` (equivalently
     `gaia.object_kind == "derive"`), or a `knowledge` claim with
     `source.has_reasoning == true` (its `inspect` action gives the
     `gaia search lkm reasoning --claim-id <id>` to fetch the chain). Emit
     `claim(...)` for the conclusion + each usable premise. Then route PER FACTOR
     in `raw.payload.factors[]` by its premises (NOT a chain-level flag):
       * `premise_count > 0` → one factor-derived `derive(conclusion,
         given=[premises], rationale="<numbered LKM steps>", label="<factor_id>")`
         (LKM factor ids are `gfac_*`; use that id as the label — `factor_id`
         may be null when upstream omits it; then fall back to the chain id);
       * `premise_count == 0` → a base/leaf factor: emit its conclusion as a
         leaf `claim(...)`, NOT a `derive(..., given=[])`. A premise-less factor
         is a normal grounding assertion (observation / given / definition), not
         a defect.
   - LKM source claim (FALLBACK) — no derivable factor (a `knowledge` claim with
     `source.has_reasoning == false`, or a `reasoning_chain` whose factors are all
     `premise_count == 0` — including the empty-shell case `source.factors == []`,
     a conclusion with zero factors): emit a leaf/source `claim(...)` with
     `provenance_source="lkm_no_chain"` and the preserved `lkm_id` (the result's
     `id`); do not invent premises, factors, or derives. Reach for `lkm_no_chain`
     only when you could not pull the source or it is genuinely chain-less —
     prefer pulling the paper and formalizing its claims (3b) over restating them
     as fresh local leaves.
   - Search lead — a `question` result, or any result with insufficient
     content/provenance: do not emit.
   - Make every claim self-contained (system/material, method, quantity, value,
     conditions) so it is judgeable true/false without the LKM payload.
   - Composite propositions: when an LKM payload is a composite claim (an AND/OR
     of several sub-assertions), decompose it into atomic part-claims with
     `decompose(whole, parts=[a, b, ...], formula=...)` (Tier 1, from
     `gaia.engine.lang`) / `gaia author decompose --whole <composite_claim_id>
     --parts a,b[,c] (--formula-template atom|and|or | --formula-expr "<expr>")`
     (Tier 2) rather than hand-splitting it into unrelated claims.
   - Supports: `derive(target, given=[U], rationale="...", label="...")` is
     directional (U supports target). Do not fabricate support.
       If two supports share a common factor, extract it as a shared-factor claim
       and route both through it (avoids double-counting in BP).
   - Contradictions: when you spot a candidate tension between two claims A and
     B, FIRST pre-mark it with `candidate_relation(claims=[A, B],
     pattern="contradict")` (Tier 1) / `gaia author candidate-relation --claims
     A,B --pattern contradict` (Tier 2). That records an INERT, unadjudicated
     marker (kind="scaffold", no belief effect) — the pattern token is
     `contradict` (NOT "contradiction") and `pattern="contradict"` requires
     exactly two claims. PROMOTE it to a live contradiction only once the tension
     is an *adjudicable scientific conflict*: materialize the scaffold with
     `materialize(scaffold, by=[contradict(A, B)])` / `gaia author materialize`
     (or author `contradict(A, B)` directly). Label it `<side_a>_vs_<side_b>` and
     let `rationale=` carry your warrant intent / the resolution you already have
     (no `metadata=` kwarg on `contradict`/`derive`/`equal`). Reserve
     open-problem framing — and the `gaia inquiry hypothesis add "<open problem>"
     --scope <ns>::<label>` route — for tensions that are GENUINELY unresolved,
     not for every promotion.
   - Priors: never pass a `prior=` kwarg on `claim(...)`; leaf priors are
     `register_prior(...)` records in `priors.py`.

5. MARK obligations for gaps you must discharge. When the survey exposes a gap
   that has to be closed — a missing prior, a weak/absent support, a structural
   hole, a focus weakness — record it as a synthetic obligation keyed by the QID
   it is about:
       gaia inquiry obligation add <target_qid> -c "<what must be shown>" \\
           [--kind prior_hole|structural_hole|support_weak|focus_weakness|other]
   Close it once discharged: `gaia inquiry obligation close <qid>` (the qid is
   printed by `gaia inquiry obligation add` / `list`). Marking obligations STEERS
   exploration: next turn the engine BOOSTS any frontier contact whose `ref` or
   `sources` match an open obligation's `target_qid` — OR that is one hop from it
   in the graph adjacency (so an obligation keyed on an authored CLAIM QID reaches
   the adjacent frontier contacts that feed that claim, not just a contact that
   names the claim directly). The pressed contact's `obligation_pressure` feature
   → 1.0 (a strong weighted term) and its `survey_brief` names the obligation it
   discharges. It is a strong nudge, not a hard gate — relevance/coverage still
   count, and nothing is starved when no obligation matches.

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


# EXPANSION.md §3.D/§3.E — the consolidate-task instructions. A consolidate turn
# emits a bridge worklist over ALREADY-surveyed nodes (no new pulls); the agent
# either authors a connecting edge OR ratifies the island as legitimately
# separate. The "ratify as separate" option is EQUAL-STATUS, never a failure path,
# and consolidation must NEVER pressure fabricating an unsound edge.
_CONSOLIDATE = """\
# Consolidation task — bridge or ratify the disconnected islands

Your map has fragmented: some surveyed regions are **disconnected islands**, not
wired to the seed core. This is a CONSOLIDATE turn (no new paper pulls): you work
entirely over the nodes you have ALREADY surveyed. The task's `bridge_worklist`
lists each island with a short brief of its member nodes.

> Integrity contract — LLM proposes, engine adjudicates (unchanged).
> You propose a connecting relation OR a ratification; the engine adjudicates the
> belief consequence of a bridge. You never decide what is true, and you NEVER
> fabricate a connection that is not scientifically sound.

## For EACH island in `bridge_worklist`, do ONE of:

(a) **Bridge it** — author the connecting relation that wires the island to your
    core reasoning, REFERENCING the already-materialized QIDs (do not restate
    them). Choose the relation the science actually warrants:
    - support: `gaia author derive --conclusion <core_qid> --given <island_qid>
      --rationale "<why it supports>"` (or the reverse direction);
    - dependency: `gaia author depends-on --conclusion <core_qid>
      --given <island_qid>` (a surveyed island node is a materialized target);
    - tension: pre-mark `candidate_relation(claims=[<core_qid>, <island_qid>],
      pattern="contradict")`, then promote with
      `materialize(scaffold, by=[contradict(<core_qid>, <island_qid>)])` only when
      it is an adjudicable scientific conflict (label `<a>_vs_<b>`, warrant in
      `rationale=`).
    The engine reports the belief consequence at the checkpoint.

(b) **Ratify it as separate** — an EQUAL-STATUS option, not a failure. If no
    scientifically sound connection exists (the island is a genuinely different
    domain), record it as a legitimately-separate region. Add it to your result
    manifest's `ratified` list with a ONE-LINE scientific rationale:
        {"member_qids": ["<island qid>", ...],
         "rationale": "<why these are legitimately disjoint from the core>"}
    The engine then EXCLUDES this island from the fragmentation count — a map of
    several ratified domains reads HEALTHY, not degraded. Ratification is
    PROVISIONAL: if a later turn surfaces evidence that could connect the island,
    the engine REOPENS it and it returns here with a "reconsider" note — at which
    point you either author the now-possible bridge or re-ratify with an updated
    rationale.

A worklist entry flagged `reopened` (with a `bridge_hint` QID) was previously
ratified; new evidence `<bridge_hint>` may now connect it — re-decide it against
the new evidence (bridge it, or re-ratify saying why the new node still doesn't
soundly connect).

**Never invent an unsound edge to make the map look connected.** A legitimate
ratification is a first-class, honest outcome. Bridge only what the science
warrants; ratify the rest.

## When you are done

1. Write the result manifest to the `result_path` named in this task:
       {"surveyed_qids": [<any nodes you authored/referenced>],
        "ratified": [{"member_qids": [...], "rationale": "..."}, ...]}
   `surveyed_qids` records nodes you authored/wired; `ratified` records the
   islands you judged legitimately separate. Either list may be empty.
2. Re-invoke the orchestrator to checkpoint:
       gaia-lkm-explore turn <pkg>
   It recompiles + infers, recomputes connectivity, reports the delta (components
   closed, orphans wired, ratifications recorded, any island REOPENED by new
   evidence), and returns to IDLE. You do NOT run compile/infer/round yourself.
"""


def build_consolidate_instructions() -> str:
    """Return the self-contained consolidate-task procedure (EXPANSION.md §3.D/§3.E).

    A consolidate turn's bridge worklist + the equal-status "ratify as separate"
    option (with a one-line scientific rationale), keeping every scientific-
    integrity rule. The LLM proposes a bridge OR a ratification; the engine
    adjudicates the bridge's belief consequence — and new evidence can always
    reopen a ratification, so a verdict is never silently frozen.
    """
    return _CONSOLIDATE


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
            "with `lkm_related` paper-contacts.\n\n"
            "(First time? `gaia-lkm-explore init <pkg>` needs an EXISTING Gaia "
            "package — scaffold one first with `gaia pkg scaffold --target <pkg> "
            "--name <name>-gaia`. Run every `gaia-lkm-explore` verb from the "
            "WORKSPACE ROOT with the package PATH as the argument — never from "
            "inside the package dir or with `.` as the path. From inside the "
            "package, `uv run` builds a fresh venv without gaia and you get a "
            "cryptic `Failed to spawn: gaia-lkm-explore / No such file or "
            "directory`.)\n"
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


__all__ = ["build_consolidate_instructions", "build_survey_instructions"]
