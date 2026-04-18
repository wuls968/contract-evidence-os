"""Structured connector registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ConnectorRecord:
    """Registered connector metadata and callable."""

    namespace: str
    handler: Callable[..., Any]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    healthy: bool = True


@dataclass
class ConnectorHub:
    """Register, validate, and invoke structured connectors."""

    connectors: dict[str, ConnectorRecord] = field(default_factory=dict)

    def register(
        self,
        namespace: str,
        handler: Callable[..., Any],
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> ConnectorRecord:
        if namespace in self.connectors:
            raise ValueError(f"connector namespace already registered: {namespace}")
        record = ConnectorRecord(namespace, handler, input_schema, output_schema)
        self.connectors[namespace] = record
        return record

    def health(self, namespace: str) -> bool:
        return self.connectors[namespace].healthy

    def invoke(self, namespace: str, **payload: Any) -> Any:
        record = self.connectors[namespace]
        return record.handler(**payload)

    def docs(self, namespace: str) -> dict[str, Any]:
        record = self.connectors[namespace]
        return {
            "namespace": namespace,
            "input_schema": record.input_schema,
            "output_schema": record.output_schema,
            "healthy": record.healthy,
        }
