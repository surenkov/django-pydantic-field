from __future__ import annotations

import copy
import typing as ty

import pydantic
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.plumbing import ResolvedComponent, is_jsonschema_compliant

if ty.TYPE_CHECKING:
    from drf_spectacular.openapi import AutoSchema
    from drf_spectacular.utils import Direction


def _unwrap_nullable(schema: dict[str, ty.Any]) -> dict[str, ty.Any]:
    """Unwrap top-level anyOf null union so drf-spectacular's append_meta applies allow_null once."""
    if "anyOf" in schema:
        any_of = schema["anyOf"]
        null_types = [item for item in any_of if item == {"type": "null"}]
        non_null = [item for item in any_of if item != {"type": "null"}]
        if null_types and len(non_null) == 1 and isinstance(non_null[0], dict):
            rest = {k: v for k, v in schema.items() if k != "anyOf"}
            return {**rest, **non_null[0]}
    return schema


def _normalize_oas_30(schema: ty.Any) -> ty.Any:
    """Recursively normalize JSON Schema draft-2020-12 nullability into OpenAPI 3.0 syntax."""
    if isinstance(schema, dict):
        if "anyOf" in schema:
            any_of = schema["anyOf"]
            null_types = [item for item in any_of if item == {"type": "null"}]
            non_null = [item for item in any_of if item != {"type": "null"}]
            if null_types and len(non_null) == 1:
                sub = _normalize_oas_30(non_null[0])
                rest = {k: _normalize_oas_30(v) for k, v in schema.items() if k != "anyOf"}
                if isinstance(sub, dict) and "$ref" in sub:
                    return {"allOf": [sub], "nullable": True, **rest}
                if isinstance(sub, dict):
                    return {**sub, "nullable": True, **rest}
        return {k: _normalize_oas_30(v) for k, v in schema.items()}
    elif isinstance(schema, list):
        return [_normalize_oas_30(item) for item in schema]
    return schema


class PydanticSchemaFieldExtension(OpenApiSerializerFieldExtension):
    """drf-spectacular extension for django_pydantic_field.v2.rest_framework.SchemaField."""

    target_class = "django_pydantic_field.v2.rest_framework.SchemaField"
    match_subclasses = True

    def map_serializer_field(self, auto_schema: AutoSchema, direction: Direction) -> dict[str, ty.Any]:
        adapter = self.target.adapter
        mode = "validation" if direction == "request" else "serialization"
        by_alias = adapter.export_kwargs.get("by_alias", True)
        ref_template = "#/components/schemas/{model}"

        schema = copy.deepcopy(
            adapter.type_adapter.json_schema(
                by_alias=by_alias,
                ref_template=ref_template,
                mode=mode,
            )
        )
        defs = schema.pop("$defs", {})

        if getattr(self.target, "allow_null", False):
            schema = _unwrap_nullable(schema)

        if not is_jsonschema_compliant():
            schema = _normalize_oas_30(schema)
            defs = {k: _normalize_oas_30(v) for k, v in defs.items()}

        for sub_name, sub_schema in defs.items():
            comp = ResolvedComponent(
                name=sub_name,
                type=ResolvedComponent.SCHEMA,
                schema=sub_schema,
                object=sub_name,
            )
            auto_schema.registry.register_on_missing(comp)

        prepared = getattr(adapter, "prepared_schema", None)
        if isinstance(prepared, type) and issubclass(prepared, pydantic.BaseModel):
            name = prepared.__name__
            comp = ResolvedComponent(
                name=name,
                type=ResolvedComponent.SCHEMA,
                schema=schema,
                object=name,
            )
            auto_schema.registry.register_on_missing(comp)
            return {"$ref": f"#/components/schemas/{name}"}

        schema.pop("title", None)
        return schema
