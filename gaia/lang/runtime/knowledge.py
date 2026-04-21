"""Gaia Lang v6 Knowledge class hierarchy."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from gaia.lang.runtime.grounding import Grounding
from gaia.lang.runtime.param import UNBOUND

if TYPE_CHECKING:
    from gaia.lang.runtime.package import CollectedPackage

_current_package: ContextVar[CollectedPackage | None] = ContextVar("_current_package", default=None)


class _SafeFormatDict(dict):
    """Return {key} for missing keys instead of raising KeyError."""

    def __missing__(self, key):
        return f"{{{key}}}"


@dataclass
class Knowledge:
    """Base knowledge node. Plain text plus metadata."""

    content: str
    type: str = "knowledge"
    title: str | None = None
    background: list[Knowledge] = field(default_factory=list)
    parameters: list[dict] = field(default_factory=list)
    provenance: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    label: str | None = None
    strategy: Any | None = None
    _package: CollectedPackage | None = field(default=None, init=False, repr=False, compare=False)
    _source_module: str | None = field(default=None, init=False, repr=False, compare=False)
    _declaration_index: int | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
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
        return id(self)


@dataclass(init=False)
class Context(Knowledge):
    """Raw unformalized text. Does not enter BP."""

    def __init__(self, content: str, **kwargs):
        if "prior" in kwargs:
            raise TypeError("Context cannot have a prior.")
        super().__init__(content=content, type="context", **kwargs)


@dataclass(init=False)
class Setting(Knowledge):
    """Formalized background. No probability."""

    def __init__(self, content: str, **kwargs):
        if "prior" in kwargs:
            raise TypeError("Setting cannot have a prior.")
        super().__init__(content=content, type="setting", **kwargs)


@dataclass(init=False)
class Claim(Knowledge):
    """Proposition with prior. Participates in BP."""

    prior: float | None = None
    grounding: Grounding | None = None
    supports: list[Any] = field(default_factory=list)
    _param_fields: ClassVar[dict[str, Any]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        base_fields = {
            "content",
            "type",
            "title",
            "background",
            "parameters",
            "provenance",
            "metadata",
            "label",
            "strategy",
            "prior",
            "grounding",
            "supports",
            "targets",
        }
        cls._param_fields = {
            name: ann
            for name, ann in getattr(cls, "__annotations__", {}).items()
            if name not in base_fields and not name.startswith("_")
        }

    def __init__(
        self,
        content: str | None = None,
        *,
        prior: float | None = None,
        grounding: Grounding | None = None,
        supports: list[Any] | None = None,
        **kwargs,
    ):
        param_fields = getattr(self.__class__, "_param_fields", {})
        param_values: dict[str, Any] = {}
        knowledge_kwargs: dict[str, Any] = {}
        for key, value in kwargs.items():
            if key in param_fields:
                param_values[key] = value
            else:
                knowledge_kwargs[key] = value

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

        template = self.__class__.__doc__ or ""
        if content is None and template and param_fields:
            metadata = dict(knowledge_kwargs.get("metadata") or {})
            metadata["content_template"] = template
            knowledge_kwargs["metadata"] = metadata
            rendered_template = template
            render_values: dict[str, Any] = {}
            for name in param_fields:
                val = param_values.get(name, UNBOUND)
                if val is not UNBOUND:
                    if isinstance(val, Knowledge):
                        ref = f"[@{val.label or '?'}]"
                        render_values[name] = ref
                        rendered_template = rendered_template.replace(f"[@{name}]", ref)
                    elif isinstance(val, Enum):
                        render_values[name] = val.value
                    else:
                        render_values[name] = val
            content = rendered_template.format_map(_SafeFormatDict(render_values))

        for name, val in param_values.items():
            object.__setattr__(self, name, val)

        super().__init__(
            content=content or "",
            type="claim",
            parameters=params or knowledge_kwargs.pop("parameters", []),
            **knowledge_kwargs,
        )
        self.prior = prior
        self.grounding = grounding
        self.supports = list(supports or [])


@dataclass(init=False)
class Question(Knowledge):
    """Open inquiry. Does not enter BP."""

    targets: list[Claim] = field(default_factory=list)

    def __init__(self, content: str, **kwargs):
        if "prior" in kwargs:
            raise TypeError("Question cannot have a prior.")
        targets = kwargs.pop("targets", [])
        super().__init__(content=content, type="question", **kwargs)
        self.targets = list(targets)
