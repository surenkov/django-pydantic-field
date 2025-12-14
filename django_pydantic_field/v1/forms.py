from __future__ import annotations

import typing as ty
from functools import partial

import pydantic
from django.core.exceptions import ValidationError
from django.forms.fields import InvalidJSONInput, JSONField
from django.utils.translation import gettext_lazy as _

from django_pydantic_field.v1 import base
from django_pydantic_field.v1.base import ST

if ty.TYPE_CHECKING:
    from django_pydantic_field.v1.base import SchemaDecoder, SchemaEncoder, ConfigType

__all__ = ("SchemaField",)


class SchemaField(JSONField, ty.Generic[ST]):
    default_error_messages = {
        "schema_error": _("Schema didn't match. Detail: %(detail)s"),
    }
    decoder: partial[SchemaDecoder]
    encoder: partial[SchemaEncoder]

    def __init__(
        self,
        schema: ty.Union[ty.Type[ST], ty.ForwardRef],
        config: ty.Optional[ConfigType] = None,
        __module__: ty.Optional[str] = None,
        **kwargs,
    ):
        self.schema = base.wrap_schema(
            schema,
            config,
            allow_null=not kwargs.get("required", True),
            __module__=__module__,
        )
        export_params = base.extract_export_kwargs(kwargs, dict.pop)
        decoder: partial[SchemaDecoder] = partial(base.SchemaDecoder, self.schema)
        encoder: partial[SchemaEncoder] = partial(
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
            raise ValidationError(
                self.error_messages["schema_error"],
                code="invalid",
                params={
                    "value": value,
                    "detail": str(e),
                    "errors": e.errors(),
                    "json": e.json(),
                },
            )

    def bound_data(self, data, initial):
        try:
            return super().bound_data(data, initial)
        except pydantic.ValidationError:
            return InvalidJSONInput(data)

    def get_bound_field(self, form, field_name):
        base.prepare_schema(self.schema, form)
        return super().get_bound_field(form, field_name)
