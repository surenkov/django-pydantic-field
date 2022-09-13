import typing as t
from contextlib import suppress

from pydantic import BaseModel, ValidationError
from django.conf import settings

from rest_framework import serializers, parsers, renderers, exceptions
from rest_framework.schemas import openapi
from rest_framework.schemas.utils import is_list_view

from . import base

__all__ = (
    "SchemaField",
    "SchemaRenderer",
    "SchemaParser",
    "AutoSchema",
)

if t.TYPE_CHECKING:
    RequestResponseContext = t.Dict[str, t.Any]


class AnnotatedSchemaT(t.Generic[base.ST]):
    schema_ctx_attr: t.ClassVar[str] = "schema"
    require_explicit_schema: t.ClassVar[bool] = False
    _cached_annotation_schema: t.Type[BaseModel]

    def get_schema(self, ctx: "RequestResponseContext"):
        schema = self.get_context_schema(ctx)
        if schema is None:
            schema = self.get_annotation_schema()

        if self.require_explicit_schema and schema is None:
            raise ValueError(
                "Schema should be either explicitly set with annotation "
                "or passed in the context"
            )

        return schema

    def get_context_schema(self, ctx: "RequestResponseContext") -> t.Optional[t.Type[BaseModel]]:
        schema = ctx.get(self.schema_ctx_attr)
        if schema is not None:
            schema = base.wrap_schema(schema)

        return schema

    def get_annotation_schema(self) -> t.Optional[t.Type[BaseModel]]:
        with suppress(AttributeError):
            return self._cached_annotation_schema

        try:
            schema = t.get_args(self.__orig_class__)[0]  # type: ignore
        except (AttributeError, IndexError):
            return None

        schema = base.wrap_schema(schema)
        self._cached_annotation_schema = schema
        return schema


class SchemaField(serializers.Field, t.Generic[base.ST]):
    decoder: "base.SchemaDecoder[base.ST]"

    def __init__(
        self,
        schema: t.Type["base.ST"],
        config: t.Optional["base.ConfigType"] = None,
        **kwargs,
    ):
        nullable = kwargs.get("allow_null", False)

        self.schema = field_schema = base.wrap_schema(schema, config, nullable)
        self.export_params = base.extract_export_kwargs(kwargs, dict.pop)
        self.decoder = base.SchemaDecoder(field_schema)

        super().__init__(**kwargs)

    def to_internal_value(self, data) -> t.Optional["base.ST"]:
        try:
            return self.decoder.decode(data)
        except ValidationError as e:
            raise serializers.ValidationError(e.errors(), self.field_name)

    def to_representation(self, value):
        obj = self.schema.parse_obj(value)
        raw_obj = obj.dict(**self.export_params)
        return raw_obj["__root__"]


class SchemaRenderer(AnnotatedSchemaT[base.ST], renderers.JSONRenderer):
    schema_ctx_attr = "render_schema"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        if response is not None and response.exception:
            return super().render(data, accepted_media_type, renderer_context)

        try:
            json_str = self.render_data(data, renderer_context)
        except ValidationError as e:
            json_str = e.json().encode()
        except AttributeError:
            json_str = super().render(data, accepted_media_type, renderer_context)

        return json_str

    def render_data(self, data, renderer_ctx) -> bytes:
        schema = self.get_schema(renderer_ctx or {})
        if schema is not None:
            data = schema(__root__=data)

        export_kw = base.extract_export_kwargs(renderer_ctx)
        json_str = data.json(**export_kw, ensure_ascii=self.ensure_ascii)
        return json_str.encode()


class SchemaParser(AnnotatedSchemaT[base.ST], parsers.JSONParser):
    schema_ctx_attr = "parser_schema"
    renderer_class = SchemaRenderer
    require_explicit_schema = True

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)
        schema = t.cast(BaseModel, self.get_schema(parser_context))

        try:
            return schema.parse_raw(stream.read(), encoding=encoding).__root__
        except ValidationError as e:
            raise exceptions.ParseError(e.errors())


class AutoSchema(openapi.AutoSchema):
    get_request_serializer: t.Callable
    _get_reference: t.Callable

    def map_field(self, field: serializers.Field):
        if isinstance(field, SchemaField):
            return field.schema.schema()
        return super().map_field(field)

    def map_parsers(self, path: str, method: str):
        request_types: t.List[t.Any] = []
        parser_ctx = self.view.get_parser_context(None)

        for parser_type in self.view.parser_classes:
            parser = parser_type()

            if isinstance(parser, SchemaParser):
                schema = self._extract_openapi_schema(parser, parser_ctx)
                if schema is not None:
                    request_types.append((parser.media_type, schema))
                else:
                    request_types.append(parser.media_type)
            else:
                request_types.append(parser.media_type)

        return request_types

    def map_renderers(self, path: str, method: str):
        response_types: t.List[t.Any] = []
        renderer_ctx = self.view.get_renderer_context()

        for renderer_type in self.view.renderer_classes:
            renderer = renderer_type()

            if isinstance(renderer, SchemaRenderer):
                schema = self._extract_openapi_schema(renderer, renderer_ctx)
                if schema is not None:
                    response_types.append((renderer.media_type, schema))
                else:
                    response_types.append(renderer.media_type)

            elif not isinstance(renderer, renderers.BrowsableAPIRenderer):
                response_types.append(renderer.media_type)

        return response_types

    def get_request_body(self, path: str, method: str):
        if method not in ('PUT', 'PATCH', 'POST'):
            return {}

        self.request_media_types = self.map_parsers(path, method)
        serializer = self.get_request_serializer(path, method)
        content_schemas = {}

        for request_type in self.request_media_types:
            if isinstance(request_type, tuple):
                media_type, request_schema = request_type
                content_schemas[media_type] = {"schema": request_schema}
            else:
                serializer_ref =  self._get_reference(serializer)
                content_schemas[request_type] = {"schema": serializer_ref}

        return {'content': content_schemas}

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

    def _extract_openapi_schema(self, schemable: AnnotatedSchemaT, ctx: "RequestResponseContext"):
        schema_model = schemable.get_schema(ctx)
        if schema_model is not None:
            return schema_model.schema()
        return None

    def _get_serializer_response_schema(self, path, method):
        serializer = self.get_response_serializer(path, method)

        if not isinstance(serializer, serializers.Serializer):
            item_schema = {}
        else:
            item_schema = self._get_reference(serializer)

        if is_list_view(path, method, self.view):
            response_schema = {
                "type": "array",
                "items": item_schema,
            }
            paginator = self.get_paginator()
            if paginator:
                response_schema = paginator.get_paginated_response_schema(response_schema)
        else:
            response_schema = item_schema
        return response_schema
