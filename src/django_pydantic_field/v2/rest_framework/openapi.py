from __future__ import annotations

import typing as ty

import pydantic
from rest_framework import serializers
from rest_framework.schemas import openapi
from rest_framework.schemas import utils as drf_schema_utils
from rest_framework.test import APIRequestFactory

from django_pydantic_field._internal._annotation_utils import get_origin_type

from . import fields, parsers, renderers

if ty.TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic.json_schema import JsonSchemaMode

    from . import mixins


class AutoSchema(openapi.AutoSchema):
    REF_TEMPLATE_PREFIX = "#/components/schemas/{model}"

    def __init__(self, tags=None, operation_id_base=None, component_name=None) -> None:
        super().__init__(tags, operation_id_base, component_name)  # type: ignore[invalid-argument-type]  # typeshed is not correct
        self.collected_schema_defs: dict[str, ty.Any] = {}
        self.collected_adapter_schema_refs: dict[str, ty.Any] = {}
        self.adapter_mode: JsonSchemaMode = "validation"
        self.rf = APIRequestFactory()

    def get_components(self, path: str, method: str) -> dict[str, ty.Any]:
        if method.lower() == "delete":
            return {}

        request_serializer = self.get_request_serializer(path, method)  # type: ignore[attr-defined]
        response_serializer = self.get_response_serializer(path, method)  # type: ignore[attr-defined]

        components = {
            **self._collect_serializer_component(response_serializer, "serialization"),
            **self._collect_serializer_component(request_serializer, "validation"),
        }
        if self.collected_schema_defs:
            components.update(self.collected_schema_defs)
            self.collected_schema_defs = {}

        return components

    def get_request_body(self, path, method):
        if method not in ("PUT", "PATCH", "POST"):
            return {}

        self.request_media_types = self.map_parsers(path, method)

        request_schema = {}
        serializer = self.get_request_serializer(path, method)
        if isinstance(serializer, serializers.Serializer):
            request_schema = self.get_reference(serializer)

        schema_content = {}

        for parser, ct in zip(self.view.parser_classes, self.request_media_types):
            if issubclass(get_origin_type(parser), parsers.SchemaParser):
                parser_schema = self.collected_adapter_schema_refs[repr(parser)]
            else:
                parser_schema = request_schema

            schema_content[ct] = {"schema": parser_schema}

        return {"content": schema_content}

    def get_responses(self, path, method):
        if method == "DELETE":
            return {"204": {"description": ""}}

        self.response_media_types = self.map_renderers(path, method)
        serializer = self.get_response_serializer(path, method)

        response_schema = {}
        if isinstance(serializer, serializers.Serializer):
            response_schema = self.get_reference(serializer)

        is_list_view = drf_schema_utils.is_list_view(path, method, self.view)
        if is_list_view:
            response_schema = self._get_paginated_schema(response_schema)

        schema_content = {}
        for renderer, ct in zip(self.view.renderer_classes, self.response_media_types):
            if issubclass(get_origin_type(renderer), renderers.SchemaRenderer):
                renderer_schema = {"schema": self.collected_adapter_schema_refs[repr(renderer)]}
                if is_list_view:
                    renderer_schema = self._get_paginated_schema(renderer_schema)
                schema_content[ct] = renderer_schema
            else:
                schema_content[ct] = response_schema

        status_code = "201" if method == "POST" else "200"
        return {
            status_code: {
                "content": schema_content,
                "description": "",
            }
        }

    def map_parsers(self, path: str, method: str) -> list[str]:
        schema_parsers = []
        media_types = []

        for parser in self.view.parser_classes:
            media_types.append(parser.media_type)
            if issubclass(get_origin_type(parser), parsers.SchemaParser):
                schema_parsers.append(parser)

        if schema_parsers:
            self.adapter_mode = "validation"
            request = self.rf.generic(method, path)
            schemas = self._collect_adapter_components(schema_parsers, self.view.get_parser_context(request))
            self.collected_adapter_schema_refs.update(schemas)

        return media_types

    def map_renderers(self, path: str, method: str) -> list[str]:
        schema_renderers = []
        media_types = []

        for renderer in self.view.renderer_classes:
            media_types.append(renderer.media_type)
            if issubclass(get_origin_type(renderer), renderers.SchemaRenderer):
                schema_renderers.append(renderer)

        if schema_renderers:
            self.adapter_mode = "serialization"
            schemas = self._collect_adapter_components(schema_renderers, self.view.get_renderer_context())
            self.collected_adapter_schema_refs.update(schemas)

        return media_types

    def map_serializer(self, serializer):
        component_content = super().map_serializer(serializer)
        field_adapters = []

        for field in serializer.fields.values():
            if isinstance(field, fields.SchemaField):
                field_adapters.append((field.field_name, self.adapter_mode, field.adapter.type_adapter))

        if field_adapters:
            field_schemas = self._collect_type_adapter_schemas(field_adapters)
            for field_name, field_schema in field_schemas.items():
                component_content["properties"][field_name] = field_schema

        return component_content

    def _collect_serializer_component(self, serializer: serializers.BaseSerializer | None, mode: JsonSchemaMode):
        schema_definition = {}
        if isinstance(serializer, serializers.Serializer):
            self.adapter_mode = mode
            component_name = self.get_component_name(serializer)
            schema_definition[component_name] = self.map_serializer(serializer)
        return schema_definition

    def _collect_adapter_components(self, components: Iterable[type[mixins.AnnotatedAdapterMixin]], context: dict):
        type_adapters = []

        for component in components:
            schema_adapter = component().get_adapter(context)
            if schema_adapter is not None:
                type_adapters.append((repr(component), self.adapter_mode, schema_adapter.type_adapter))

        if type_adapters:
            return self._collect_type_adapter_schemas(type_adapters)

        return {}

    def _collect_type_adapter_schemas(self, adapters: Iterable[tuple[str, JsonSchemaMode, pydantic.TypeAdapter]]):
        inner_schemas = {}

        schemas, common_schemas = pydantic.TypeAdapter.json_schemas(adapters, ref_template=self.REF_TEMPLATE_PREFIX)
        for (field_name, _), field_schema in schemas.items():
            inner_schemas[field_name] = field_schema

        self.collected_schema_defs.update(common_schemas.get("$defs", {}))
        return inner_schemas

    def _get_paginated_schema(self, schema) -> ty.Any:
        response_schema = {"type": "array", "items": schema}
        paginator = self.get_paginator()
        if paginator:
            response_schema = paginator.get_paginated_response_schema(response_schema)  # type: ignore
        return response_schema
