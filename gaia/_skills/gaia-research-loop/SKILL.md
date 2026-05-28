---
name: gaia-research-loop
description: Run Gaia's agent-facing Explore -> Assess research loop through self-contained task envelopes.
---

# Gaia Research Loop

Use this when a user asks to run or continue a Gaia research loop.

1. Run `gaia-research-loop next <pkg> --json`.
2. Open the returned task envelope.
3. Follow the task's `instructions`.
4. If the task requires reasoning, use your own model.
5. Write candidate JSON matching `output_contract`.
6. Run the task's `submit_command`.
7. If validation fails, run `gaia-research-loop next <pkg> --json` and repair
   the same task using `repair_context`.
8. Repeat until `gaia-research-loop status <pkg>` or `gaia-research-loop gate`
   reports that the loop is done.

Do not hardcode query planning, focus synthesis, or assessment schemas. The task
envelope is the contract.
