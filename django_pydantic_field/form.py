import pydantic
import typing as t
from functools import partial

from django.core.exceptions import ValidationError
from django.forms.fields import JSONField, InvalidJSONInput

from . import base

__all__ = ("SchemaField",)


class SchemaField(JSONField, t.Generic[base.ST]):
    decoder: base.SchemaDecoder[base.ST]
    encoder: base.SchemaEncoder

    def __init__(
        self,
        schema: t.Type["base.ST"],
        config: t.Optional["base.ConfigType"] = None,
        **kwargs
    ):
        allow_null = not kwargs.get("required", True)
        bound_schema = base.wrap_schema(schema, config, allow_null)
        export_params = base.extract_export_kwargs(kwargs)

        decoder = partial(base.SchemaDecoder, bound_schema)
        encoder = partial(
            base.SchemaEncoder,
            schema=bound_schema,
            export=export_params,
            raise_errors=True,
        )
        kwargs.update(encoder=encoder, decoder=decoder)
        super().__init__(**kwargs)

    def to_python(self, value):
        try:
            return super().to_python(value)
        except pydantic.ValidationError as e:
            raise ValidationError(e.errors(), code="invalid")

    def bound_data(self, data, initial):
        try:
            return super().bound_data(data, initial)
        except pydantic.ValidationError as e:
            return InvalidJSONInput(data)
