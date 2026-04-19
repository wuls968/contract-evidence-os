"""Shared schema and serialization utilities."""

from __future__ import annotations

from dataclasses import MISSING, asdict, fields, is_dataclass
from datetime import UTC, datetime
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(tz=UTC)


class SchemaModel:
    """Small base class for typed models with validation and JSON helpers."""

    version: str

    def validate(self) -> None:
        """Run model-specific validation."""

        version = getattr(self, "version", "")
        if not isinstance(version, str) or not version:
            raise ValueError(f"{type(self).__name__} requires a non-empty version")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model into JSON-safe primitives."""

        if not is_dataclass(self):
            raise TypeError(f"{type(self).__name__} must be a dataclass")
        return {field.name: _serialize(getattr(self, field.name)) for field in fields(self)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Any:
        """Deserialize the model from a plain dictionary."""

        hints = get_type_hints(cls)
        values: dict[str, Any] = {}
        for field in fields(cls):
            if field.name in payload:
                values[field.name] = _deserialize(payload.get(field.name), hints.get(field.name, Any))
            elif field.default is not MISSING:
                values[field.name] = field.default
            elif field.default_factory is not MISSING:  # type: ignore[attr-defined]
                values[field.name] = field.default_factory()  # type: ignore[misc]
        return cls(**values)

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """Publish a lightweight JSON schema for the model."""

        hints = get_type_hints(cls)
        return {
            "title": cls.__name__,
            "type": "object",
            "properties": {
                field.name: _schema_for(hints.get(field.name, Any)) for field in fields(cls)
            },
            "required": [field.name for field in fields(cls)],
        }


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, SchemaModel):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _deserialize(value: Any, annotation: Any) -> Any:
    if value is None:
        return None

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (list, list[Any]):
        subtype = args[0] if args else Any
        return [_deserialize(item, subtype) for item in value]

    if origin in (dict, dict[Any, Any]):
        value_type = args[1] if len(args) > 1 else Any
        return {key: _deserialize(item, value_type) for key, item in value.items()}

    if origin in (Union, UnionType):
        non_none = [candidate for candidate in args if candidate is not type(None)]
        if len(non_none) == 1:
            return _deserialize(value, non_none[0])
        return value

    if annotation is datetime:
        return datetime.fromisoformat(value)

    if isinstance(annotation, type) and issubclass(annotation, SchemaModel):
        return annotation.from_dict(value)

    return value


def _schema_for(annotation: Any) -> dict[str, Any]:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is datetime:
        return {"type": "string", "format": "date-time"}
    if origin in (list, list[Any]):
        subtype = args[0] if args else Any
        return {"type": "array", "items": _schema_for(subtype)}
    if origin in (dict, dict[Any, Any]):
        return {"type": "object"}
    if origin in (Union, UnionType):
        non_none = [candidate for candidate in args if candidate is not type(None)]
        if len(non_none) == 1:
            schema = _schema_for(non_none[0])
            schema["nullable"] = True
            return schema
        return {"anyOf": [_schema_for(candidate) for candidate in non_none]}
    if isinstance(annotation, type) and issubclass(annotation, SchemaModel):
        return {"type": "object", "title": annotation.__name__}
    return {"type": "string"}
