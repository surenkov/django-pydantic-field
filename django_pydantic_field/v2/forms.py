from __future__ import annotations

import typing as ty

import pydantic
from django.core.exceptions import ValidationError
from django.forms.fields import InvalidJSONInput, JSONField, JSONString
from django.utils.translation import gettext_lazy as _

from django_pydantic_field.compat import deprecation
from . import types


class SchemaField(JSONField, ty.Generic[types.ST]):
    adapter: types.SchemaAdapter
    default_error_messages = {
        "schema_error": _("Schema didn't match for %(title)s."),
    }

    def __init__(
        self,
        schema: type[types.ST] | ty.ForwardRef | str,
        config: pydantic.ConfigDict | None = None,
        allow_null: bool | None = None,
        *args,
        **kwargs,
    ):
        deprecation.truncate_deprecated_v1_export_kwargs(kwargs)

        self.schema = schema
        self.config = config
        self.export_kwargs = types.SchemaAdapter.extract_export_kwargs(kwargs)
        self.adapter = types.SchemaAdapter(schema, config, None, None, allow_null, **self.export_kwargs)
        super().__init__(*args, **kwargs)

    def get_bound_field(self, form: ty.Any, field_name: str):
        if not self.adapter.is_bound:
            self.adapter.bind(form, field_name)
        return super().get_bound_field(form, field_name)

    def bound_data(self, data: ty.Any, initial: ty.Any):
        if self.disabled:
            return self.adapter.validate_python(initial)
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

        try:
            if not isinstance(value, str):
                # The form data may contain python objects for some cases (e.g. using django-constance).
                value = self.adapter.validate_python(value)
            elif not isinstance(value, JSONString):
                # Otherwise, try to parse incoming JSON accoring to the schema.
                value = self.adapter.validate_json(value)
        except pydantic.ValidationError as exc:
            error_params = {"value": value, "title": exc.title, "detail": exc.json(), "errors": exc.errors()}
            raise ValidationError(self.error_messages["schema_error"], code="invalid", params=error_params) from exc

        if isinstance(value, str):
            value = JSONString(value)

        return value

    def prepare_value(self, value):
        if isinstance(value, InvalidJSONInput):
            return value

        value = self.adapter.validate_python(value)
        return self.adapter.dump_json(value).decode()

    def has_changed(self, initial: ty.Any | None, data: ty.Any | None) -> bool:
        if super(JSONField, self).has_changed(initial, data):
            return True
        return self.adapter.dump_json(initial) != self.adapter.dump_json(data)
