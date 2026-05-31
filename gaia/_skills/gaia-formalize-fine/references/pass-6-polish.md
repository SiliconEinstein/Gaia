# Pass 6 — Polish for standalone readability

Load this file after Pass 5 is complete and its compile + check loop passes.
When this pass is done, run the inner loop a final time and load
`priors-analysis-render.md`.

**Prerequisite:** the knowledge graph is structurally correct (Pass 5 complete). Pass 6 ensures that every claim, rationale, and metadata entry is independently understandable without access to the original source.

### 6a. Claim self-containedness

Review every claim for standalone readability:

**Symbols must be self-explanatory.**
- Every mathematical symbol must have a brief explanation on its first appearance in that claim.
- Example: do not write "$\alpha \ll 1$"; write "the parameter $\alpha$ (ratio of XX to YY) is much less than 1".
- The physical meaning of subscripts / superscripts must be explicit.

**Abbreviations must be expanded.**
- Every abbreviation must be expanded on its first appearance in that claim.
- Example: do not write "XXX computes $\lambda$"; write "the such-and-such method (XXX) computes the coupling constant $\lambda$".
- Even if an abbreviation has been expanded in another claim, each claim is independent and must expand it again.

**No comparative assertions without reference.**
- Do not write "significantly larger than X" — the reader does not know what is being compared.
- Do not write "nearly exact agreement" — the reader does not know what it agrees with.
- Numerical comparisons must provide both values.

**Sufficient detail.**
- Can a reader understand what this claim says by reading only this one claim?
- Are conditions and applicable ranges clear?
- Do numerical values include units and error bars?

### 6b. Data formatting

- Tabular data should use markdown tables in claim content.
- Key numerical values from figures must be transcribed into the claim text (not just referenced).
- Trends described in prose should include specific data points.

### 6c. Rationale standalone readability

Review every relation's `rationale` text:

- The rationale should be a complete reasoning chain, not "see Section 3 of the paper."
- Specific numbers, method names, and conditions should be stated, not implied.
- Every `@label` reference should have enough surrounding context that a reader unfamiliar with the label can follow the argument.

### 6d. Figure and table references

Create artifact notes for every figure or table that materially supports authored content. Use
`figure(...)` for figures and `artifact(kind="table", ...)` for tables; both create ordinary
`note(...)` nodes with `metadata["gaia"]["artifact"]`.

```python
source_fig3 = figure(
    source="SourceKey",
    locator="Fig. 3",
    path="artifacts/figures/source_fig3.png",
    caption="Short caption with the figure number and key content.",
)

claim_from_figure = claim(
    "The measured trend increases monotonically across the reported range [@source_fig3].",
    background=[source_fig3],
)
```

1. **Coverage.** Check each module against the source for missing artifact anchors.
2. **Path validity.** Verify each file path exists in `artifacts/`.
3. **Caption accuracy.** Copy the figure caption from the source (abbreviated OK, but figure number and key content must be correct).
4. **Relation text.** Relations whose `rationale` uses figure data should cite the artifact label with `[@source_fig3]`.

### 6e. Complete citation metadata

During Passes 1-4, `references.json` entries were kept minimal (key + type + title). Now fill in complete metadata for all cited references:

- **author** — full author list (`[{"family": "...", "given": "..."}]`).
- **issued** — publication date (`{"date-parts": [[2020]]}`).
- **container-title** — journal / conference name.
- **volume**, **page**, **DOI** — where applicable.

Verify: every `[@key]` used in claims and rationales has a corresponding entry in `references.json`. Run `gaia build compile .` to catch any missing keys (strict `[@key]` form raises a compile error if the key is not found).

### 6f. Format consistency

- Metadata format should be consistent across all claims (same key names, same path conventions).
- Titles should follow a consistent naming style.
- Cross-module import patterns should be uniform.
