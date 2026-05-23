# What Is Gaia?

> **Status:** Current canonical

## The Problem

Scientific knowledge lives in millions of papers. Each paper makes claims that depend on claims from other papers. When a new experiment contradicts an old result, which downstream conclusions should we still trust? Which ones need to be revised?

Today, no system tracks this. Scientists do it in their heads, in literature reviews, in conversations. The web of dependencies is too large and too tangled for any person to hold. Important contradictions go unnoticed. Outdated conclusions persist because nobody re-checked what they were built on.

## What Gaia Does

Gaia represents scientific knowledge as a structured graph and computes how trust flows through it. Each claim, each experimental setup, each reasoning step is a node or a link. Every claim carries a posterior between 0 and 1 representing how much we should trust it given the evidence currently in the system.

When authors run inference after adding new evidence — a package update, a new experiment, a contradiction — Gaia recomputes beliefs for the local package and, when requested, installed dependency graphs. Claims that lose support drop in credibility; claims that gain new evidence rise. Global corpus-wide recomputation belongs to the registry / LKM layer, not to a hidden automatic step in the local CLI.

## How It Works

Authors (or AI agents) write **knowledge packages** — small structured descriptions of a paper's claims, settings, and reasoning chains. The primary path is **authoring the Python DSL (`gaia.engine.lang`) directly**; the `gaia` command-line toolchain compiles, infers, and (optionally) helps author:

1. `gaia build init <name>-gaia` scaffolds a package.
2. `gaia sdk` writes the SDK reference + a one-page `CHEATSHEET.md`; the author then **writes `claim(...)`, `note(...)`, `derive(...)`, `infer(...)`, relation verbs (`contradict`, `equal`, `exclusive`), and propositional formulas directly in Python**. (The `gaia author` CLI is an optional convenience that does the same writes for you.)
3. `gaia build compile` lowers the DSL into Gaia IR (`Knowledge / Operator / Strategy / Compose` records).
4. `gaia run infer` lowers the IR into a factor graph and runs belief propagation locally.
5. `gaia pkg register` checks the release artifacts and prepares or writes git-backed registry metadata, where downstream packages can depend on exported claims.

Knowledge extraction itself is **author-side or agent-side work**, not an automated pipeline inside Gaia. Gaia's contribution is the **executable contract** (compile, validate, infer, gate, register) that turns those declarations into a graph whose beliefs are reproducible and machine-checkable.

## What Gaia Is NOT

- **Not a general-purpose search engine.** Retrieval adapters such as `gaia search lkm`
  can bring candidate papers or packages into the workflow, but Gaia's core job is
  reasoning about structured claims, not ranking arbitrary literature results.
- **Not a chatbot.** It does not generate text or answer questions in natural language.
- **Not a citation manager.** It does not track who cited whom -- it tracks which claims depend on which evidence and how much each claim should be trusted.

Gaia is a **reasoning engine for scientific knowledge**, with a Python authoring DSL on the input side and belief propagation on the output side.

## Key Concepts

- **Knowledge** -- A package record. `claim(...)` records scientific propositions
  that can carry beliefs; `note(...)` and `question(...)` provide context and
  inquiry structure without participating directly in BP.
- **Package** -- A container of knowledge from one paper or one line of reasoning. Like a commit in version control, it represents a coherent batch of new knowledge entering the system.
- **Factor** -- A reasoning link that connects claims. "These three observations support this conclusion" is a factor. "These two predictions contradict each other" is also a factor.
- **Belief** -- A number between 0 and 1 representing how much the system trusts a claim, computed from all the evidence in the graph. Not a vote, not a frequency -- a logical consequence of the evidence structure.
- **Belief propagation** -- The algorithm that computes beliefs. It sends messages along every link in the graph until all the trust scores are mutually consistent.
