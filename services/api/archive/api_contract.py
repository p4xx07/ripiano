"""The versioned API contract: JSON shapes of requests and responses for the documented operations.

`api_contract_v1.json` is recorded from a realistic scenario (archive/test_api_contract.py) and published in
/api/schema.json. Version 1 promises additive changes only: a response may gain fields, but a recorded
field is never removed or changed to another type, and a recorded route never disappears, without a new
API version. Regenerate after an intended, compatible change with:

    RIPIANO_WRITE_CONTRACT=1 RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_api_contract.py
"""

import json
from pathlib import Path

CONTRACT_FILE = Path(__file__).with_name("api_contract_v1.json")
API_VERSION = "1"


def _type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def shape(value):
    """A JSON Schema (subset) describing one JSON value."""
    kind = _type(value)
    if kind == "object":
        return {"type": ["object"], "properties": {key: shape(item) for key, item in sorted(value.items())}}
    if kind == "array":
        items = None
        for item in value:
            items = shape(item) if items is None else merge(items, shape(item))
        return {"type": ["array"], **({"items": items} if items is not None else {})}
    return {"type": [kind]}


def merge(left, right):
    """Combine two shapes seen for the same field (for example a value that is sometimes null)."""
    result: dict = {"type": sorted(set(left.get("type", [])) | set(right.get("type", [])))}
    if "properties" in left or "properties" in right:
        properties = dict(left.get("properties", {}))
        for key, value in right.get("properties", {}).items():
            properties[key] = merge(properties[key], value) if key in properties else value
        result["properties"] = dict(sorted(properties.items()))
    if "items" in left or "items" in right:
        result["items"] = merge(left["items"], right["items"]) if "items" in left and "items" in right else left.get("items") or right.get("items")
    return result


def breaking_changes(expected, actual, path="$"):
    """Differences that would break a client written against `expected`. New fields are allowed."""
    problems = []
    # A type that was promised must still be possible; "null" alone (an optional value) does not pin a type.
    promised = set(expected.get("type", [])) - {"null"}
    seen = set(actual.get("type", []))
    if promised and not promised & seen and seen != {"null"}:
        problems.append(f"{path}: type changed from {sorted(promised)} to {sorted(seen)}")
    for key, value in expected.get("properties", {}).items():
        if "properties" in actual or "object" in seen:
            if key not in actual.get("properties", {}):
                problems.append(f"{path}.{key}: field removed")
            else:
                problems += breaking_changes(value, actual["properties"][key], f"{path}.{key}")
    if "items" in expected and "items" in actual:
        problems += breaking_changes(expected["items"], actual["items"], f"{path}[]")
    return problems


def load():
    try:
        return json.loads(CONTRACT_FILE.read_text())
    except (OSError, ValueError):
        return {"version": API_VERSION, "operations": {}}


def to_openapi(entry):
    """OpenAPI 3.1 fragments (requestBody, responses) for one recorded operation."""
    def schema(value):
        result: dict = {key: value[key] for key in ("properties",) if key in value}
        types = value.get("type", [])
        result["type"] = types[0] if len(types) == 1 else types
        if "properties" in result:
            result["properties"] = {key: schema(item) for key, item in result["properties"].items()}
        if "items" in value:
            result["items"] = schema(value["items"])
        return result

    fragment = {"responses": {str(entry["status"]): {"description": "JSON response", "content": {"application/json": {"schema": schema(entry["response"])}}}}}
    if entry.get("request"):
        fragment["requestBody"] = {"content": {"application/json": {"schema": schema(entry["request"])}}}
    if entry.get("multipart"):
        fragment["requestBody"] = {"content": {"multipart/form-data": {"schema": {"type": "object", "properties": {key: {"type": "string", "format": "binary"} for key in entry["multipart"]}}}}}
    return fragment
