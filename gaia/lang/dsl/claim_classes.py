"""Parameterized Claim class helpers for Gaia Lang v6."""

from __future__ import annotations

import re
from typing import Any, get_args, get_origin, get_type_hints

from gaia.lang.runtime import Knowledge


_RESERVED_KWARGS = {
    "background",
    "label",
    "metadata",
    "provenance",
    "rendered_content",
    "title",
}


def _annotation_name(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is not None:
        args = ", ".join(_annotation_name(arg) for arg in get_args(annotation))
        origin_name = getattr(origin, "__name__", str(origin))
        return f"{origin_name}[{args}]"
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


def _render_value(value: Any) -> str:
    if isinstance(value, Knowledge):
        return (
            value.rendered_content
            or value.title
            or value.content
            or value.label
            or "<knowledge>"
        )
    return str(value)


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_template(template: str, values: dict[str, Any]) -> str:
    rendered_values = {name: _render_value(value) for name, value in values.items()}
    return template.format_map(_SafeFormatDict(rendered_values))


def _default_template(cls: type) -> str:
    fields = ", ".join(f"{name}={{{name}}}" for name in _claim_fields(cls))
    class_name = getattr(cls, "__name__", "ParameterizedClaim")
    return f"{class_name}({fields})"


def _claim_fields(cls: type) -> dict[str, Any]:
    declared = getattr(cls, "__annotations__", {})
    hints = get_type_hints(cls)
    return {
        name: hints.get(name, annotation)
        for name, annotation in declared.items()
        if not name.startswith("_") and name not in _RESERVED_KWARGS
    }


def instantiate_claim_class(cls: type, **kwargs: Any) -> Knowledge:
    """Instantiate ``cls`` as a human-readable parameterized claim."""
    fields = _claim_fields(cls)
    field_values: dict[str, Any] = {}
    metadata = dict(getattr(cls, "metadata", {}) or {})
    metadata.update(dict(kwargs.pop("metadata", {}) or {}))

    title = kwargs.pop("title", getattr(cls, "title", None))
    label = kwargs.pop("label", None)
    background = kwargs.pop("background", None)
    provenance = kwargs.pop("provenance", None)
    rendered_content = kwargs.pop("rendered_content", None)

    unknown = set(kwargs) - set(fields)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise TypeError(f"{cls.__name__} got unexpected parameter(s): {names}")

    missing = [name for name in fields if name not in kwargs]
    if missing:
        names = ", ".join(missing)
        raise TypeError(f"{cls.__name__} missing required parameter(s): {names}")

    for name in fields:
        field_values[name] = kwargs[name]

    template = getattr(cls, "template", None) or _default_template(cls)
    rendered = rendered_content or _render_template(template, field_values)
    parameters = [
        {
            "name": name,
            "type": _annotation_name(fields[name]),
            "value": value,
        }
        for name, value in field_values.items()
    ]
    metadata.setdefault("claim_class", f"{cls.__module__}.{cls.__qualname__}")
    if getattr(cls, "kind", None):
        metadata.setdefault("kind", getattr(cls, "kind"))

    knowledge = Knowledge(
        content=rendered,
        type="claim",
        title=title,
        content_template=template,
        rendered_content=rendered,
        background=background or [],
        parameters=parameters,
        provenance=provenance or [],
        metadata=metadata,
    )
    if label is not None:
        knowledge.label = _normalize_label(label)
    return knowledge


def _normalize_label(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]", "_", label.strip().lower())
    if not normalized:
        return "_anon"
    if not (normalized[0].isalpha() or normalized[0] == "_"):
        normalized = f"_{normalized}"
    return normalized


class ParameterizedClaim:
    """Base class for v6 human-readable parameterized Claim classes.

    Subclasses are factories: calling ``MyClaim(...)`` returns a runtime
    ``Knowledge(type="claim")`` with canonical parameters and rendered text.
    """

    template: str

    def __new__(cls, **kwargs: Any):
        if cls is ParameterizedClaim:
            return super().__new__(cls)
        return instantiate_claim_class(cls, **kwargs)


def claim_class(cls: type | None = None, **options: Any):
    """Decorator form for defining a parameterized claim factory."""

    def decorate(target: type):
        for key, value in options.items():
            setattr(target, key, value)

        class DecoratedParameterizedClaim(target, ParameterizedClaim):  # type: ignore[misc, valid-type]
            pass

        DecoratedParameterizedClaim.__name__ = target.__name__
        DecoratedParameterizedClaim.__qualname__ = target.__qualname__
        DecoratedParameterizedClaim.__module__ = target.__module__
        DecoratedParameterizedClaim.__annotations__ = dict(
            getattr(target, "__annotations__", {})
        )
        return DecoratedParameterizedClaim

    if cls is None:
        return decorate
    return decorate(cls)
