from __future__ import annotations

import typing as ty

import pydantic
import weakref
from rest_framework import serializers
from rest_framework.schemas import openapi, utils as drf_schema_utils
from rest_framework.test import APIRequestFactory

from . import fields, parsers, renderers

if ty.TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic.json_schema import JsonSchemaMode

    from . import mixins


class AutoSchema(openapi.AutoSchema):
    REF_TEMPLATE_PREFIX = "#/components/schemas/{model}"

    def __init__(self, tags=None, operation_id_base=None, component_name=None) -> None:
        super().__init__(tags, operation_id_base, component_name)
        self.collected_schema_defs: dict[str, ty.Any] = {}
        self.adapter_type_to_schema_refs = weakref.WeakKeyDictionary[type, str]()
        self.adapter_mode: JsonSchemaMode = "validation"
        self.rf = APIRequestFactory()

    def get_components(self, path: str, method: str) -> dict[str, ty.Any]:
        if method.lower() == "delete":
            return {}

        super().get_components

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
            if issubclass(parser, parsers.SchemaParser):
                ref_path = self._get_component_ref(self.adapter_type_to_schema_refs[parser])
                schema_content[ct] = {"schema": {"$ref": ref_path}}
            else:
                schema_content[ct] = request_schema

        return {"content": schema_content}

    def get_responses(self, path, method):
        if method == "DELETE":
            return {"204": {"description": ""}}

        self.response_media_types = self.map_renderers(path, method)
        serializer = self.get_response_serializer(path, method)

        item_schema = {}
        if isinstance(serializer, serializers.Serializer):
            item_schema = self.get_reference(serializer)

        if drf_schema_utils.is_list_view(path, method, self.view):
            response_schema = {"type": "array", "items": item_schema}
            paginator = self.get_paginator()
            if paginator:
                response_schema = paginator.get_paginated_response_schema(response_schema)
        else:
            response_schema = item_schema

        schema_content = {}
        for renderer, ct in zip(self.view.renderer_classes, self.response_media_types):
            if issubclass(renderer, renderers.SchemaRenderer):
                ref_path = self._get_component_ref(self.adapter_type_to_schema_refs[renderer])
                schema_content[ct] = {"schema": {"$ref": ref_path}}
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
            if issubclass(parser, parsers.SchemaParser):
                schema_parsers.append(parser())

        if schema_parsers:
            self.adapter_mode = "validation"
            request = self.rf.generic(method, path)
            schemas = self._collect_adapter_components(schema_parsers, self.view.get_parser_context(request))
            self.collected_schema_defs.update(schemas)

        return media_types

    def map_renderers(self, path: str, method: str) -> list[str]:
        schema_renderers = []
        media_types = []

        for renderer in self.view.renderer_classes:
            media_types.append(renderer.media_type)
            if issubclass(renderer, renderers.SchemaRenderer):
                schema_renderers.append(renderer())

        if schema_renderers:
            self.adapter_mode = "serialization"
            schemas = self._collect_adapter_components(schema_renderers, self.view.get_renderer_context())
            self.collected_schema_defs.update(schemas)

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

    def _collect_adapter_components(self, components: Iterable[mixins.AnnotatedAdapterMixin], context: dict):
        type_adapters = []

        for component in components:
            schema_adapter = component.get_adapter(context)
            if schema_adapter is not None:
                schema_name = schema_adapter.prepared_schema.__class__.__name__
                self.adapter_type_to_schema_refs[type(component)] = schema_name

                type_adapters.append((schema_name, self.adapter_mode, schema_adapter.type_adapter))

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

    def _get_component_ref(self, model: str):
        return self.REF_TEMPLATE_PREFIX.format(model=model)
