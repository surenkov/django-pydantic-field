from __future__ import annotations

import typing as ty

import pydantic
from pydantic.json_schema import GenerateJsonSchema
from rest_framework import exceptions, parsers, renderers, serializers
from rest_framework.schemas import openapi
from rest_framework.schemas.utils import is_list_view

from .serialization import SchemaDecoder, prepare_export_params
from .type_utils import SchemaT, cached_property, type_adapter

__all__ = (
    "SchemaField",
    "SchemaRenderer",
    "SchemaParser",
    "AutoSchema",
)

if ty.TYPE_CHECKING:
    RequestResponseContext = ty.Mapping[str, ty.Any]


class AnnotatedSchemaT(ty.Generic[SchemaT]):
    schema_ctx_attr: ty.ClassVar[str] = "schema"
    schema_generator: ty.ClassVar[type[GenerateJsonSchema]] = GenerateJsonSchema

    require_explicit_schema: ty.ClassVar[bool] = False
    by_alias_ctx_attr: ty.ClassVar[str] = "by_alias"
    by_alias_default: ty.ClassVar[bool] = False

    _cached_annotation_schema: type[SchemaT]

    def get_type_adapter(self, ctx: RequestResponseContext) -> pydantic.TypeAdapter[SchemaT]:
        schema = self.get_schema(ctx)
        return type_adapter(schema)

    def get_json_schema(self, ctx: RequestResponseContext):
        adapter = self.get_type_adapter(ctx)
        return adapter.json_schema(by_alias=ctx.get(self.by_alias_ctx_attr, self.by_alias_default))

    def get_schema(self, ctx: RequestResponseContext) -> type[SchemaT] | None:
        schema = ctx.get(self.schema_ctx_attr)
        if schema is None:
            schema = self.get_annotation_schema()

        if self.require_explicit_schema and schema is None:
            raise ValueError("Schema should be either explicitly set with annotation or passed in the context")

        return schema  # type: ignore

    def get_annotation_schema(self):
        try:
            schema = self._cached_annotation_schema
        except AttributeError:
            try:
                schema = ty.get_args(self.__orig_class__)[0]  # type: ignore [missing-attr]
            except (AttributeError, IndexError):
                return None

            self._cached_annotation_schema = schema

        return schema


class SchemaField(serializers.Field, ty.Generic[SchemaT]):
    def __init__(
        self,
        schema: type[SchemaT],
        config: pydantic.ConfigDict | None = None,
        **kwargs,
    ):
        self.schema: type[SchemaT] = schema
        self.config = config
        self.export_params = prepare_export_params(kwargs, dict.pop)
        super().__init__(**kwargs)

    def to_internal_value(self, data: ty.Any) -> SchemaT | None:
        try:
            return self.decoder.decode(data)
        except pydantic.ValidationError as e:
            raise serializers.ValidationError(e.errors(), self.field_name)

    def to_representation(self, value: SchemaT) -> ty.Any:
        return self._type_adapter.dump_python(value, **self.export_params)

    def get_json_schema(self):
        return self._type_adapter.json_schema(by_alias=self.export_params.get("by_alias", False))

    @cached_property
    def decoder(self):
        return SchemaDecoder(self._type_adapter)

    @cached_property
    def _type_adapter(self) -> pydantic.TypeAdapter[SchemaT]:
        return type_adapter(self.schema, self.config, allow_null=self.allow_null)


class SchemaRenderer(AnnotatedSchemaT[SchemaT], renderers.JSONRenderer):
    schema_ctx_attr = "render_schema"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        if response is not None and response.exception:
            return super().render(data, accepted_media_type, renderer_context)

        try:
            json_str = self.render_data(data, renderer_context)
        except pydantic.ValidationError as e:
            json_str = e.json().encode()
        except AttributeError:
            json_str = super().render(data, accepted_media_type, renderer_context)

        return json_str

    def render_data(self, data, renderer_ctx) -> bytes:
        adapter = type_adapter(self.get_schema(renderer_ctx))
        export_kw = prepare_export_params(renderer_ctx)
        return adapter.dump_json(data, **export_kw)


class SchemaParser(AnnotatedSchemaT[SchemaT], parsers.JSONParser):
    schema_ctx_attr = "parser_schema"
    renderer_class = SchemaRenderer
    require_explicit_schema = True

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        adapter = type_adapter(self.get_schema(parser_context))
        try:
            return adapter.validate_json(stream.read())
        except pydantic.ValidationError as e:
            raise exceptions.ParseError(e.errors())


class AutoSchema(openapi.AutoSchema):
    get_request_serializer: ty.Callable

    def map_field(self, field: serializers.Field):
        if isinstance(field, SchemaField):
            return field.get_json_schema()
        return super().map_field(field)

    def map_parsers(self, path: str, method: str):
        request_types: list[ty.Any] = []

        for parser_type in self.view.parser_classes:
            parser = parser_type()

            if isinstance(parser, SchemaParser):
                parser_ctx = self.view.get_parser_context(None)
                schema = parser.get_json_schema(parser_ctx)
                if schema is not None:
                    request_types.append((parser.media_type, schema))
                else:
                    request_types.append(parser.media_type)
            else:
                request_types.append(parser.media_type)

        return request_types

    def map_renderers(self, path: str, method: str):
        response_types: list[ty.Any] = []

        for renderer_type in self.view.renderer_classes:
            renderer = renderer_type()

            if isinstance(renderer, SchemaRenderer):
                renderer_ctx = self.view.get_renderer_context()
                schema = renderer.get_json_schema(renderer_ctx)
                if schema is not None:
                    response_types.append((renderer.media_type, schema))
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
                try:
                    serializer_ref = self.get_reference(serializer)  # type: ignore
                except AttributeError:
                    # For compatibility with elder rest framework
                    serializer_ref = self._get_reference(serializer)  # type: ignore
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

    def _get_serializer_response_schema(self, path, method):
        serializer = self.get_response_serializer(path, method)

        if not isinstance(serializer, serializers.Serializer):
            item_schema = {}
        else:
            try:
                item_schema = self.get_reference(serializer)  # type: ignore
            except AttributeError:
                # For compatibility with elder rest framework
                item_schema = self._get_reference(serializer)  # type: ignore

        if is_list_view(path, method, self.view):
            response_schema = {"type": "array", "items": item_schema}
            paginator = self.get_paginator()
            if paginator:
                response_schema = paginator().get_paginated_response_schema(response_schema)
        else:
            response_schema = item_schema
        return response_schema
