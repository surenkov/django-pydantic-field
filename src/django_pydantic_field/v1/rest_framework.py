from __future__ import annotations

import typing as ty

from rest_framework import exceptions, parsers, renderers, serializers
from rest_framework.pagination import BasePagination
from rest_framework.schemas import openapi
from rest_framework.schemas.utils import is_list_view

from django_pydantic_field.compat.pydantic import pydantic_v1
from django_pydantic_field.compat.typing import get_args
from django_pydantic_field.v1 import types

if ty.TYPE_CHECKING:
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
    require_explicit_schema: ty.ClassVar[bool] = False

    def get_adapter(self, ctx: RequestResponseContext) -> ty.Optional[types.SchemaAdapter[types.ST]]:
        schema = ctx.get(self.schema_ctx_attr)
        parent = ctx.get("view")

        if schema is not None:
            config = ctx.get("config")
            export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(ctx))
            adapter = types.SchemaAdapter(schema, config, type(parent) if parent else None, None, **export_kwargs)
            return adapter

        try:
            schema = get_args(self.__orig_class__)[0]  # type: ignore
        except (AttributeError, IndexError):
            schema = None

        if self.require_explicit_schema and schema is None:
            raise ValueError("Schema should be either explicitly set with annotation or passed in the context")

        if schema is not None:
            config = ctx.get("config")
            export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(ctx))
            adapter = types.SchemaAdapter(schema, config, type(parent) if parent else None, None, **export_kwargs)
            return adapter

        return None


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
            raise serializers.ValidationError(e.errors())

    def to_representation(self, value: ty.Optional[types.ST]) -> ty.Any:
        return self.adapter.dump_python(value)


class SchemaRenderer(AnnotatedAdapterMixin[types.ST], renderers.JSONRenderer):
    schema_ctx_attr = "render_schema"

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

        try:
            return adapter.validate_json(stream.read())
        except pydantic_v1.ValidationError as e:
            raise exceptions.ParseError(e.errors())


class AutoSchema(openapi.AutoSchema):
    get_request_serializer: ty.Callable

    def map_field(self, field: serializers.Field):
        if isinstance(field, SchemaField):
            return field.adapter.json_schema()
        return super().map_field(field)

    def map_parsers(self, path: str, method: str):
        request_types: ty.List[ty.Any] = []
        parser_ctx = self.view.get_parser_context(None)

        for parser_type in self.view.parser_classes:
            parser = parser_type()

            if isinstance(parser, SchemaParser):
                adapter = parser.get_adapter(parser_ctx)
                if adapter is not None:
                    request_types.append((parser.media_type, adapter.json_schema()))
                else:
                    request_types.append(parser.media_type)
            else:
                request_types.append(parser.media_type)

        return request_types

    def map_renderers(self, path: str, method: str):
        response_types: ty.List[ty.Any] = []
        renderer_ctx = self.view.get_renderer_context()

        for renderer_type in self.view.renderer_classes:
            renderer = renderer_type()

            if isinstance(renderer, SchemaRenderer):
                adapter = renderer.get_adapter(renderer_ctx)
                if adapter is not None:
                    response_types.append((renderer.media_type, adapter.json_schema()))
                else:
                    response_types.append(renderer.media_type)

            elif not isinstance(renderer, renderers.BrowsableAPIRenderer):
                response_types.append(renderer.media_type)

        return response_types

    def get_request_body(self, path: str, method: str):
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
                serializer_ref = self.get_reference(serializer)
                content_schemas[request_type] = {"schema": serializer_ref}

        return {"content": content_schemas}

    def get_responses(self, path: str, method: str):
        if method == "DELETE":
            return {"204": {"description": ""}}

        self.response_media_types = self.map_renderers(path, method)
        status_code = "201" if method == "POST" else "200"
        content_types = {}

        for response_type in self.response_media_types:
            if isinstance(response_type, tuple):
                media_type, response_schema = response_type
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

    def get_reference(self, serializer):
        try:
            get_reference = super().get_reference
        except AttributeError:
            get_reference = super()._get_reference  # type: ignore

        return get_reference(serializer)

    def _get_serializer_response_schema(self, path, method):
        serializer = self.get_response_serializer(path, method)

        if not isinstance(serializer, serializers.Serializer):
            item_schema = {}
        else:
            item_schema = self.get_reference(serializer)

        if is_list_view(path, method, self.view):
            response_schema: ty.Dict[str, ty.Any] = {
                "type": "array",
                "items": item_schema,
            }
            paginator: BasePagination = self.get_paginator()  # type: ignore
            if paginator:
                response_schema = paginator.get_paginated_response_schema(response_schema)
        else:
            response_schema = item_schema
        return response_schema
