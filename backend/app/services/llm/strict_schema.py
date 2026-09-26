"""Chuyển schema Pydantic sang dạng JSON schema strict (Groq json_schema strict, Gemini response_json_schema)."""

from typing import Any

from pydantic import BaseModel


def to_strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema của Pydantic → inline $ref, mọi object additionalProperties=false + required đủ."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def strictify(node: Any) -> Any:
        if isinstance(node, list):
            return [strictify(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return strictify(definitions[node["$ref"].removeprefix("#/$defs/")])
        node = {key: strictify(value) for key, value in node.items()}
        if node.get("type") == "object":
            node["additionalProperties"] = False
            node["required"] = list(node.get("properties", {}))
        return node

    return strictify(schema)
