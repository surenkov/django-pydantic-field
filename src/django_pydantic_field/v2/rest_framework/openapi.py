from __future__ import annotations

import typing as ty

from rest_framework import renderers as drf_renderers
from rest_framework import serializers
from rest_framework.schemas import openapi
from rest_framework.schemas import utils as drf_schema_utils
from rest_framework.test import APIRequestFactory

from django_pydantic_field._internal._annotation_utils import get_origin_type
from django_pydantic_field._internal._openapi import translate_adapter_schema, wrap_ref_siblings

from . import fields, parsers, renderers

if ty.TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic.json_schema import JsonSchemaMode

    from django_pydantic_field._internal._openapi import OpenAPISchema
    from django_pydantic_field.v2.types import SchemaAdapter


class AutoSchema(openapi.AutoSchema):
    REF_TEMPLATE_PREFIX = "#/components/schemas/{model}"

    def __init__(
        self,
        tags: Sequence[str] | None = None,
        operation_id_base: str | None = None,
        component_name: str | None = None,
    ) -> None:
        super().__init__(tags, operation_id_base, component_name)  # type: ignore[invalid-argument-type]
        self._adapter_mode: JsonSchemaMode = "validation"
        self.rf = APIRequestFactory()

    def _translate_adapter(
        self,
        adapter: SchemaAdapter[ty.Any] | None,
        *,
        mode: JsonSchemaMode = "validation",
        unwrap_root_nullable: bool = False,
    ) -> OpenAPISchema:
        return translate_adapter_schema(
            adapter,
            ref_template=self.REF_TEMPLATE_PREFIX,
            mode=mode,
            oas_version="3.0",
            unwrap_root_nullable=unwrap_root_nullable,
        )

    def map_field(self, field: serializers.Field) -> dict[str, ty.Any]:
        if isinstance(field, fields.SchemaField):
            return self._translate_adapter(
                field.adapter,
                mode=self._adapter_mode,
                unwrap_root_nullable=bool(field.allow_null),
            ).schema
        return super().map_field(field)

    def map_serializer(self, serializer: serializers.BaseSerializer) -> dict[str, ty.Any]:
        result = super().map_serializer(serializer)
        properties = result.get("properties")
        if isinstance(properties, dict):
            for prop_name, prop_schema in properties.items():
                if isinstance(prop_schema, dict):
                    properties[prop_name] = wrap_ref_siblings(prop_schema)
        return result

    def map_parsers(self, path: str, method: str) -> list[str]:
        return super().map_parsers(path, method)

    def _non_browsable_renderers(self) -> list[type[ty.Any]]:
        return [
            renderer
            for renderer in self.view.renderer_classes
            if not issubclass(get_origin_type(renderer), drf_renderers.BrowsableAPIRenderer)
        ]

    def map_renderers(self, path: str, method: str) -> list[str]:
        return [renderer.media_type for renderer in self._non_browsable_renderers()]

    def get_request_body(self, path: str, method: str) -> dict[str, ty.Any]:
        if method not in ("PUT", "PATCH", "POST"):
            return {}

        self.request_media_types = self.map_parsers(path, method)
        serializer = self.get_request_serializer(path, method)

        request_schema: dict[str, ty.Any] = {}
        if isinstance(serializer, serializers.Serializer):
            request_schema = self.get_reference(serializer)

        schema_content: dict[str, ty.Any] = {}
        for parser, ct in zip(self.view.parser_classes, self.request_media_types):
            if issubclass(get_origin_type(parser), parsers.SchemaParser):
                adapter = self._get_parser_adapter(parser, path, method)
                parser_schema = self._translate_adapter(adapter, mode="validation").schema
            else:
                parser_schema = request_schema

            schema_content[ct] = {"schema": parser_schema}

        return {"content": schema_content}

    def get_responses(self, path: str, method: str) -> dict[str, ty.Any]:
        if method == "DELETE":
            return {"204": {"description": ""}}

        self.response_media_types = self.map_renderers(path, method)
        serializer = self.get_response_serializer(path, method)

        response_schema: dict[str, ty.Any] = {}
        if isinstance(serializer, serializers.Serializer):
            response_schema = self.get_reference(serializer)

        is_list_view = drf_schema_utils.is_list_view(path, method, self.view)
        if is_list_view:
            response_schema = self._get_paginated_schema(response_schema)

        schema_content: dict[str, ty.Any] = {}
        for renderer, ct in zip(self._non_browsable_renderers(), self.response_media_types):
            if issubclass(get_origin_type(renderer), renderers.SchemaRenderer):
                adapter = self._get_renderer_adapter(renderer, path, method)
                item_schema = self._translate_adapter(adapter, mode="serialization").schema
                if is_list_view and item_schema:
                    item_schema = self._get_paginated_schema(item_schema)
                schema_content[ct] = {"schema": item_schema}
            else:
                schema_content[ct] = {"schema": response_schema}

        status_code = "201" if method == "POST" else "200"
        return {
            status_code: {
                "content": schema_content,
                "description": "",
            }
        }

    def get_components(self, path: str, method: str) -> dict[str, ty.Any]:
        components: dict[str, ty.Any] = {}
        upper_method = method.upper()

        if upper_method in ("PUT", "PATCH", "POST"):
            request_serializer = self.get_request_serializer(path, method)
            if isinstance(request_serializer, serializers.Serializer):
                components.update(self._collect_serializer_components(request_serializer, "validation"))

        for parser in self.view.parser_classes:
            if issubclass(get_origin_type(parser), parsers.SchemaParser):
                adapter = self._get_parser_adapter(parser, path, method)
                components.update(self._translate_adapter(adapter, mode="validation").components)

        if upper_method != "DELETE":
            response_serializer = self.get_response_serializer(path, method)
            if isinstance(response_serializer, serializers.Serializer):
                components.update(self._collect_serializer_components(response_serializer, "serialization"))

        for renderer in self.view.renderer_classes:
            if issubclass(get_origin_type(renderer), renderers.SchemaRenderer):
                adapter = self._get_renderer_adapter(renderer, path, method)
                components.update(self._translate_adapter(adapter, mode="serialization").components)

        return components

    def _collect_field_components(
        self,
        field: serializers.Field,
        mode: JsonSchemaMode,
    ) -> dict[str, ty.Any]:
        if isinstance(field, fields.SchemaField):
            return self._translate_adapter(
                field.adapter,
                mode=mode,
                unwrap_root_nullable=bool(field.allow_null),
            ).components
        if isinstance(field, (serializers.ListSerializer, serializers.ListField)) and isinstance(
            field.child, serializers.Field
        ):
            return self._collect_field_components(field.child, mode)
        if isinstance(field, serializers.Serializer):
            defs: dict[str, ty.Any] = {}
            for child_field in field.fields.values():
                defs.update(self._collect_field_components(child_field, mode))
            return defs
        return {}

    def _collect_serializer_components(
        self,
        serializer: serializers.Serializer,
        mode: JsonSchemaMode,
    ) -> dict[str, ty.Any]:
        defs: dict[str, ty.Any] = {}
        prev_mode = self._adapter_mode
        self._adapter_mode = mode
        try:
            for field in serializer.fields.values():
                defs.update(self._collect_field_components(field, mode))
            component_name = self.get_component_name(serializer)
            defs[component_name] = self.map_serializer(serializer)
        finally:
            self._adapter_mode = prev_mode
        return defs

    def _fallback_view_context(self) -> dict[str, ty.Any]:
        return {
            "view": self.view,
            "args": getattr(self.view, "args", ()),
            "kwargs": getattr(self.view, "kwargs", {}),
        }

    def _get_parser_adapter(self, parser_cls: type[ty.Any], path: str, method: str) -> SchemaAdapter[ty.Any] | None:
        request = self.rf.generic(method, path)
        try:
            ctx = self.view.get_parser_context(request)
        except Exception:
            ctx = self._fallback_view_context()
        return parser_cls().get_adapter(ctx or {})

    def _get_renderer_adapter(self, renderer_cls: type[ty.Any], path: str, method: str) -> SchemaAdapter[ty.Any] | None:
        try:
            ctx = self.view.get_renderer_context()
        except Exception:
            ctx = self._fallback_view_context()
        return renderer_cls().get_adapter(ctx or {})

    def _get_paginated_schema(self, schema: dict[str, ty.Any]) -> dict[str, ty.Any]:
        response_schema: dict[str, ty.Any] = (
            schema if schema.get("type") == "array" else {"type": "array", "items": schema}
        )
        paginator = self.get_paginator()
        if paginator:
            response_schema = paginator.get_paginated_response_schema(response_schema)  # type: ignore
        return response_schema
