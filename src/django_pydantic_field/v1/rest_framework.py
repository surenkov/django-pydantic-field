from __future__ import annotations

import typing as ty

from django.http import HttpRequest
from rest_framework import exceptions, parsers, renderers, serializers
from rest_framework.pagination import BasePagination
from rest_framework.schemas import openapi
from rest_framework.schemas.utils import is_list_view

from django_pydantic_field._internal._openapi import translate_adapter_schema, wrap_ref_siblings
from django_pydantic_field.compat.typing import get_args
from django_pydantic_field.v1 import types
from django_pydantic_field.v1.compat import pydantic_v1

if ty.TYPE_CHECKING:
    from django_pydantic_field._internal._openapi import OpenAPISchema
    from django_pydantic_field.compat.pydantic import ConfigType

    RequestResponseContext = ty.Mapping[str, ty.Any]

__all__ = (
    "AutoSchema",
    "SchemaField",
    "SchemaParser",
    "SchemaRenderer",
)


class AnnotatedAdapterMixin(ty.Generic[types.ST]):
    schema_ctx_attr: ty.ClassVar[str] = "schema"
    schema_ctx_attrs: ty.ClassVar[tuple[str, ...]] = ()
    require_explicit_schema: ty.ClassVar[bool] = False

    def _build_adapter(
        self,
        schema: ty.Any,
        ctx: RequestResponseContext,
    ) -> types.SchemaAdapter[types.ST]:
        parent = ctx.get("view")
        config = ctx.get("config") or ctx.get("renderer_config") or ctx.get("parser_config")
        export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(ctx))
        return types.SchemaAdapter(schema, config, type(parent) if parent else None, None, **export_kwargs)

    def get_adapter(self, ctx: RequestResponseContext) -> ty.Optional[types.SchemaAdapter[types.ST]]:
        attrs = self.schema_ctx_attrs or (self.schema_ctx_attr,)
        schema = next((ctx[attr] for attr in attrs if ctx.get(attr) is not None), None)
        if schema is None:
            try:
                schema = get_args(self.__orig_class__)[0]  # type: ignore
            except (AttributeError, IndexError):
                schema = None

        if schema is None:
            if self.require_explicit_schema:
                raise ValueError("Schema should be either explicitly set with annotation or passed in the context")
            return None

        return self._build_adapter(schema, ctx)


class SchemaField(serializers.Field, ty.Generic[types.ST]):
    adapter: types.SchemaAdapter[types.ST]

    def __init__(
        self,
        schema: ty.Type[types.ST],
        config: ty.Optional[ConfigType] = None,
        **kwargs,
    ):
        self.export_params = types.SchemaAdapter.extract_export_kwargs(kwargs)
        super().__init__(**kwargs)
        self.adapter = types.SchemaAdapter(schema, config, None, None, allow_null=self.allow_null, **self.export_params)

    def bind(self, field_name, parent):
        if not self.adapter.is_bound:
            self.adapter.bind(type(parent), field_name)
        super().bind(field_name, parent)

    def to_internal_value(self, data: ty.Any) -> ty.Optional[types.ST]:
        try:
            if isinstance(data, (str, bytes)):
                return self.adapter.validate_json(data)
            return self.adapter.validate_python(data)
        except pydantic_v1.ValidationError as e:
            raise serializers.ValidationError(ty.cast(ty.Any, e.errors()))

    def to_representation(self, value: ty.Optional[types.ST]) -> ty.Any:
        return self.adapter.dump_python(value)


class SchemaRenderer(AnnotatedAdapterMixin[types.ST], renderers.JSONRenderer):
    schema_ctx_attr = "render_schema"
    schema_ctx_attrs = ("render_schema", "renderer_schema")

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        if response is not None and response.exception:
            return super().render(data, accepted_media_type, renderer_context)

        try:
            json_str = self.render_data(data, renderer_context)
        except pydantic_v1.ValidationError as e:
            json_str = e.json().encode()
        except AttributeError:
            json_str = super().render(data, accepted_media_type, renderer_context)

        return json_str

    def render_data(self, data, renderer_ctx) -> bytes:
        adapter = self.get_adapter(renderer_ctx or {})
        if adapter is None:
            adapter = types.SchemaAdapter(ty.Any, None, None, None)
        return adapter.dump_json(data, ensure_ascii=self.ensure_ascii)


class SchemaParser(AnnotatedAdapterMixin[types.ST], parsers.JSONParser):
    schema_ctx_attr = "parser_schema"
    renderer_class = SchemaRenderer
    require_explicit_schema = True

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        adapter = self.get_adapter(parser_context)
        if adapter is None:
            raise RuntimeError("Schema should be either explicitly set with annotation or passed in the context")

        try:
            return adapter.validate_json(stream.read())
        except pydantic_v1.ValidationError as e:
            raise exceptions.ParseError(ty.cast(ty.Any, e.errors()))


class AutoSchema(openapi.AutoSchema):
    REF_TEMPLATE_PREFIX = "#/components/schemas/{model}"
    get_request_serializer: ty.Callable

    def _translate_adapter(
        self,
        adapter: types.SchemaAdapter[ty.Any] | None,
        *,
        unwrap_root_nullable: bool = False,
    ) -> OpenAPISchema:
        return translate_adapter_schema(
            adapter,
            ref_template=self.REF_TEMPLATE_PREFIX,
            oas_version="3.0",
            unwrap_root_nullable=unwrap_root_nullable,
        )

    def map_field(self, field: serializers.Field) -> dict[str, ty.Any]:
        if isinstance(field, SchemaField):
            return self._translate_adapter(
                field.adapter,
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

    def _fallback_view_context(self) -> dict[str, ty.Any]:
        return {
            "view": self.view,
            "args": getattr(self.view, "args", ()),
            "kwargs": getattr(self.view, "kwargs", {}),
        }

    def _get_parser_context(self) -> dict[str, ty.Any]:
        try:
            return self.view.get_parser_context(HttpRequest()) or {}
        except Exception:
            return self._fallback_view_context()

    def _get_renderer_context(self) -> dict[str, ty.Any]:
        try:
            return self.view.get_renderer_context() or {}
        except Exception:
            return self._fallback_view_context()

    def map_parsers(self, path: str, method: str) -> list[ty.Any]:
        request_types: list[ty.Any] = []
        parser_ctx = self._get_parser_context()

        for parser_type in self.view.parser_classes:
            parser = parser_type()
            if isinstance(parser, SchemaParser):
                adapter = parser.get_adapter(parser_ctx)
                if adapter is not None:
                    parser_schema = self._translate_adapter(adapter).schema
                    request_types.append((parser.media_type, parser_schema))
                    continue

            request_types.append(parser.media_type)

        return request_types

    def map_renderers(self, path: str, method: str) -> list[ty.Any]:
        response_types: list[ty.Any] = []
        renderer_ctx = self._get_renderer_context()

        for renderer_type in self.view.renderer_classes:
            renderer = renderer_type()
            if isinstance(renderer, SchemaRenderer):
                adapter = renderer.get_adapter(renderer_ctx)
                if adapter is not None:
                    renderer_schema = self._translate_adapter(adapter).schema
                    response_types.append((renderer.media_type, renderer_schema))
                    continue

            if not isinstance(renderer, renderers.BrowsableAPIRenderer):
                response_types.append(renderer.media_type)

        return response_types

    def _collect_field_components(self, field: serializers.Field) -> dict[str, ty.Any]:
        if isinstance(field, SchemaField):
            return self._translate_adapter(
                field.adapter,
                unwrap_root_nullable=bool(field.allow_null),
            ).components
        if isinstance(field, (serializers.ListSerializer, serializers.ListField)) and isinstance(
            field.child, serializers.Field
        ):
            return self._collect_field_components(field.child)
        if isinstance(field, serializers.Serializer):
            defs: dict[str, ty.Any] = {}
            for child_field in field.fields.values():
                defs.update(self._collect_field_components(child_field))
            return defs
        return {}

    def get_components(self, path: str, method: str) -> dict[str, ty.Any]:
        components = dict(super().get_components(path, method))
        upper_method = method.upper()

        if upper_method in ("PUT", "PATCH", "POST"):
            request_serializer = self.get_request_serializer(path, method)
            if isinstance(request_serializer, serializers.Serializer):
                for field in request_serializer.fields.values():
                    components.update(self._collect_field_components(field))

        parser_ctx = self._get_parser_context()
        for parser_type in self.view.parser_classes:
            parser = parser_type()
            if isinstance(parser, SchemaParser):
                adapter = parser.get_adapter(parser_ctx)
                components.update(self._translate_adapter(adapter).components)

        if upper_method != "DELETE":
            response_serializer = self.get_response_serializer(path, method)
            if isinstance(response_serializer, serializers.Serializer):
                for field in response_serializer.fields.values():
                    components.update(self._collect_field_components(field))

        renderer_ctx = self._get_renderer_context()
        for renderer_type in self.view.renderer_classes:
            renderer = renderer_type()
            if isinstance(renderer, SchemaRenderer):
                adapter = renderer.get_adapter(renderer_ctx)
                components.update(self._translate_adapter(adapter).components)

        return components

    def get_request_body(self, path: str, method: str) -> dict[str, ty.Any]:
        if method not in ("PUT", "PATCH", "POST"):
            return {}

        self.request_media_types = self.map_parsers(path, method)
        serializer = self.get_request_serializer(path, method)
        content_schemas = {}

        for request_type in self.request_media_types:
            if isinstance(request_type, tuple):
                media_type, request_schema = request_type
                content_schemas[media_type] = {"schema": request_schema}
            else:
                serializer_ref = (
                    self.get_reference(serializer) if isinstance(serializer, serializers.Serializer) else {}
                )
                content_schemas[request_type] = {"schema": serializer_ref}

        return {"content": content_schemas}

    def get_responses(self, path: str, method: str) -> dict[str, ty.Any]:
        if method == "DELETE":
            return {"204": {"description": ""}}

        self.response_media_types = self.map_renderers(path, method)
        status_code = "201" if method == "POST" else "200"
        content_types = {}
        list_view = is_list_view(path, method, self.view)

        for response_type in self.response_media_types:
            if isinstance(response_type, tuple):
                media_type, response_schema = response_type
                if list_view and response_schema:
                    response_schema = self._wrap_list_response_schema(response_schema)
                content_types[media_type] = {"schema": response_schema}
            else:
                response_schema = self._get_serializer_response_schema(path, method)
                content_types[response_type] = {"schema": response_schema}

        return {
            status_code: {
                "content": content_types,
                "description": "",
            }
        }

    def get_reference(self, serializer: serializers.BaseSerializer) -> dict[str, str]:
        try:
            get_reference = super().get_reference
        except AttributeError:
            get_reference = super()._get_reference  # type: ignore

        return get_reference(serializer)

    def _wrap_list_response_schema(self, schema: dict[str, ty.Any]) -> dict[str, ty.Any]:
        response_schema = schema if schema.get("type") == "array" else {"type": "array", "items": schema}
        paginator: BasePagination = self.get_paginator()  # type: ignore
        if paginator:
            response_schema = paginator.get_paginated_response_schema(response_schema)
        return response_schema

    def _get_serializer_response_schema(self, path: str, method: str) -> dict[str, ty.Any]:
        serializer = self.get_response_serializer(path, method)
        item_schema = self.get_reference(serializer) if isinstance(serializer, serializers.Serializer) else {}
        if is_list_view(path, method, self.view):
            return self._wrap_list_response_schema(item_schema)
        return item_schema
