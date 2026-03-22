from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SchemaValidationError(ValueError):
    pass


class SchemaValidator:
    def __init__(self, schema_dir: Path) -> None:
        self.schema_dir = schema_dir
        self.schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in schema_dir.glob("*.json")
        }

    def validate(self, schema_name: str, data: Any) -> None:
        schema = self.schemas[schema_name]
        self._validate_node(data, schema, "$", schema)

    def _validate_node(self, data: Any, schema: dict[str, Any], path: str, root_schema: dict[str, Any]) -> None:
        ref = schema.get("$ref")
        if ref:
            target = self._resolve_ref(root_schema, ref)
            self._validate_node(data, target, path, root_schema)
            return

        # Handle combination keywords: anyOf, oneOf, allOf
        if "anyOf" in schema:
            self._validate_any_of(data, schema["anyOf"], path, root_schema)
            return
        if "oneOf" in schema:
            self._validate_one_of(data, schema["oneOf"], path, root_schema)
            return
        if "allOf" in schema:
            self._validate_all_of(data, schema["allOf"], path, root_schema)
            return

        schema_type = schema.get("type")
        if schema_type == "object":
            self._validate_object(data, schema, path, root_schema)
            return
        if schema_type == "array":
            self._validate_array(data, schema, path, root_schema)
            return
        if schema_type == "string":
            self._validate_string(data, schema, path)
            return
        if schema_type == "integer":
            self._validate_integer(data, schema, path)
            return
        if schema_type == "number":
            self._validate_number(data, schema, path)
            return
        if schema_type == "boolean":
            if not isinstance(data, bool):
                raise SchemaValidationError(f"{path}: expected boolean")
            return

    def _validate_object(self, data: Any, schema: dict[str, Any], path: str, root_schema: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise SchemaValidationError(f"{path}: expected object")
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                raise SchemaValidationError(f"{path}: missing required field '{key}'")
        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties", {}).keys())
            for key in data:
                if key not in allowed:
                    raise SchemaValidationError(f"{path}: unexpected field '{key}'")
        for key, value in data.items():
            if key in schema.get("properties", {}):
                self._validate_node(value, schema["properties"][key], f"{path}.{key}", root_schema)

    def _validate_array(self, data: Any, schema: dict[str, Any], path: str, root_schema: dict[str, Any]) -> None:
        if not isinstance(data, list):
            raise SchemaValidationError(f"{path}: expected array")
        min_items = schema.get("minItems")
        if min_items is not None and len(data) < min_items:
            raise SchemaValidationError(f"{path}: expected at least {min_items} items")
        if schema.get("uniqueItems"):
            normalized = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in data]
            if len(set(normalized)) != len(normalized):
                raise SchemaValidationError(f"{path}: expected unique items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(data):
                self._validate_node(item, item_schema, f"{path}[{index}]", root_schema)

    def _validate_string(self, data: Any, schema: dict[str, Any], path: str) -> None:
        if not isinstance(data, str):
            raise SchemaValidationError(f"{path}: expected string")
        min_length = schema.get("minLength")
        if min_length is not None and len(data) < min_length:
            raise SchemaValidationError(f"{path}: expected string length >= {min_length}")
        enum = schema.get("enum")
        if enum is not None and data not in enum:
            raise SchemaValidationError(f"{path}: value '{data}' not in enum")

    def _validate_integer(self, data: Any, schema: dict[str, Any], path: str) -> None:
        if isinstance(data, bool) or not isinstance(data, int):
            raise SchemaValidationError(f"{path}: expected integer")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and data < minimum:
            raise SchemaValidationError(f"{path}: expected integer >= {minimum}")
        if maximum is not None and data > maximum:
            raise SchemaValidationError(f"{path}: expected integer <= {maximum}")

    def _validate_number(self, data: Any, schema: dict[str, Any], path: str) -> None:
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            raise SchemaValidationError(f"{path}: expected number")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and data < minimum:
            raise SchemaValidationError(f"{path}: expected number >= {minimum}")
        if maximum is not None and data > maximum:
            raise SchemaValidationError(f"{path}: expected number <= {maximum}")

    def _validate_any_of(self, data: Any, sub_schemas: list[dict[str, Any]], path: str, root_schema: dict[str, Any]) -> None:
        """At least one sub-schema must validate."""
        errors: list[str] = []
        for i, sub in enumerate(sub_schemas):
            try:
                self._validate_node(data, sub, f"{path}(anyOf[{i}])", root_schema)
                return  # first match is enough
            except SchemaValidationError as e:
                errors.append(str(e))
        raise SchemaValidationError(f"{path}: data does not match any of the anyOf schemas: {'; '.join(errors)}")

    def _validate_one_of(self, data: Any, sub_schemas: list[dict[str, Any]], path: str, root_schema: dict[str, Any]) -> None:
        """Exactly one sub-schema must validate."""
        match_count = 0
        last_errors: list[str] = []
        for i, sub in enumerate(sub_schemas):
            try:
                self._validate_node(data, sub, f"{path}(oneOf[{i}])", root_schema)
                match_count += 1
            except SchemaValidationError as e:
                last_errors.append(str(e))
        if match_count == 0:
            raise SchemaValidationError(f"{path}: data does not match any of the oneOf schemas: {'; '.join(last_errors)}")
        if match_count > 1:
            raise SchemaValidationError(f"{path}: data matches {match_count} schemas but oneOf requires exactly 1")

    def _validate_all_of(self, data: Any, sub_schemas: list[dict[str, Any]], path: str, root_schema: dict[str, Any]) -> None:
        """All sub-schemas must validate."""
        for i, sub in enumerate(sub_schemas):
            try:
                self._validate_node(data, sub, f"{path}(allOf[{i}])", root_schema)
            except SchemaValidationError as e:
                raise SchemaValidationError(f"{path}: allOf[{i}] failed: {e}") from e

    def _resolve_ref(self, schema: dict[str, Any], ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise SchemaValidationError(f"Unsupported ref: {ref}")
        node: Any = schema
        for token in ref[2:].split("/"):
            node = node[token]
        if not isinstance(node, dict):
            raise SchemaValidationError(f"Ref does not resolve to object schema: {ref}")
        return node
