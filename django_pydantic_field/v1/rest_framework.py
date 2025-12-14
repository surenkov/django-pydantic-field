from __future__ import annotations


import typing as ty

from django.conf import settings
from pydantic import BaseModel, ValidationError
from rest_framework import exceptions, parsers, renderers, serializers
from rest_framework.pagination import BasePagination
from rest_framework.schemas import openapi
from rest_framework.schemas.utils import is_list_view

from django_pydantic_field.compat.typing import get_args

from . import base

if ty.TYPE_CHECKING:
    from django_pydantic_field.v1.base import ST, SchemaDecoder, ConfigType

    RequestResponseContext = ty.Mapping[str, ty.Any]

__all__ = (
    "SchemaField",
    "SchemaRenderer",
    "SchemaParser",
    "AutoSchema",
)


class AnnotatedSchemaT(ty.Generic[ST]):
    schema_ctx_attr: ty.ClassVar[str] = "schema"
    require_explicit_schema: ty.ClassVar[bool] = False
    _cached_annotation_schema: ty.Type[BaseModel]

    def get_schema(self, ctx: RequestResponseContext) -> ty.Optional[ty.Type[BaseModel]]:
        schema = self.get_context_schema(ctx)
        if schema is None:
            schema = self.get_annotation_schema(ctx)

        if self.require_explicit_schema and schema is None:
            raise ValueError("Schema should be either explicitly set with annotation or passed in the context")

        return schema

    def get_context_schema(self, ctx: RequestResponseContext):
        schema = ctx.get(self.schema_ctx_attr)
        if schema is not None:
            schema = base.wrap_schema(schema)
            base.prepare_schema(schema, ctx.get("view"))

        return schema

    def get_annotation_schema(self, ctx: RequestResponseContext):
        try:
            schema = self._cached_annotation_schema
        except AttributeError:
            try:
                schema = get_args(self.__orig_class__)[0]  # type: ignore
            except (AttributeError, IndexError):
                return None

            self._cached_annotation_schema = schema = base.wrap_schema(schema)
            base.prepare_schema(schema, ctx.get("view"))

        return schema


class SchemaField(serializers.Field, ty.Generic[ST]):
    decoder: SchemaDecoder[ST]
    _is_prepared_schema: bool = False

    def __init__(
        self,
        schema: ty.Type[ST],
        config: ty.Optional[ConfigType] = None,
        **kwargs,
    ):
        nullable = kwargs.get("allow_null", False)

        self.schema = field_schema = base.wrap_schema(schema, config, nullable)
        self.export_params = base.extract_export_kwargs(kwargs, dict.pop)
        self.decoder = base.SchemaDecoder(field_schema)
        super().__init__(**kwargs)

    def bind(self, field_name, parent):
        if not self._is_prepared_schema:
            base.prepare_schema(self.schema, parent)
            self._is_prepared_schema = True

        super().bind(field_name, parent)

    def to_internal_value(self, data: ty.Any) -> ty.Optional[ST]:
        try:
            return self.decoder.decode(data)
        except ValidationError as e:
            raise serializers.ValidationError(e.errors(), self.field_name)  # type: ignore[arg-type]

    def to_representation(self, value: ty.Optional[ST]) -> ty.Any:
        obj = self.schema.parse_obj(value)
        raw_obj = obj.dict(**self.export_params)
        return raw_obj["__root__"]


class SchemaRenderer(AnnotatedSchemaT[ST], renderers.JSONRenderer):
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


class SchemaParser(AnnotatedSchemaT[ST], parsers.JSONParser):
    schema_ctx_attr = "parser_schema"
    renderer_class = SchemaRenderer
    require_explicit_schema = True

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)
        schema = ty.cast(BaseModel, self.get_schema(parser_context))

        try:
            return schema.parse_raw(stream.read(), encoding=encoding).__root__  # type: ignore[unresolved-attribute]
        except ValidationError as e:
            raise exceptions.ParseError(e.errors())


class AutoSchema(openapi.AutoSchema):
    get_request_serializer: ty.Callable

    def map_field(self, field: serializers.Field):
        if isinstance(field, SchemaField):
            return field.schema.schema()  # type: ignore[unresolved-attribute]
        return super().map_field(field)

    def map_parsers(self, path: str, method: str):
        request_types: ty.List[ty.Any] = []
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
        response_types: ty.List[ty.Any] = []
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

    def _extract_openapi_schema(self, schemable: AnnotatedSchemaT, ctx: RequestResponseContext):
        schema_model = schemable.get_schema(ctx)
        if schema_model is not None:
            return schema_model.schema()  # type: ignore[unresolved-attribute]
        return None

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
