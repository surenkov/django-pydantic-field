from __future__ import annotations

import typing as ty

import pydantic
from rest_framework import exceptions, fields

from django_pydantic_field._internal._rest_framework import bind_serializer_field, register_serializer_field
from django_pydantic_field.compat import deprecation
from django_pydantic_field.v2 import types

if ty.TYPE_CHECKING:
    from collections.abc import Mapping

    from rest_framework.serializers import BaseSerializer

    RequestResponseContext = Mapping[str, ty.Any]


class SchemaField(fields.Field, ty.Generic[types.ST]):
    adapter: types.SchemaAdapter

    if ty.TYPE_CHECKING:

        @ty.overload
        def __new__(
            cls,
            schema: type[types.ST],
            config: pydantic.ConfigDict | None = None,
            **kwargs: ty.Any,
        ) -> SchemaField[types.ST]: ...
        @ty.overload
        def __new__(
            cls,
            schema: ty.ForwardRef | str,
            config: pydantic.ConfigDict | None = None,
            **kwargs: ty.Any,
        ) -> SchemaField[ty.Any]: ...
        @ty.overload
        def __new__(
            cls,
            schema: None = None,
            config: pydantic.ConfigDict | None = None,
            **kwargs: ty.Any,
        ) -> ty.Any: ...
        @ty.overload
        def __new__(
            cls,
            schema: ty.Any,
            config: pydantic.ConfigDict | None = None,
            **kwargs: ty.Any,
        ) -> SchemaField[ty.Any]: ...

    def __init__(
        self,
        schema: type[types.ST] | ty.ForwardRef | str | ty.Any = None,
        config: pydantic.ConfigDict | None = None,
        **kwargs,
    ):
        kwargs.pop("encoder", None)
        kwargs.pop("decoder", None)
        deprecation.truncate_deprecated_v1_export_kwargs(kwargs)
        allow_null = kwargs.get("allow_null", False)

        self.schema = schema
        self.config = config
        self.export_kwargs = types.SchemaAdapter.extract_export_kwargs(kwargs)
        self.adapter = types.SchemaAdapter(schema, config, None, None, allow_null, **self.export_kwargs)
        super().__init__(**kwargs)

    def bind(self, field_name: str, parent: BaseSerializer):
        super().bind(field_name, parent)
        bind_serializer_field(self, field_name, parent)

    def to_internal_value(self, data: ty.Any):
        try:
            if isinstance(data, (str, bytes)):
                return self.adapter.validate_json(data)
            return self.adapter.validate_python(data)
        except pydantic.ValidationError as exc:
            raise exceptions.ValidationError(ty.cast(ty.Any, exc.errors()), code="invalid")

    def to_representation(self, value: ty.Optional[types.ST]):
        try:
            prep_value = self.adapter.validate_python(value)
            return self.adapter.dump_python(prep_value)
        except pydantic.ValidationError as exc:
            raise exceptions.ValidationError(ty.cast(ty.Any, exc.errors()), code="invalid")


register_serializer_field()
