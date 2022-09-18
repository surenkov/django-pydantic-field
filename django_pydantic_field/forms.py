import pydantic
import typing as t
from functools import partial

from django.core.exceptions import ValidationError
from django.forms.fields import JSONField, InvalidJSONInput

from . import base, utils

__all__ = ("SchemaField",)


class SchemaField(JSONField, t.Generic[base.ST]):
    _is_prepared_field: bool = False

    def __init__(
        self,
        schema: t.Union[t.Type["base.ST"], t.ForwardRef],
        config: t.Optional["base.ConfigType"] = None,
        __module__: str = None,
        **kwargs
    ):
        self.schema = base.wrap_schema(
            schema,
            config,
            allow_null=not kwargs.get("required", True),
            __module__=__module__,
        )
        export_params = base.extract_export_kwargs(kwargs)
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
        except pydantic.ValidationError as e:
            return InvalidJSONInput(data)

    def get_bound_field(self, form, field_name):
        if not self._is_prepared_field:
            self._prepare_field(form)
        return super().get_bound_field(form, field_name)

    def _prepare_field(self, form):
        form_ns = utils.get_local_namespace(form)
        self.schema.update_forward_refs(**form_ns)
        self._is_prepared_field = True
