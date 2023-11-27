from __future__ import annotations

import typing as ty

import pydantic
from rest_framework import exceptions, fields, parsers, renderers
from rest_framework.schemas import coreapi

from ..compat.deprecation import truncate_deprecated_v1_export_kwargs
from ..compat.typing import get_args
from . import types

if ty.TYPE_CHECKING:
    from collections.abc import Mapping

    from rest_framework.serializers import BaseSerializer

    RequestResponseContext = Mapping[str, ty.Any]


class SchemaField(fields.Field, ty.Generic[types.ST]):
    adapter: types.SchemaAdapter

    def __init__(
        self,
        schema: type[types.ST],
        config: pydantic.ConfigDict | None = None,
        *args,
        allow_null: bool = False,
        **kwargs,
    ):
        truncate_deprecated_v1_export_kwargs(kwargs)
        self.schema = schema
        self.config = config
        self.export_kwargs = types.SchemaAdapter.extract_export_kwargs(kwargs)
        self.adapter = types.SchemaAdapter(schema, config, None, None, allow_null, **self.export_kwargs)
        super().__init__(*args, **kwargs)

    def bind(self, field_name: str, parent: BaseSerializer):
        if not self.adapter.is_bound:
            self.adapter.bind(type(parent), field_name)
        super().bind(field_name, parent)

    def to_internal_value(self, data: ty.Any):
        try:
            if isinstance(data, (str, bytes)):
                return self.adapter.validate_json(data)
            return self.adapter.validate_python(data)
        except pydantic.ValidationError as exc:
            raise exceptions.ValidationError(exc.errors(), code="invalid")  # type: ignore

    def to_representation(self, value: ty.Optional[types.ST]):
        try:
            prep_value = self.adapter.validate_python(value)
            return self.adapter.dump_python(prep_value)
        except pydantic.ValidationError as exc:
            raise exceptions.ValidationError(exc.errors(), code="invalid")  # type: ignore


class _AnnotatedAdapterMixin(ty.Generic[types.ST]):
    schema_context_key: ty.ClassVar[str] = "response_schema"
    config_context_key: ty.ClassVar[str] = "response_schema_config"

    def get_adapter(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        adapter = self._make_adapter_from_context(ctx)
        if adapter is None:
            adapter = self._make_adapter_from_annotation(ctx)

        return adapter

    def _make_adapter_from_context(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        schema = ctx.get(self.schema_context_key)
        if schema is not None:
            config = ctx.get(self.config_context_key)
            export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(ctx))
            return types.SchemaAdapter(schema, config, type(ctx.get("view")), None, **export_kwargs)

        return schema

    def _make_adapter_from_annotation(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        try:
            schema = get_args(self.__orig_class__)[0]  # type: ignore
        except (AttributeError, IndexError):
            return None

        config = ctx.get(self.config_context_key)
        export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(ctx))
        return types.SchemaAdapter(schema, config, type(ctx.get("view")), None, **export_kwargs)


class SchemaRenderer(_AnnotatedAdapterMixin[types.ST], renderers.JSONRenderer):
    schema_context_key = "renderer_schema"
    config_context_key = "renderer_config"

    def render(self, data: ty.Any, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        if response is not None and response.exception:
            return super().render(data, accepted_media_type, renderer_context)

        adapter = self.get_adapter(renderer_context)
        if adapter is None and isinstance(data, pydantic.BaseModel):
            return self.render_pydantic_model(data, renderer_context)
        if adapter is None:
            raise RuntimeError("Schema should be either explicitly set with annotation or passed in the context")

        try:
            prep_data = adapter.validate_python(data)
            return adapter.dump_json(prep_data)
        except pydantic.ValidationError as exc:
            return exc.json(indent=True, include_input=True).encode()

    def render_pydantic_model(self, instance: pydantic.BaseModel, renderer_context: Mapping[str, ty.Any]):
        export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(renderer_context))
        export_kwargs.pop("strict", None)
        export_kwargs.pop("from_attributes", None)
        export_kwargs.pop("mode", None)

        json_dump = instance.model_dump_json(**export_kwargs)  # type: ignore
        return json_dump.encode()


class SchemaParser(_AnnotatedAdapterMixin[types.ST], parsers.JSONParser):
    schema_context_key = "parser_schema"
    config_context_key = "parser_config"
    renderer_class = SchemaRenderer

    def parse(self, stream: ty.IO[bytes], media_type=None, parser_context=None):
        parser_context = parser_context or {}
        adapter = self.get_adapter(parser_context)
        if adapter is None:
            raise RuntimeError("Schema should be either explicitly set with annotation or passed in the context")

        try:
            return adapter.validate_json(stream.read())
        except pydantic.ValidationError as exc:
            raise exceptions.ParseError(exc.errors())  # type: ignore


class AutoSchema(coreapi.AutoSchema):
    """Not implemented yet."""
