from __future__ import annotations

import typing as ty

import pydantic

from rest_framework import serializers
from rest_framework.schemas import openapi

from .fields import SchemaField

if ty.TYPE_CHECKING:
    from pydantic.json_schema import JsonSchemaMode


class AutoSchema(openapi.AutoSchema):
    _SCHEMA_REF_TEMPLATE_PREFIX = "#/components/schemas/{model}"

    def __init__(self, tags=None, operation_id_base=None, component_name=None) -> None:
        super().__init__(tags, operation_id_base, component_name)
        self.collected_schema_defs = {}

    def get_components(self, path: str, method: str) -> dict[str, ty.Any]:
        if method.lower() == "delete":
            return {}

        request_serializer = self.get_request_serializer(path, method)
        response_serializer = self.get_response_serializer(path, method)
        components = {}

        if isinstance(request_serializer, serializers.Serializer):
            component_name = self.get_component_name(request_serializer)
            content = self.map_serializer(request_serializer, "validation")
            components.setdefault(component_name, content)

        if isinstance(response_serializer, serializers.Serializer):
            component_name = self.get_component_name(response_serializer)
            content = self.map_serializer(response_serializer, "serialization")
            components.setdefault(component_name, content)

        if self.collected_schema_defs:
            components.update(self.collected_schema_defs)
            self.collected_schema_defs = {}

        return components

    def map_serializer(
        self,
        serializer: serializers.Serializer,
        mode: JsonSchemaMode = "validation",
    ) -> dict[str, ty.Any]:
        component_content = super().map_serializer(serializer)
        schema_fields_adapters = []

        for field in serializer.fields.values():
            if isinstance(field, SchemaField):
                schema_fields_adapters.append((field.field_name, mode, field.adapter.type_adapter))

        if schema_fields_adapters:
            field_schemas, common_schemas = pydantic.TypeAdapter.json_schemas(
                schema_fields_adapters,
                ref_template=self._SCHEMA_REF_TEMPLATE_PREFIX,
            )
            for (field_name, _), field_schema in field_schemas.items():
                component_content["properties"][field_name] = field_schema

            self.collected_schema_defs.update(common_schemas.get("$defs", {}))

        return component_content

    def map_parsers(self, path: str, method: str) -> list[str]:
        # TODO: Implmenent SchemaParser
        return super().map_parsers(path, method)

    def map_renderers(self, path: str, method: str) -> list[str]:
        # TODO: Implement SchemaRenderer
        return super().map_renderers(path, method)
