from __future__ import annotations

import typing as ty

from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.plumbing import ResolvedComponent, is_jsonschema_compliant

from django_pydantic_field._internal._openapi import translate_adapter_schema
from django_pydantic_field.compat.pydantic import PYDANTIC_V2

if ty.TYPE_CHECKING:
    from drf_spectacular.openapi import AutoSchema
    from drf_spectacular.utils import Direction

__all__ = ("PydanticSchemaFieldExtension",)

if PYDANTIC_V2:

    class PydanticSchemaFieldExtension(OpenApiSerializerFieldExtension):
        """drf-spectacular extension for django_pydantic_field.v2.rest_framework.SchemaField."""

        target_class = "django_pydantic_field.v2.rest_framework.SchemaField"
        match_subclasses = True

        def map_serializer_field(self, auto_schema: AutoSchema, direction: Direction) -> dict[str, ty.Any]:
            adapter = self.target.adapter
            mode: ty.Literal["validation", "serialization"] = (
                "validation" if direction == "request" else "serialization"
            )
            oas_version: ty.Literal["3.0", "3.1"] = "3.1" if is_jsonschema_compliant() else "3.0"

            openapi_schema = translate_adapter_schema(
                adapter,
                ref_template="#/components/schemas/{model}",
                mode=mode,
                oas_version=oas_version,
                unwrap_root_nullable=bool(getattr(self.target, "allow_null", False)),
            )

            for sub_name, sub_schema in openapi_schema.components.items():
                comp = ResolvedComponent(
                    name=sub_name,
                    type=ResolvedComponent.SCHEMA,
                    schema=sub_schema,
                    object=sub_name,
                )
                auto_schema.registry.register_on_missing(comp)

            return openapi_schema.schema
