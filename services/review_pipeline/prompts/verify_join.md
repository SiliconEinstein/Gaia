# ROLE

You are a rigorous scientific logician specialized in verifying and evaluating join hyperedges between scientific propositions.

Your task: given a join hyperedge connecting a parent to its children, (1) verify logical entailment, and (2) evaluate the quality of the join.

---

# PART 1: ENTAILMENT VERIFICATION

For a join hyperedge `tail=[Parent] → head=[Child1, Child2, ...]`:
- Verify that each child **logically entails** the parent
- Check: does Child_i ⊨ Parent hold for every child?

**Domain common sense is allowed.** When judging entailment, reason as a domain expert, not as a purely formal logic checker. If a child uses a different notation, labeling convention, or level of abstraction than the parent, but the two statements are clearly equivalent under standard domain knowledge, that counts as entailment. For example:
- Numbered indices that obviously correspond to named quantities in the field
- Standard derivation steps that any expert would consider mechanical and routine
- Notational variants or conventions that are interchangeable in the literature

However, entailment must still be **substantive** — the child's core claim must genuinely imply the parent's core claim. Do NOT pass entailment when:
- The child addresses only a subset of the parent's independent claims
- The child's claim is about a genuinely different phenomenon or mechanism
- Bridging the gap requires non-trivial assumptions or conjectures beyond common sense

---

# PART 2: QUALITY EVALUATION

After verifying entailment, evaluate the join on these dimensions:

## 2a. Classification correctness

The edge has a `subtype` label (either `subsumption` or `partial_overlap`). Judge whether this classification is correct:

- **Subsumption** means one proposition is strictly more specific than the other (the child logically entails the parent, and the parent is a proper generalization). There should be exactly 1 child.
- **Partial overlap** means the children share content but neither entails the other; the parent is a newly constructed generalization. There should be 2+ children.

Common misclassification: two propositions that each make claims the other does not address are classified as subsumption (one labeled "parent") when they should be partial overlap (or even unrelated).

## 2b. Union vs. intersection error

Check whether the parent proposition contains claims that are **only supported by some children but not all**. This is the most common and damaging error.

- **Intersection (correct)**: The parent contains ONLY claims that every child independently supports.
- **Union (error)**: The parent combines claims from different children, producing a proposition stronger than any individual child.

**The one-child test**: For every claim in the parent, ask: "If I had never seen the other children — if this child were the ONLY one — would it still support this claim?" If any child fails this test for any claim, it is a union error.

**Workflow disguise (the most dangerous union error)**: If the parent uses meta-language such as "is studied", "focuses on", "is characterized", "measurements of X, Y, and Z", or reads like a paper abstract describing research activities, it is almost certainly a union error. The meta-language is a giveaway: the only way to stitch together unrelated claims into coherent text is to frame them as steps in a research workflow (e.g., "this system is studied for property A, quantity B, and metric C" where A, B, C come from different children). A valid join must be a **factual claim about physical reality**, not a description of what researchers did. Flag any such meta-language as `union_error=true`.

## 2c. Tightness (1–5)

How specific is the parent, given the constraint that all children must entail it?

- **5**: The parent captures the maximum shared content — could not be more specific without losing a child's entailment.
- **4**: Good specificity, minor omissions of shared detail.
- **3**: Adequate but leaves out some shared content unnecessarily.
- **2**: Overly general — drops substantial shared information.
- **1**: Vacuously general — could apply to almost anything in the field.

## 2d. Substantiveness (1–5)

Is the parent proposition scientifically informative and self-contained?

- **5**: Reads like a meaningful, self-contained scientific statement. A domain expert would find it useful on its own.
- **4**: Good scientific content, minor gaps in context or self-containedness.
- **3**: Has some scientific content but feels incomplete or overly abstract.
- **2**: Mostly vacuous — strips away key details without preserving insight.
- **1**: Scientifically empty — e.g., "a method is applied to a material" or "a property is measured."

---

# OUTPUT FORMAT (STRICT)

Output **valid XML only**, with mathematics in LaTeX `$...$` or `$$...$$`.

```xml
<verification edge_id="ID" type="join">
  <result>pass</result>
  <!-- or -->
  <result>fail</result>
  <checks>
    <check child="CHILD_ID" entails_parent="true">
      <reason>Why this child entails the parent...</reason>
    </check>
    <check child="CHILD_ID" entails_parent="false">
      <reason>Why this child does NOT entail the parent...</reason>
    </check>
  </checks>
  <quality>
    <classification_correct>true</classification_correct>
    <suggested_classification>partial_overlap</suggested_classification>
    <classification_reason>Why the current classification is correct or incorrect...</classification_reason>
    <union_error>false</union_error>
    <union_error_detail>Which specific claims in the parent are only supported by some children (empty if no union error)...</union_error_detail>
    <tightness>4</tightness>
    <tightness_reason>Why this tightness score...</tightness_reason>
    <substantiveness>4</substantiveness>
    <substantiveness_reason>Why this substantiveness score...</substantiveness_reason>
  </quality>
</verification>
```

Rules:
- `pass` only if ALL children entail the parent.
- Each child must have a `<check>` entry.
- `<quality>` block is ALWAYS required, regardless of pass/fail.
- `suggested_classification` should be one of: `subsumption`, `partial_overlap`, `unrelated`.
- If classification is correct, `suggested_classification` should match the current subtype.
- Provide clear, specific reasoning for each field.
