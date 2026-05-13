"""Gaia Lang v6 Knowledge class hierarchy."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from gaia.lang.runtime.param import UNBOUND

if TYPE_CHECKING:
    from gaia.lang.runtime.action import Action
    from gaia.lang.runtime.package import CollectedPackage

_current_package: ContextVar[CollectedPackage | None] = ContextVar("_current_package", default=None)


class _SafeFormatDict(dict[str, object]):
    """Return {key} for missing keys instead of raising KeyError."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


@dataclass
class Knowledge:
    """Base knowledge node. Plain text plus metadata."""

    content: str
    format: str = "markdown"
    type: str = "knowledge"
    title: str | None = None
    background: list[Knowledge] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    label: str | None = None
    strategy: Any | None = None
    _package: CollectedPackage | None = field(default=None, init=False, repr=False, compare=False)
    _source_module: str | None = field(default=None, init=False, repr=False, compare=False)
    _declaration_index: int | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Register the knowledge node with the active or inferred package."""
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg
            pkg._register_knowledge(self)

    def __hash__(self) -> int:
        """Return object-identity hash for mutable runtime nodes."""
        return id(self)


@dataclass(init=False, eq=False)
class Note(Knowledge):
    """Non-probabilistic contextual material. Does not enter BP."""

    def __init__(self, content: str, *, format: str = "markdown", **kwargs: Any) -> None:
        """Create a non-probabilistic note."""
        if "prior" in kwargs:
            raise TypeError("Note cannot have a prior.")
        super().__init__(content=content, type="note", format=format, **kwargs)


@dataclass(init=False, eq=False)
class Context(Note):
    """Deprecated compatibility alias for Note."""

    def __init__(self, content: str, *, format: str = "markdown", **kwargs: Any) -> None:
        """Create a deprecated context note alias."""
        if "prior" in kwargs:
            raise TypeError("Context cannot have a prior.")
        metadata = dict(kwargs.pop("metadata", {}) or {})
        metadata.setdefault("legacy_kind", "context")
        super().__init__(content=content, format=format, metadata=metadata, **kwargs)


@dataclass(init=False, eq=False)
class Setting(Note):
    """Deprecated compatibility alias for Note."""

    def __init__(self, content: str, *, format: str = "markdown", **kwargs: Any) -> None:
        """Create a deprecated setting note alias."""
        if "prior" in kwargs:
            raise TypeError("Setting cannot have a prior.")
        metadata = dict(kwargs.pop("metadata", {}) or {})
        metadata.setdefault("legacy_kind", "setting")
        super().__init__(content=content, format=format, metadata=metadata, **kwargs)


class ClaimKind(Enum):
    """Shape discriminator for the structured-content of a Claim (spec §4.2).

    GENERAL      — default; formula optional, no structural commitments
    PARAMETER    — asserts a Variable takes a specific value (Equals(var, const))
    QUANTIFIED   — top-level quantifier (Forall/Exists) in formula
    CAUSAL       — top-level Causes(...) predicate in formula

    NOT a "role" (hypothesis/prediction/observation-as-evidence) — those live
    on action graph nodes. Observation is an Observe action, not a Claim kind.
    NOT helper-claim metadata.
    """

    GENERAL = "general"
    PARAMETER = "parameter"
    QUANTIFIED = "quantified"
    CAUSAL = "causal"


def _validate_formula_and_kind(formula: Any, kind: ClaimKind) -> None:
    if formula is not None:
        from gaia.lang.formula.predicate import is_formula

        if not is_formula(formula):
            raise TypeError(f"formula must be a Formula or None, got {type(formula).__name__}")
    if not isinstance(kind, ClaimKind):
        raise TypeError(f"kind must be a ClaimKind member, got {type(kind).__name__}")


def _split_param_kwargs(
    kwargs: dict[str, Any],
    param_fields: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    param_values: dict[str, Any] = {}
    knowledge_kwargs: dict[str, Any] = {}
    for key, value in kwargs.items():
        if key in param_fields:
            param_values[key] = value
        else:
            knowledge_kwargs[key] = value
    return param_values, knowledge_kwargs


def _parameter_entries(
    param_fields: dict[str, Any],
    param_values: dict[str, Any],
) -> list[dict[str, Any]]:
    params = []
    for name, ann in param_fields.items():
        val = param_values.get(name, UNBOUND)
        stored_val = val.value if isinstance(val, Enum) else val
        params.append(
            {
                "name": name,
                "type": ann.__name__ if isinstance(ann, type) else str(ann),
                "value": stored_val,
            }
        )
    return params


def _render_templated_content(
    content: str | None,
    *,
    template: str,
    param_fields: dict[str, Any],
    param_values: dict[str, Any],
    knowledge_kwargs: dict[str, Any],
) -> str | None:
    if content is not None or not template or not param_fields:
        return content

    metadata = dict(knowledge_kwargs.get("metadata") or {})
    metadata["content_template"] = template
    knowledge_kwargs["metadata"] = metadata
    rendered_template = template
    render_values: dict[str, Any] = {}
    for name in param_fields:
        val = param_values.get(name, UNBOUND)
        if val is UNBOUND:
            continue
        if isinstance(val, Knowledge):
            ref = f"[@{val.label or '?'}]"
            render_values[name] = ref
            rendered_template = rendered_template.replace(f"[@{name}]", ref)
        elif isinstance(val, Enum):
            render_values[name] = val.value
        else:
            render_values[name] = val
    return rendered_template.format_map(_SafeFormatDict(render_values))


@dataclass(init=False, eq=False)
class Claim(Knowledge):
    """Proposition with prior. Participates in BP."""

    prior: float | None = None
    from_actions: list[Action] = field(default_factory=list)
    formula: Any = None
    kind: ClaimKind = ClaimKind.GENERAL
    _param_fields: ClassVar[dict[str, Any]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Collect subclass-specific parameter fields for templated claims."""
        super().__init_subclass__(**kwargs)
        base_fields = {
            "content",
            "format",
            "type",
            "title",
            "background",
            "parameters",
            "provenance",
            "metadata",
            "label",
            "strategy",
            "prior",
            "from_actions",
            "supported_by",
            "supports",
            "targets",
            "formula",
            "kind",
        }
        cls._param_fields = {
            name: ann
            for name, ann in getattr(cls, "__annotations__", {}).items()
            if name not in base_fields and not name.startswith("_")
        }

    def __bool__(self) -> bool:
        """Reject accidental use of Claim objects in Python truth tests."""
        raise TypeError(
            "Claim objects do not have Python truth values. Use claim(formula=...) "
            "with ClaimAtom/land/lor/lnot to build structured formula claims; "
            "legacy ~A, A & B, and A | B shortcuts still exist but emit "
            "DeprecationWarning."
        )

    def __invert__(self) -> Claim:
        """Create the deprecated propositional negation helper."""
        from gaia.lang.dsl.propositional import not_

        return not_(self)

    def __and__(self, other: Claim) -> Claim:
        """Create the deprecated propositional conjunction helper."""
        if not isinstance(other, Claim):
            return NotImplemented
        from gaia.lang.dsl.propositional import and_

        return and_(self, other)

    def __or__(self, other: Claim) -> Claim:
        """Create the deprecated propositional disjunction helper."""
        if not isinstance(other, Claim):
            return NotImplemented
        from gaia.lang.dsl.propositional import or_

        return or_(self, other)

    def __init__(
        self,
        content: str | None = None,
        *,
        prior: float | None = None,
        from_actions: list[Any] | None = None,
        formula: Any = None,
        kind: ClaimKind = ClaimKind.GENERAL,
        **kwargs: Any,
    ) -> None:
        """Create a probabilistic claim node."""
        _validate_formula_and_kind(formula, kind)
        param_fields = getattr(self.__class__, "_param_fields", {})
        param_values, knowledge_kwargs = _split_param_kwargs(kwargs, param_fields)
        params = _parameter_entries(param_fields, param_values)

        template = self.__class__.__doc__ or ""
        content = _render_templated_content(
            content,
            template=template,
            param_fields=param_fields,
            param_values=param_values,
            knowledge_kwargs=knowledge_kwargs,
        )

        for name, val in param_values.items():
            object.__setattr__(self, name, val)

        super().__init__(
            content=content or "",
            type="claim",
            parameters=params or knowledge_kwargs.pop("parameters", []),
            **knowledge_kwargs,
        )
        self.prior = prior
        self.from_actions = list(from_actions or [])
        self.formula = formula
        self.kind = kind


@dataclass(init=False, eq=False)
class Question(Knowledge):
    """Open inquiry. Does not enter BP."""

    targets: list[Claim] = field(default_factory=list)

    def __init__(self, content: str, **kwargs: Any) -> None:
        """Create a non-probabilistic question."""
        if "prior" in kwargs:
            raise TypeError("Question cannot have a prior.")
        targets = kwargs.pop("targets", [])
        super().__init__(content=content, type="question", **kwargs)
        self.targets = list(targets)
