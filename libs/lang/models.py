"""Gaia DSL Pydantic models — the type system as Python classes."""

from __future__ import annotations

from pydantic import BaseModel, Field, PrivateAttr


# ── Terminals ──────────────────────────────────────────────


class Param(BaseModel):
    name: str
    type: str


class Arg(BaseModel):
    ref: str
    dependency: str | None = None  # "direct" | "indirect" (V3)


class Manifest(BaseModel):
    description: str | None = None
    authors: list[str] = Field(default_factory=list)
    license: str | None = None


# ── Steps (in a ChainExpr) ────────────────────────────────


class StepRef(BaseModel):
    step: int
    ref: str


class StepApply(BaseModel):
    step: int
    apply: str
    args: list[Arg] = Field(default_factory=list)
    prior: float | None = None


class StepLambda(BaseModel):
    step: int
    lambda_: str = Field(alias="lambda")
    prior: float | None = None

    model_config = {"populate_by_name": True}


Step = StepRef | StepApply | StepLambda


# ── Declarations (unified — everything is Knowledge) ──────


class Declaration(BaseModel):
    """Base for all declarations. Subclasses set type as a literal."""

    type: str
    name: str
    metadata: dict | None = None
    prior: float | None = None


class Claim(Declaration):
    type: str = "claim"
    content: str = ""
    belief: float | None = None  # posterior after BP


class Question(Declaration):
    type: str = "question"
    content: str = ""


class Setting(Declaration):
    type: str = "setting"
    content: str = ""
    belief: float | None = None  # posterior after BP


class Relation(Declaration):
    """Base for logical relations between knowledge objects."""

    between: list[str] = Field(default_factory=list)
    content: str = ""
    belief: float | None = None


class Contradiction(Relation):
    type: str = "contradiction"


class Equivalence(Relation):
    type: str = "equivalence"


class Action(Declaration):
    """Base for executable actions (InferAction, ToolCallAction)."""

    params: list[Param] = Field(default_factory=list)
    return_type: str | None = None
    content: str = ""


class InferAction(Action):
    type: str = "infer_action"


class ToolCallAction(Action):
    type: str = "toolcall_action"
    tool: str | None = None


class RetractAction(Action):
    type: str = "retract_action"
    target: str = ""
    reason: str = ""  # ref to a Contradiction Relation


class Expr(Declaration):
    """Base for compound expressions (ChainExpr, future BranchExpr/DAGExpr)."""

    pass


class ChainExpr(Expr):
    type: str = "chain_expr"
    steps: list[Step] = Field(default_factory=list)
    edge_type: str | None = None  # "deduction" | "retraction" | "contradiction"


class Ref(Declaration):
    type: str = "ref"
    target: str = ""
    _resolved: Declaration | None = PrivateAttr(default=None)  # populated by resolver


# ── Module ────────────────────────────────────────────────

DECLARATION_TYPE_MAP: dict[str, type[Declaration]] = {
    "claim": Claim,
    "question": Question,
    "setting": Setting,
    "contradiction": Contradiction,
    "equivalence": Equivalence,
    "infer_action": InferAction,
    "toolcall_action": ToolCallAction,
    "retract_action": RetractAction,
    "chain_expr": ChainExpr,
    "ref": Ref,
}


class Module(BaseModel):
    type: str  # reasoning_module, setting_module, etc.
    name: str
    declarations: list[Declaration] = Field(default_factory=list)
    export: list[str] = Field(default_factory=list)


# ── Package ───────────────────────────────────────────────


class Dependency(BaseModel):
    package: str
    version: str | None = None


class Package(BaseModel):
    name: str
    version: str | None = None
    manifest: Manifest | None = None
    dependencies: list[Dependency] = Field(default_factory=list)
    modules_list: list[str] = Field(default_factory=list, alias="modules")
    export: list[str] = Field(default_factory=list)
    # Populated after loading module files:
    loaded_modules: list[Module] = Field(default_factory=list, exclude=True)
    _index: dict[str, Declaration] = PrivateAttr(default_factory=dict)  # populated by resolver

    model_config = {"populate_by_name": True}
