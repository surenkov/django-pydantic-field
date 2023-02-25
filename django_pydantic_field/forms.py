import typing as t
from functools import partial

import pydantic
from django.core.exceptions import ValidationError
from django.forms.fields import InvalidJSONInput, JSONField

from . import base

__all__ = ("SchemaField",)


class SchemaField(JSONField, t.Generic[base.ST]):
    def __init__(
        self,
        schema: t.Union[t.Type["base.ST"], t.ForwardRef],
        config: t.Optional["base.ConfigType"] = None,
        __module__: t.Optional[str] = None,
        **kwargs
    ):
        self.schema = base.wrap_schema(
            schema,
            config,
            allow_null=not kwargs.get("required", True),
            __module__=__module__,
        )
        export_params = base.extract_export_kwargs(kwargs, dict.pop)
        decoder = partial(base.SchemaDecoder, self.schema)
        encoder = partial(
            base.SchemaEncoder,
            schema=self.schema,
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
        except pydantic.ValidationError:
            return InvalidJSONInput(data)

    def get_bound_field(self, form, field_name):
        base.prepare_schema(self.schema, form)
        return super().get_bound_field(form, field_name)
