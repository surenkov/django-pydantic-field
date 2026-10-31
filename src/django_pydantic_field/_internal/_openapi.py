from __future__ import annotations

import typing as ty

if ty.TYPE_CHECKING:
    from django_pydantic_field.types import BaseSchemaAdapter


class OpenAPISchema(ty.NamedTuple):
    schema: dict[str, ty.Any]
    components: dict[str, dict[str, ty.Any]]


def _split_null_any_of(any_of: list[ty.Any]) -> tuple[bool, list[ty.Any]]:
    null_item = {"type": "null"}
    non_null = [item for item in any_of if item != null_item]
    return len(non_null) < len(any_of), non_null


def unwrap_nullable(schema: dict[str, ty.Any]) -> dict[str, ty.Any]:
    """Unwrap top-level anyOf null union so the caller (DRF / drf-spectacular) applies allow_null once."""
    if "anyOf" not in schema:
        return schema

    has_null, non_null = _split_null_any_of(schema["anyOf"])
    if not has_null:
        return schema

    rest = {k: v for k, v in schema.items() if k != "anyOf"}
    if len(non_null) == 1 and isinstance(non_null[0], dict):
        return {**rest, **non_null[0]}
    if len(non_null) > 1:
        return {**rest, "anyOf": non_null}
    return schema


def normalize_oas_30(schema: ty.Any) -> ty.Any:
    """Recursively normalize JSON Schema Draft 2020-12 / Draft 7 constructs into OpenAPI 3.0.2 syntax."""
    if isinstance(schema, list):
        return [normalize_oas_30(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    if "anyOf" in schema:
        has_null, non_null = _split_null_any_of(schema["anyOf"])
        if has_null and non_null:
            rest = {k: normalize_oas_30(v) for k, v in schema.items() if k != "anyOf"}
            if len(non_null) == 1:
                sub = normalize_oas_30(non_null[0])
                if isinstance(sub, dict) and "$ref" in sub:
                    return {"allOf": [sub], "nullable": True, **rest}
                if isinstance(sub, dict):
                    return {**sub, "nullable": True, **rest}
            else:
                subs = [normalize_oas_30(item) for item in non_null]
                union_key = "oneOf" if "discriminator" in rest else "anyOf"
                return {union_key: subs, "nullable": True, **rest}

    result: dict[str, ty.Any] = {}
    for k, v in schema.items():
        if k == "const":
            result["enum"] = [v]
        elif k == "exclusiveMinimum" and isinstance(v, (int, float)) and not isinstance(v, bool):
            result["minimum"] = v
            result["exclusiveMinimum"] = True
        elif k == "exclusiveMaximum" and isinstance(v, (int, float)) and not isinstance(v, bool):
            result["maximum"] = v
            result["exclusiveMaximum"] = True
        elif k in ("prefixItems", "items") and isinstance(v, list):
            normalized_items = [normalize_oas_30(item) for item in v]
            if k == "items" or not isinstance(schema.get("items"), dict):
                if len(normalized_items) > 1:
                    result["items"] = {"anyOf": normalized_items}
                elif len(normalized_items) == 1:
                    result["items"] = normalized_items[0]
                else:
                    result["items"] = {}
                result.setdefault("minItems", len(normalized_items))
                result.setdefault("maxItems", len(normalized_items))
        elif k == "items" and isinstance(v, bool) and "prefixItems" in schema:
            continue
        elif k == "additionalItems" and isinstance(v, bool) and isinstance(schema.get("items"), list):
            continue
        elif k == "anyOf" and "discriminator" in schema:
            result["oneOf"] = [normalize_oas_30(item) for item in v]
        else:
            result[k] = normalize_oas_30(v)

    return result


def wrap_ref_siblings(schema: dict[str, ty.Any]) -> dict[str, ty.Any]:
    """Ensure '$ref' in an OpenAPI 3.0 Schema Object has no sibling keys by wrapping in 'allOf'."""
    if "$ref" in schema and len(schema) > 1:
        ref = schema["$ref"]
        siblings = {k: v for k, v in schema.items() if k != "$ref"}
        if not siblings:
            return {"$ref": ref}
        return {"allOf": [{"$ref": ref}], **siblings}
    if isinstance(schema.get("properties"), dict):
        schema["properties"] = {
            k: wrap_ref_siblings(v) if isinstance(v, dict) else v for k, v in schema["properties"].items()
        }
    if isinstance(schema.get("items"), dict):
        schema["items"] = wrap_ref_siblings(schema["items"])
    return schema


def translate_adapter_schema(
    adapter: BaseSchemaAdapter[ty.Any] | None,
    *,
    ref_template: str = "#/components/schemas/{model}",
    mode: ty.Literal["validation", "serialization"] = "validation",
    oas_version: ty.Literal["3.0", "3.1"] = "3.0",
    unwrap_root_nullable: bool = False,
) -> OpenAPISchema:
    """Extract, normalize, and hoist component schemas from a BaseSchemaAdapter (v1 or v2)."""
    if adapter is None:
        return OpenAPISchema({}, {})

    schema, defs = adapter.raw_openapi_schema(ref_template=ref_template, mode=mode)

    if unwrap_root_nullable:
        schema = unwrap_nullable(schema)

    if oas_version == "3.0":
        schema = normalize_oas_30(schema)
        defs = {k: normalize_oas_30(v) for k, v in defs.items()}

    name = adapter.root_model_name
    if name is not None:
        ref_uri = ref_template.format(model=name)
        if name not in defs and "$ref" not in schema:
            defs[name] = schema
            return OpenAPISchema({"$ref": ref_uri}, defs)
        if schema == {"$ref": ref_uri}:
            return OpenAPISchema({"$ref": ref_uri}, defs)

    schema.pop("title", None)
    return OpenAPISchema(schema, defs)
