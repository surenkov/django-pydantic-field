from __future__ import annotations

import typing as ty

import pydantic
from rest_framework import exceptions, fields

from django_pydantic_field.compat import deprecation
from django_pydantic_field.v2 import types

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
        **kwargs,
    ):
        deprecation.truncate_deprecated_v1_export_kwargs(kwargs)
        allow_null = kwargs.get("allow_null", False)

        self.schema = schema
        self.config = config
        self.export_kwargs = types.SchemaAdapter.extract_export_kwargs(kwargs)
        self.adapter = types.SchemaAdapter(schema, config, None, None, allow_null, **self.export_kwargs)
        super().__init__(**kwargs)

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
