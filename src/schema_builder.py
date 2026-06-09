"""JSON schema builder matching Apple's fm schema command."""

import json


class SchemaProperty:
    def __init__(self, name: str, prop_type: str, description: str = None, is_array: bool = False, is_optional: bool = False, nested_schema: dict = None):
        self.name = name
        self.prop_type = prop_type
        self.description = description
        self.is_array = is_array
        self.is_optional = is_optional
        self.nested_schema = nested_schema

    def to_schema(self) -> dict:
        type_map = {
            "string": {"type": "string"},
            "integer": {"type": "integer"},
            "int": {"type": "integer"},
            "double": {"type": "number"},
            "float": {"type": "number"},
            "number": {"type": "number"},
            "boolean": {"type": "boolean"},
            "bool": {"type": "boolean"},
            "object": {},
        }
        schema = type_map.get(self.prop_type, {"type": "string"})
        if self.description:
            schema["description"] = self.description
        if self.nested_schema and self.prop_type == "object":
            schema = dict(self.nested_schema)
        if self.is_array:
            schema = {"type": "array", "items": schema}
        return schema


def build_object(name: str, properties: list[SchemaProperty], any_of_schemas: list[dict] = None) -> dict:
    schema = {
        "name": name,
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    required = []
    for prop in properties:
        parts = prop.name.split(".")
        current = schema["properties"]
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {"type": "object", "properties": {}, "additionalProperties": False}
            current = current[part]["properties"]
        current[parts[-1]] = prop.to_schema()
        if not prop.is_optional:
            _add_required(schema, parts[:-1], parts[-1])

    if any_of_schemas:
        schema["anyOf"] = any_of_schemas

    return schema


def _add_required(schema: dict, path: list[str], field: str):
    current = schema
    for part in path:
        current = current["properties"].get(part, {})
    if "required" not in current:
        current["required"] = []
    current["required"].append(field)


def format_schema(schema: dict, indent=2) -> str:
    output = {"type": "json_schema", "json_schema": schema}
    return json.dumps(output, indent=indent)
