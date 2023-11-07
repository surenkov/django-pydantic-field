from __future__ import annotations

import typing as ty
from collections import ChainMap
from django.forms import BaseForm, ModelForm

import pydantic
from django.core.exceptions import ValidationError
from django.forms.fields import JSONField, JSONString, InvalidJSONInput
from django.utils.translation import gettext_lazy as _

from . import types, utils


class SchemaField(JSONField, ty.Generic[types.ST]):
    adapter: types.SchemaAdapter
    default_error_messages = {
        "schema_error": _("Schema didn't match for %(title)s."),
    }

    def __init__(self, schema: types.ST | ty.ForwardRef, config: pydantic.ConfigDict | None = None, *args, **kwargs):
        self.schema = schema
        self.export_kwargs = types.SchemaAdapter.extract_export_kwargs(kwargs)
        allow_null = None in self.empty_values
        self.adapter = types.SchemaAdapter(schema, config, None, None, allow_null=allow_null, **self.export_kwargs)
        super().__init__(*args, **kwargs)

    def get_bound_field(self, form: ty.Any, field_name: str):
        if not self.adapter.is_bound:
            self._bind_schema_adapter(form, field_name)
        return super().get_bound_field(form, field_name)

    def bound_data(self, data: ty.Any, initial: ty.Any):
        if self.disabled:
            return initial
        if data is None:
            return None
        try:
            return self.adapter.validate_json(data)
        except pydantic.ValidationError:
            return InvalidJSONInput(data)

    def to_python(self, value: ty.Any) -> ty.Any:
        if self.disabled:
            return value
        if value in self.empty_values:
            return None
        elif isinstance(value, JSONString):
            return value
        try:
            converted = self.adapter.validate_json(value)
        except pydantic.ValidationError as exc:
            error_params = {"value": value, "title": exc.title, "detail": exc.json(), "errors": exc.errors()}
            raise ValidationError(self.error_messages["schema_error"], code="invalid", params=error_params) from exc

        if isinstance(converted, str):
            return JSONString(converted)

        return converted

    def prepare_value(self, value):
        if isinstance(value, InvalidJSONInput):
            return value

        value = self.adapter.validate_python(value)
        return self.adapter.dump_json(value).decode()

    def has_changed(self, initial: ty.Any | None, data: ty.Any | None) -> bool:
        if super(JSONField, self).has_changed(initial, data):
            return True
        return self.adapter.dump_json(initial) != self.adapter.dump_json(data)

    def _bind_schema_adapter(self, form: BaseForm, field_name: str):
        modelns = None
        if isinstance(form, ModelForm):
            modelns = ChainMap(
                utils.get_local_namespace(form._meta.model),
                utils.get_global_namespace(form._meta.model),
            )
        self.adapter.bind(form, field_name, modelns)
