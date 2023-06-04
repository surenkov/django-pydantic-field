from __future__ import annotations

import typing as ty

import pydantic
from django.core.exceptions import FieldError, ValidationError
from django.forms import BaseForm, BoundField
from django.forms.fields import InvalidJSONInput, JSONField

from .serialization import SchemaDecoder, SchemaEncoder, prepare_export_params
from .type_utils import SchemaT, cached_property, evaluate_forward_ref, get_type_annotation, type_adapter


class SchemaField(JSONField, ty.Generic[SchemaT]):
    def __init__(self, schema: type[SchemaT], config: pydantic.ConfigDict | None = None, **kwargs):
        self.schema: type[SchemaT] = schema
        self.config: pydantic.ConfigDict | None = config
        self.export_params = prepare_export_params(kwargs, dict.pop)

        super().__init__(**kwargs)
        del self.encoder
        del self.decoder

    def encoder(self, **kwargs) -> SchemaEncoder[SchemaT]:
        return SchemaEncoder(adapter=self._type_adapter, export_params=self.export_params, raise_errors=True, **kwargs)

    def decoder(self) -> SchemaDecoder[SchemaT]:
        return SchemaDecoder(self._type_adapter)

    def get_bound_field(self, form, field_name):
        return BoundSchemaField(form, self, field_name)

    def to_python(self, value):
        try:
            return super().to_python(value)
        except pydantic.ValidationError as e:
            # FIXME: fix validation error data: e.errors() failing for some reason
            raise ValidationError(e.json(), code="invalid")

    def bound_data(self, data, initial):
        try:
            return super().bound_data(data, initial)
        except pydantic.ValidationError:
            return InvalidJSONInput(data)

    def bind_schema(self, schema: type[SchemaT]):
        self.schema = schema
        self.__dict__.pop("_type_adapter", None)

    @cached_property
    def _type_adapter(self) -> pydantic.TypeAdapter[SchemaT]:
        return type_adapter(self.schema, self.config)


class BoundSchemaField(BoundField, ty.Generic[SchemaT]):
    field: SchemaField[SchemaT]

    def __init__(self, form: BaseForm, field: SchemaField[SchemaT], field_name: str):
        super().__init__(form, field, field_name)
        self._bind_schema()

    def _bind_schema(self):
        schema = self.field.schema
        if schema is None:
            self.field.bind_schema(self._get_annotatated_schema())
        elif isinstance(schema, ty.ForwardRef):
            self.field.bind_schema(self._evaluate_forward_ref(schema))

    def _get_annotatated_schema(self):
        try:
            return get_type_annotation(type(self.form), self.name)
        except KeyError:
            raise FieldError(
                f"{type(self.form)}.{self.name} needs to be either annotated or "
                "`schema=` field attribute should be explicitly passed"
            )

    def _evaluate_forward_ref(self, schema: ty.ForwardRef) -> type[SchemaT]:
        return evaluate_forward_ref(type(self.form), schema)
