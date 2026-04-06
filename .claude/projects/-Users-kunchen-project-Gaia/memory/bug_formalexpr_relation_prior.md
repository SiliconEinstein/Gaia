---
name: FormalExpr relation conclusion prior bug
description: FormalExpr internal relation operator conclusions get π=0.5 instead of 1-ε, causing dead-end constraint vanishing in elimination/case_analysis
type: project
---

FormalExpr expand path in `gaia/bp/lowering.py:232-237` uses `_ensure_claim_var` (default π=0.5) for ALL operator conclusions, including relation operators. Top-level operators (line 81-106) correctly distinguish relation vs directed, but FormalExpr path does not.

**Why:** This causes dead-end relation conclusions (Eq, Contra in elimination; Eq in case_analysis) to lose their constraint — the exact bug #340 describes.

**How to apply:** Fix by adding relation-type prior logic to the FormalExpr expand path. The prior should be 1-ε for relation operator conclusions, 0.5 for directed operator conclusions, matching the top-level operator path.

**Files:** `gaia/bp/lowering.py` lines 232-237 (FormalExpr expand), line 126-131 (`_ensure_claim_var`).
