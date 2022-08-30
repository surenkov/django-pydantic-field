import typing as t
from contextlib import suppress

from pydantic import BaseModel, ValidationError
from rest_framework import serializers, parsers, renderers, exceptions
from django.conf import settings

from . import base

__all__ = "PydanticSchemaField", "PydanticSchemaRenderer", "PydanticSchemaParser"


class AnnotatedSchemaT(base.SchemaWrapper[base.ST]):
    _schema: t.Type[BaseModel]
    schema_ctx_attr: t.ClassVar[str] = "schema"

    def get_schema(self, ctx) -> t.Type[BaseModel]:
        with suppress(AttributeError):
            return self._schema

        schema = ctx.get(self.schema_ctx_attr)
        if schema is None:
            with suppress(AttributeError, IndexError):
                schema = t.get_args(self.__orig_class__)[0]  # type: ignore

        if schema is not None:
            schema = self._wrap_schema(schema)

        self.output_schema = schema
        return schema


class PydanticSchemaField(base.SchemaWrapper[base.ST], serializers.Field):
    def __init__(
        self,
        schema: t.Type[base.ST],
        config: t.Optional[base.ConfigType] = None,
        **kwargs,
    ):
        self.schema = field_schema = self._wrap_schema(schema, config)
        self.decoder = base.SchemaDecoder[base.ST](field_schema, serializer_error_handler)
        self.export_cfg = self._extract_export_kwargs(kwargs, dict.pop)
        super().__init__(**kwargs)

    def to_internal_value(self, data) -> t.Optional[base.ST]:
        return self.decoder.decode(data)

    def to_representation(self, value):
        obj = self.schema.parse_obj(value)
        raw_obj = obj.dict(**self.export_cfg)
        return raw_obj["__root__"]


class PydanticSchemaRenderer(AnnotatedSchemaT[base.ST], renderers.JSONRenderer):
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

        export_kw = self._extract_export_kwargs(renderer_ctx)
        json_str = data.json(**export_kw)
        return json_str.encode()


class PydanticSchemaParser(AnnotatedSchemaT[base.ST], parsers.JSONParser):
    schema_ctx_attr = "parser_schema"
    renderer_class = PydanticSchemaRenderer

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)
        schema = self.get_schema(parser_context)

        try:
            return schema.parse_raw(stream.read(), encoding=encoding).__root__
        except ValidationError as e:
            raise exceptions.ParseError(e.errors())


def serializer_error_handler(obj, err):
    raise exceptions.ValidationError(err[1])
