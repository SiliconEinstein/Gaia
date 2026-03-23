# What Is Gaia?

> **Status:** Current canonical

## The Problem

Scientific knowledge lives in millions of papers. Each paper makes claims that depend on claims from other papers. When a new experiment contradicts an old result, which downstream conclusions should we still trust? Which ones need to be revised?

Today, no system tracks this. Scientists do it in their heads, in literature reviews, in conversations. The web of dependencies is too large and too tangled for any person to hold. Important contradictions go unnoticed. Outdated conclusions persist because nobody re-checked what they were built on.

## What Gaia Does

Gaia reads scientific papers and extracts their knowledge as a structured graph. Each claim, each experimental setup, each reasoning step becomes a node or link in the graph. Every claim carries a number between 0 and 1 representing how much we should trust it, given all the evidence in the system.

When new evidence arrives -- a new paper, a new experiment, a contradiction -- Gaia automatically recalculates trust across the entire graph. Claims that were well-supported might drop in credibility. Claims that gain new evidence rise. The whole graph stays internally consistent without anyone having to manually trace every dependency.

## How It Works

Authors (or AI agents) write knowledge packages -- structured descriptions of a paper's claims, experimental settings, and reasoning chains. Gaia compiles each package into a factor graph, a mathematical structure that encodes how claims support or contradict each other. It then runs belief propagation, an algorithm that passes messages between nodes until the graph reaches a stable set of beliefs. When a new package enters the system, beliefs update automatically across every connected claim.

## What Gaia Is NOT

- **Not a search engine.** It does not find papers -- it reasons about what they say.
- **Not a chatbot.** It does not generate text or answer questions in natural language.
- **Not a citation manager.** It does not track who cited whom -- it tracks which claims depend on which evidence and how much each claim should be trusted.

Gaia is a **reasoning engine for scientific knowledge**.

## Key Concepts

- **Knowledge** -- A single proposition: a claim, an experimental setup, an observation, or a question. Each one carries a trust score (its "belief").
- **Package** -- A container of knowledge from one paper or one line of reasoning. Like a commit in version control, it represents a coherent batch of new knowledge entering the system.
- **Factor** -- A reasoning link that connects claims. "These three observations support this conclusion" is a factor. "These two predictions contradict each other" is also a factor.
- **Belief** -- A number between 0 and 1 representing how much the system trusts a claim, computed from all the evidence in the graph. Not a vote, not a frequency -- a logical consequence of the evidence structure.
- **Belief propagation** -- The algorithm that computes beliefs. It sends messages along every link in the graph until all the trust scores are mutually consistent.
