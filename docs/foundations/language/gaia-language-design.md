# Gaia Language Design

## Purpose

This document defines the language design of Gaia — a formal language for knowledge representation and epistemic inference based on plausible reasoning.

It is the top-level language blueprint. The V1/V2/V3 documents define specific layer implementations of this language:

- **V1** — FP language core (types, values, functions, expressions, modules)
- **V2** — Package metadata and dependency layer (`version`, `manifest`, `dependencies` on current main; future package-management extraction, registry, publish)
- **V3** — Probabilistic layer (prior, posterior, belief propagation)

For Gaia Language's system role, lifecycle stages, and layer boundaries, see
[gaia-language-spec.md](gaia-language-spec.md).

## Design Approach

**Layered language kernel.** Gaia follows the same architecture as Church (extending Scheme) and Pyro (extending Python): a deterministic host language with a probabilistic layer on top. Each version layer adds primitives to the kernel:

```
V1 kernel:    Knowledge, Action, Expr, Ref, Module   (FP: values, functions, composition, references, modules)
V2 extension: Package, Dependency, Registry           (package management: Cargo/Cabal)
V3 extension: Prior, Posterior, Dependency, Propagate  (probability: Church's sample/observe)
```

**Formality level.** Semi-formal — natural language + BNF + semantic rule tables.

**Primary user.** AI agents. The language prioritizes machine-parsability, unambiguous rules, and ease of automatic generation and validation.

**Abstract vs concrete syntax.** This document defines both:

- **Abstract syntax** — the language's legal structures, specified in layered BNF
- **Concrete syntax** — YAML serialization format. Since the primary user is AI agents, YAML is the concrete syntax directly. No custom parser is needed — `yaml.safe_load()` + schema validation replaces parsing entirely. This follows the same strategy as Church (reusing Scheme's parser) and Pyro (reusing Python's parser).

## Type System

### Design principles

- **Subtyping**: the type system is a tree with inheritance. Rules defined at any level apply to all subtypes.
- **Extensible**: new subtypes can be added without changing existing rules.
- **Knowledge as root type**: all objects in the language are knowledge.
- **Naming convention**: base types use short names (Claim, Action, Expr, Ref, Module). Subtypes carry the parent type name as a suffix (InferAction, ChainExpr, ReasoningModule).

### Type hierarchy

```
Knowledge                              (root type)
├── Claim                              (assertive knowledge — truth-apt)
│   ├── ...                            (future: Observation, Conjecture, Theorem...)
├── Question                           (interrogative knowledge — not truth-apt)
│   ├── ...
├── Setting                            (contextual knowledge — conditions, definitions)
│   ├── ...                            (future: Definition, Assumption, Environment...)
├── Action                             (procedural knowledge — single callable function)
│   ├── InferAction                    (NL reasoning — inherently probabilistic)
│   ├── ToolCallAction                 (executable code — deterministic given env)
│   └── ...                            (future: PythonCallAction, LeanProofAction...)
├── Expr                               (compositional knowledge — function composition)
│   ├── ChainExpr                      (linear pipeline: A => f => B => g => C)
│   └── ...                            (future: BranchExpr, DAGExpr...)
├── Ref                                (reference to external knowledge)
│   └── ...
└── Module                             (composite knowledge unit — organizational)
    ├── ReasoningModule                (produces claims through reasoning)
    ├── SettingModule                   (establishes context/definitions)
    ├── MotivationModule               (establishes why the work was undertaken)
    ├── FollowUpModule                 (open questions for future work)
    └── ...
```

### Base types

**Claim** — assertive, truth-apt knowledge. Statements, results, conclusions.

**Question** — interrogative knowledge. Not truth-apt (has no truth value). Inquiries, open problems.

**Setting** — contextual knowledge. Definitions, assumptions, execution environments, experimental conditions. Establishes the background under which reasoning is interpreted.

**Action** — procedural knowledge. Describes a single process, method, or tool. Functions in the language — can be "called" in expressions. Two subtypes:

- **InferAction**: natural language method description. Executed by AI agents reading and applying the described method. Inherently probabilistic — NL reasoning has error space.
- **ToolCallAction**: executable code in an external language (Python, Lean, etc.). Requires an execution environment (Setting). Deterministic given correct environment — uncertainty comes from the environment/inputs, not the code itself.

**Expr** — compositional knowledge. Represents the composition of multiple Actions into a reasoning structure. Unlike Action (single atomic function), Expr captures the structure of how knowledge objects are connected through reasoning steps.

- **ChainExpr**: linear pipeline connected by `=>`. The simplest form of composition.
- Future subtypes may include BranchExpr, DAGExpr, etc. for more complex reasoning structures.

**Ref** — a reference to knowledge declared in another module. Replaces the traditional `import` statement. Since Ref is a Knowledge type, imports are just declarations like any other knowledge object.

**Module** — a composite knowledge unit that groups declarations and exports. Modules have a type describing their purpose (ReasoningModule, SettingModule, etc.) rather than a separate "role" field.

### Key type distinctions

| Property | Claim | Question | Setting | Action | Expr | Ref | Module |
|----------|-------|----------|---------|--------|------|-----|--------|
| Truth-apt? | Yes | **No** | Yes | No | No | No | No |
| Participates in BP? | Yes | No | Yes | Via application | Via steps | Via dependency | Via exports |
| Can be "called"? | No | No | No | **Yes** | **Yes** | No | Deferred |
| Has internal structure? | No | No | No | No | **Yes** (steps) | No | **Yes** (declarations) |

### Subtyping rules

- Any rule defined for a parent type automatically applies to all subtypes.
- Example: "Claim participates in BP" → Observation (future subtype of Claim) also participates in BP.
- Adding a new subtype never requires updating existing rules.

## Unified Declaration

All knowledge objects are declared with a single unified form:

```
Type Name Params? ReturnType? Body Metadata?
```

The differences between knowledge types are expressed through the **Body**, not through separate declaration forms:

| Body type | Used by | Structure |
|-----------|---------|-----------|
| **ContentBody** | Claim, Question, Setting, Action | Text content (string) |
| **ChainBody** | ChainExpr | `Step => Step => Step` pipeline |
| **ModuleBody** | Module and subtypes | Declarations + Export (recursive) |
| **RefBody** | Ref | Target reference (module.name path) |

Examples:

```
claim drag_explains_falling := "Air resistance explains differential fall rates"

infer_action contrastive_analysis(env: setting, hyp: claim) -> claim :=
  "Contrast behavior under two different conditions to test the hypothesis"

chain_expr main_derivation := premise => contrastive_analysis(premise) => conclusion

ref premise := env_module.premise

reasoning_module main := <declarations...> export conclusion
```

### Immutability

Values are immutable and referentially transparent. A name always refers to the same content. There is no assignment or mutable state in the deterministic layer (V1).

### No private scope

**All knowledge is globally visible.** This is a fundamental difference from code languages:

| | Code (Rust) | Knowledge (Gaia) |
|---|---|---|
| Private | External cannot see | **Does not exist** — all knowledge is visible |
| Non-exported | Crate-internal | In LKM, visible, referenceable, but **does not participate in BP** |
| Exported | Globally available | Registered in LKM, **participates in BP** |

Knowledge is objective — there is no reason to hide intermediate reasoning steps. The only distinction is whether knowledge enters the probabilistic inference layer.

### Naming and identity

**Local (authoring):** human-readable names. No global ID needed.

```
-- Within a module: just the name
drag_explains_falling

-- Within a package, cross-module: module.name
reasoning.drag_explains_falling

-- Cross-package: package.module.name
physics.reasoning.drag_explains_falling
```

**Global (LKM):** identity is assigned at publish time by the registry (V2), not at creation time. Identity is content-driven, not ownership-driven.

**Identity and provenance are separated:**

| Aspect | What it is | Who manages it |
|--------|-----------|---------------|
| Local name | Human-readable variable name | Author |
| Global identity | Content-driven ID in LKM | Registry (V2) |
| Provenance | Which packages contributed this knowledge | Metadata |

This preserves objectivity: if two packages independently derive the same conclusion, the registry merges them into one global identity with two provenance records. Knowledge does not "belong to" any package.

## Action as Function

Action is a Knowledge type that has function semantics. Like Haskell, functions are values — an Action is a piece of knowledge that can also be "called."

### Functions are not pure

Unlike Haskell, Gaia functions are **not pure**. Natural language reasoning has inherent uncertainty — an AI agent executing an InferAction can make mistakes.

```
Haskell:  f(a, b) -> c     -- deterministic, always correct
Gaia:     f(a, b) -> c     -- probabilistic, may be wrong
```

Each function application carries its own prior/posterior (V3):

```
premise => contrastive_analysis(vacuum_setting, premise) (prior = 0.9) => conclusion
-- After BP: posterior may change based on evidence
```

### Lambda (anonymous single-parameter function)

Inline reasoning text in an expression — a one-off reasoning step. The lambda takes one implicit parameter from the pipe (`=>`), making it a **single-parameter anonymous function**:

```
premise => "Obviously follows from the definition" => conclusion
```

This is equivalent to `λpremise. "reasoning about premise" → conclusion`. The parameter is provided implicitly by the pipe operator.

## Expression (ChainExpr)

### Definition

A ChainExpr is a linear pipeline of knowledge and function applications, connected by `=>`:

```
premise => contrastive_analysis(vacuum_setting, premise) => conclusion
```

### Pipe operator `=>`

The `=>` operator is the **edge constructor** in the reasoning graph. It connects Steps, creating the factor graph structure:

```
[premise]  ——factor——  [conclusion]
 variable    contrastive    variable
  node       analysis        node
```

Syntax distinction:

```
=>   for chain flow (knowledge flows through reasoning steps)
->   for type signatures (input types to output types)
```

### Steps

A Step in a chain has three forms:

| Form | Role | Factor graph |
|------|------|-------------|
| **KnowledgeRef** | Reference to declared knowledge | Variable node |
| **Application** | Named function call | Factor node |
| **Lambda** | Anonymous single-param function | Anonymous factor node |

### Branching via multiple ChainExprs

Instead of explicit branch syntax, branching is expressed as multiple ChainExprs sharing knowledge references:

```
-- Two conclusions from the same premise
chain_expr branch_a := premise => analysis_a(premise) => conclusion_a
chain_expr branch_b := premise => analysis_b(premise) => conclusion_b

-- Synthesis of multiple results
chain_expr synthesis := conclusion_a => synthesize(conclusion_a, conclusion_b) => final
```

Future Expr subtypes (BranchExpr, DAGExpr) may provide explicit branching syntax.

### Design rules

| Rule | Decision |
|------|----------|
| Structure | Linear pipeline (ChainExpr) |
| Branching | Multiple ChainExprs sharing refs; future: BranchExpr |
| Loops | Not allowed (circular reasoning = logical error) |
| Per module | Multiple ChainExprs supported |
| Well-formedness | Flexible — no strict alternation rules |

## Module

### Definition

A Module is a Knowledge type (subtype of Knowledge) that groups declarations, manages references, and provides scoping. Its "type" describes its purpose (replacing the earlier "role" concept):

```
reasoning_module main:
  ref premise := env_module.premise
  ref vacuum_setting := env_module.vacuum_setting

  claim conclusion := "Air resistance explains differential fall rates"

  chain_expr derivation :=
    premise => contrastive_analysis(vacuum_setting, premise) => conclusion

  export conclusion
```

### Imports as Ref declarations

There is no separate import syntax. Imports are `ref` type declarations within a module:

```
ref premise := env_module.premise           -- reference to external knowledge
ref context := background_module.setting    -- another reference
```

### Exports and BP participation

Export determines whether knowledge enters the probabilistic inference layer:

- Exported knowledge → participates in BP (enters the factor graph)
- Non-exported knowledge → in LKM, visible, but does not participate in BP

### Module types

Modules have a type describing their purpose:

- `reasoning_module` — produces claims through reasoning chains
- `setting_module` — establishes shared context (definitions, environments, assumptions)
- `motivation_module` — establishes why the work was undertaken
- `follow_up_module` — establishes open questions for future work

Types replace separate "role" fields — the type system itself carries editorial intent.

## Package

Package is primarily a V2 (package management) concern. In V1, a package is a container of modules with exports:

```
package falling_bodies:
  modules = [motivation, env, reasoning, follow_up]
  export conclusion, follow_up_question
```

V2 adds: version, manifest, dependency declarations, cross-package resolution, registry/publish protocol, and global identity assignment at publish time. On current `main`, those metadata fields still live in `package.yaml`; a separate package-management manifest remains deferred.

## Abstract Syntax (Layered BNF)

### V1 — FP Core

```bnf
(* ====== Types ====== *)
Type           ::= 'knowledge'
                 | 'claim' | 'question' | 'setting'
                 | 'action' | 'infer_action' | 'toolcall_action'
                 | 'expr' | 'chain_expr'
                 | 'ref'
                 | 'module' | 'reasoning_module' | 'setting_module'
                             | 'motivation_module' | 'follow_up_module'

(* ====== Top-level ====== *)
Package        ::= Name Module+

(* ====== Module ====== *)
Module         ::= Type Name Knowledge* Export

(* ====== Knowledge (unified — everything is Knowledge) ====== *)
Knowledge      ::= Type Name Params? ReturnType? Body Metadata?

Params         ::= '(' Param (',' Param)* ')'
Param          ::= Name ':' Type
ReturnType     ::= '->' Type

Body           ::= ContentBody | ChainBody | ModuleBody | RefBody
ContentBody    ::= Content                       (* Claim, Question, Setting, Action *)
ChainBody      ::= Step ('=>' Step)*             (* ChainExpr *)
ModuleBody     ::= Knowledge* Export             (* Module — recursive *)
RefBody        ::= ModuleRef                     (* Ref — points to external knowledge *)

(* ====== Steps in a Chain ====== *)
Step           ::= KnowledgeRef | Application | Lambda
KnowledgeRef   ::= Name
Application    ::= Name '(' Arg (',' Arg)* ')'
Arg            ::= KnowledgeRef
Lambda         ::= Content                       (* single-param anonymous function *)

(* ====== Exports ====== *)
Export         ::= Name+

(* ====== Terminals ====== *)
Name           ::= Identifier
Content        ::= String
Metadata       ::= KeyValuePairs
ModuleRef      ::= Name ('.' Name)*
```

### V2 — Package Management Extension

```bnf
(* Extends Package *)
Package        ::= Name Version? Manifest? Dependency* Module+

Version        ::= Natural '.' Natural '.' Natural
Manifest       ::= Description? Author* License? Repository?

(* Dependencies *)
Dependency     ::= PackageRef VersionConstraint?
PackageRef     ::= Name
VersionConstraint ::= Operator Version
Operator       ::= '>=' | '>' | '=' | '<' | '<=' | '^' | '~'

(* Cross-package references — extends ModuleRef scope *)
ModuleRef      ::= Name ('.' Name)*
                   (* V1: module.name *)
                   (* V2: package.module.name *)

(* Publish & Identity *)
Publish        ::= PackageRef Registry?
Registry       ::= URL
GlobalIdentity ::= RegistryAssigned
Provenance     ::= Source+
Source          ::= PackageRef Version
```

### V3 — Probabilistic Layer Extension

```bnf
(* Extends Knowledge with prior *)
Knowledge      ::= Type Name Params? ReturnType? Body Metadata? ProbAnnot?
ProbAnnot      ::= '(' 'prior' '=' Float ')'

(* Extends Application and Lambda with prior *)
Application    ::= Name '(' Arg (',' Arg)* ')' ProbAnnot?
Lambda         ::= Content ProbAnnot?

(* Extends Arg with dependency type *)
Arg            ::= KnowledgeRef Dependency?
Dependency     ::= 'direct' | 'indirect'

(* Posterior — computed by BP, not authored *)
Posterior      ::= Float
```

## Concrete Syntax (YAML)

Since Gaia's primary user is AI agents, YAML is the concrete syntax. No custom parser is needed — `yaml.safe_load()` + Pydantic schema validation replaces traditional parsing.

### File organization

Each package is a directory. Each module is a YAML file. The package manifest is `package.yaml`:

```
falling_bodies/              # package directory
├── package.yaml             # package metadata + module list
├── motivation.yaml          # module
├── env.yaml                 # module
├── reasoning.yaml           # module
└── follow_up.yaml           # module
```

### Package manifest (`package.yaml`)

```yaml
# V1
name: falling_bodies
modules:
  - motivation
  - env
  - reasoning
  - follow_up
export:
  - conclusion
  - follow_up_question

# V2 additions
version: 1.0.0
manifest:
  description: "Analysis of falling bodies in vacuum vs air"
  authors: ["Galileo"]
  license: "CC-BY-4.0"
dependencies:
  - package: physics_base
    version: ">=1.0.0"
```

### Module file (`reasoning.yaml`)

```yaml
type: reasoning_module
name: reasoning

declarations:
  # Ref — reference to external knowledge
  - type: ref
    name: premise
    target: env.premise

  - type: ref
    name: vacuum_setting
    target: env.vacuum_setting

  # Claim
  - type: claim
    name: conclusion
    content: "Air resistance, not mass, explains differential fall rates"
    prior: 0.5                    # V3

  # Action
  - type: infer_action
    name: contrastive_analysis
    params:
      - name: env
        type: setting
      - name: hyp
        type: claim
    return_type: claim
    content: "Contrast behavior under two different conditions to test the hypothesis"
    prior: 0.9                    # V3

  # ChainExpr
  - type: chain_expr
    name: main_derivation
    steps:
      - step: 1
        ref: premise
      - step: 2
        apply: contrastive_analysis
        args:
          - ref: premise
            dependency: direct    # V3
          - ref: vacuum_setting
            dependency: indirect  # V3
        prior: 0.85              # V3
      - step: 3
        ref: conclusion

export:
  - conclusion
```

### Step YAML forms

```yaml
steps:
  # KnowledgeRef — reference to declared knowledge
  - step: 1
    ref: premise

  # Application — call an action
  - step: 2
    apply: contrastive_analysis
    args:
      - ref: premise
        dependency: direct        # V3
    prior: 0.85                   # V3

  # Lambda — anonymous single-parameter function
  - step: 3
    lambda: "Obviously follows from the definition"
    prior: 0.95                   # V3
```

### Abstract-to-YAML mapping

| Abstract Syntax | YAML representation |
|----------------|---------------------|
| `Type Name Body` | `type: xxx`, `name: xxx`, `content/steps/target/declarations: ...` |
| `KnowledgeRef` | `ref: name` |
| `Application` | `apply: name`, `args: [...]` |
| `Lambda` | `lambda: "text"` |
| `ProbAnnot` | `prior: float` |
| `Dependency` | `dependency: direct/indirect` |
| `RefBody` | `target: module.name` |
| `Params` | `params: [{name: x, type: y}, ...]` |
| `ReturnType` | `return_type: type` |
| `Export` | `export: [name, ...]` |

## Probabilistic Layer (V3)

### Unified probabilistic interface

**One pair of primitives — (prior, posterior) — applies to all language elements:**

| Language element | Prior | Posterior | Factor graph role |
|-----------------|-------|-----------|------------------|
| Knowledge (Claim, Setting) | Initial belief | Belief after BP | Variable node |
| Function application | Initial reliability | Reliability after BP | Factor node |
| ToolCallAction application | ~= 1.0 (deterministic) | ~= 1.0 | Near-transparent factor |

### Dependency type as conditioning

Dependency type (direct/indirect) is Gaia's analog of `observe` in probabilistic PLs. It is specified at the point of **use** (in Application args), not at the point of declaration (Ref):

- `direct` — creates a BP edge. If the premise is wrong, the conclusion is almost certainly wrong too.
- `indirect` — folded into prior. Contextual reference, conclusion can stand on its own.

The same Ref can be used with different dependency types in different contexts:

```yaml
# Same ref, different dependency in different chains
- type: chain_expr
  name: main_argument
  steps:
    - ref: premise
    - apply: detailed_analysis
      args:
        - ref: premise
          dependency: direct       # load-bearing here

- type: chain_expr
  name: side_note
  steps:
    - ref: premise
    - lambda: "tangentially related"
      # premise is just context here, not load-bearing
    - ref: observation
```

### BP as posterior inference

Belief propagation computes posteriors from priors + graph structure:

```
priors (input) -> BP on factor graph -> posteriors (output)
```

The factor graph is derived from the ChainExpr structure:

```
[premise]  --f(prior=0.9)--  [intermediate]  --g(prior=0.85)--  [conclusion]
   |                              |                                  |
 variable                      variable                           variable
(prior/posterior)            (prior/posterior)                  (prior/posterior)
```

## Version Layers Summary

| Layer | What it adds | PL analogy |
|-------|-------------|------------|
| **V1 -- FP Core** | Knowledge types, Action, Expr, Ref, Module, unified Knowledge | Haskell values, functions, composition, modules |
| **V2 -- Package Management** | Version, manifest, dependency resolution, registry, publish, global identity | Cargo, Cabal, npm |
| **V3 -- Probabilistic Layer** | Prior, posterior, dependency type (direct/indirect), BP | Church's flip/observe, Pyro's sample/observe |
| **Future** | Action type signatures, Module-as-callable-value, dependent types, formal verification | Lean, OCaml functors, Coq |

## Decided Questions

The following questions have been resolved:

1. **Abstract vs concrete syntax separation?** -> Yes. Abstract = BNF, concrete = YAML. No custom parser needed.
2. **Declaration unified or split?** -> Unified. One Knowledge form, Body distinguishes types.
3. **Module role or type?** -> Type. Module is a Knowledge type (ReasoningModule, SettingModule, etc.).
4. **Expression: structural element or type?** -> Type. Expr is a Knowledge base type, ChainExpr is a subtype of Expr under Action's sibling.
5. **Import: separate syntax or Ref type?** -> Ref type. Imports are `ref` declarations, not a separate syntactic construct.
6. **Lambda: traditional or pipe-implicit?** -> Pipe-implicit single-parameter anonymous function.
7. **Strong/weak: on Ref or on usage?** -> On usage. `dependency: direct/indirect` annotated at the point of use (in Application args).
8. **Strong/weak naming?** -> `direct` / `indirect`. More descriptive than strong/weak.
9. **Subtype naming convention?** -> Subtypes carry parent type as suffix (InferAction, ChainExpr, ReasoningModule).
10. **V1/V2/V3 BNF: unified or layered?** -> Layered. V1 defines base, V2/V3 extend productions.

## Open Design Questions

The following topics are identified for further discussion:

1. **Package as Knowledge type** — should Package be in the type tree? (deferred)
2. **Contradiction/Retraction modeling** — how to express conflict and retraction relationships between knowledge objects (deferred)
3. **Module-as-callable-value** — can a Module be "called" like an Action (imports -> exports)? (deferred)
4. **Well-formedness rules** — precise conditions for valid expressions, modules, packages
5. **Identity resolution algorithm** — how the registry merges equivalent knowledge from different packages (V2)
6. **BP on fine-grained factor graph** — implications of per-function-application factors vs per-module factors (V3)
7. **Action type signatures** — formal input/output type constraints for future type checking
8. **Scoping rules** — precise definition of visibility and reference resolution
9. **Interaction between InferAction and ToolCallAction** — how tool results feed back into NL reasoning chains
