from __future__ import annotations

import typing as ty

import pydantic
from django.core import checks, exceptions
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.expressions import BaseExpression, Col, Value
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.json import JSONField
from django.db.models.lookups import Transform
from django.db.models.query_utils import DeferredAttribute

from django_pydantic_field.compat import deprecation
from django_pydantic_field.compat.django import GenericContainer

from . import forms, types

if ty.TYPE_CHECKING:
    import json
    import typing_extensions as te
    from django.db.models import Model

    class _SchemaFieldKwargs(types.ExportKwargs, total=False):
        # django.db.models.fields.Field kwargs
        name: str | None
        verbose_name: str | None
        primary_key: bool
        max_length: int | None
        unique: bool
        blank: bool
        db_index: bool
        rel: ty.Any
        editable: bool
        serialize: bool
        unique_for_date: str | None
        unique_for_month: str | None
        unique_for_year: str | None
        choices: ty.Sequence[ty.Tuple[str, str]] | None
        help_text: str | None
        db_column: str | None
        db_tablespace: str | None
        auto_created: bool
        validators: ty.Sequence[ty.Callable] | None
        error_messages: ty.Mapping[str, str] | None
        db_comment: str | None
        # django.db.models.fields.json.JSONField kwargs
        encoder: ty.Callable[[], json.JSONEncoder]
        decoder: ty.Callable[[], json.JSONDecoder]


__all__ = ("SchemaField",)


class SchemaAttribute(DeferredAttribute):
    field: PydanticSchemaField

    def __set_name__(self, owner, name):
        self.field.adapter.bind(owner, name)

    def __set__(self, obj, value):
        obj.__dict__[self.field.attname] = self.field.to_python(value)


class PydanticSchemaField(JSONField, ty.Generic[types.ST]):
    descriptor_class: type[DeferredAttribute] = SchemaAttribute
    adapter: types.SchemaAdapter

    def __init__(
        self,
        *args,
        schema: type[types.ST] | GenericContainer | ty.ForwardRef | str | None = None,
        config: pydantic.ConfigDict | None = None,
        **kwargs,
    ):
        kwargs.setdefault("encoder", DjangoJSONEncoder)
        self.export_kwargs = export_kwargs = types.SchemaAdapter.extract_export_kwargs(kwargs)
        super().__init__(*args, **kwargs)

        self.schema = GenericContainer.unwrap(schema)
        self.config = config
        self.adapter = types.SchemaAdapter(schema, config, None, self.get_attname(), self.null, **export_kwargs)

    def __copy__(self):
        _, _, args, kwargs = self.deconstruct()
        copied = self.__class__(*args, **kwargs)
        copied.set_attributes_from_name(self.name)
        return copied

    def deconstruct(self) -> ty.Any:
        field_name, import_path, args, kwargs = super().deconstruct()
        if import_path.startswith("django_pydantic_field.v2."):
            import_path = import_path.replace("django_pydantic_field.v2", "django_pydantic_field", 1)

        default = kwargs.get("default", NOT_PROVIDED)
        if default is not NOT_PROVIDED and not callable(default):
            kwargs["default"] = self.adapter.dump_python(default, include=None, exclude=None, round_trip=True)

        prep_schema = GenericContainer.wrap(self.adapter.prepared_schema)
        kwargs.update(schema=prep_schema, config=self.config, **self.export_kwargs)

        return field_name, import_path, args, kwargs

    def contribute_to_class(self, cls: types.DjangoModelType, name: str, private_only: bool = False) -> None:
        self.adapter.bind(cls, name)
        super().contribute_to_class(cls, name, private_only)

    def check(self, **kwargs: ty.Any) -> list[checks.CheckMessage]:
        # Remove checks of using mutable datastructure instances as `default` values, since they'll be adapted anyway.
        performed_checks = [check for check in super().check(**kwargs) if check.id != "fields.E010"]
        try:
            # Test that the schema could be resolved in runtime, even if it contains forward references.
            self.adapter.validate_schema()
        except types.ImproperlyConfiguredSchema as exc:
            message = f"Cannot resolve the schema. Original error: \n{exc.args[0]}"
            performed_checks.append(checks.Error(message, obj=self, id="pydantic.E001"))

        if self.has_default():
            try:
                # Test that the default value conforms to the schema.
                self.get_prep_value(self.get_default())
            except pydantic.ValidationError as exc:
                message = f"Default value cannot be adapted to the schema. Pydantic error: \n{str(exc)}"
                performed_checks.append(checks.Error(message, obj=self, id="pydantic.E002"))

        if {"include", "exclude"} & self.export_kwargs.keys():
            # Try to prepare the default value to test export ability against it.
            schema_default = self.get_default()
            if schema_default is None:
                # If the default value is not set, try to get the default value from the schema.
                prep_value = self.adapter.type_adapter.get_default_value()
                if prep_value is not None:
                    prep_value = prep_value.value
                schema_default = prep_value

            if schema_default is not None:
                try:
                    # Perform the full round-trip transformation to test the export ability.
                    self.adapter.validate_python(self.get_prep_value(self.default))
                except pydantic.ValidationError as exc:
                    message = f"Export arguments may lead to data integrity problems. Pydantic error: \n{str(exc)}"
                    hint = "Please review `import` and `export` arguments."
                    performed_checks.append(checks.Warning(message, obj=self, hint=hint, id="pydantic.E003"))

        return performed_checks

    def validate(self, value: ty.Any, model_instance: ty.Any) -> None:
        value = self.adapter.validate_python(value)
        return super(JSONField, self).validate(value, model_instance)

    def to_python(self, value: ty.Any):
        try:
            value = self.adapter.validate_json(value)
        except ValueError:
            """This is an expected error, this step is required to parse serialized values."""

        try:
            return self.adapter.validate_python(value)
        except pydantic.ValidationError as exc:
            error_params = {"errors": exc.errors(), "field": self}
            raise exceptions.ValidationError(exc.json(), code="invalid", params=error_params) from exc

    def get_prep_value(self, value: ty.Any):
        if isinstance(value, Value) and isinstance(value.output_field, self.__class__):
            # Prepare inner value for `Value`-wrapped expressions.
            value = Value(self.get_prep_value(value.value), value.output_field)
        elif not isinstance(value, BaseExpression):
            # Prepare the value if it is not a query expression.
            prep_value = self.adapter.validate_python(value)
            value = self.adapter.dump_python(prep_value)

        return super().get_prep_value(value)

    def get_transform(self, lookup_name: str):
        transform: ty.Any = super().get_transform(lookup_name)
        if transform is not None:
            transform = SchemaKeyTransformAdapter(transform)
        return transform

    def get_default(self) -> types.ST:
        default_value = super().get_default()
        return self.adapter.validate_python(default_value)

    def formfield(self, **kwargs):
        field_kwargs = dict(
            form_class=forms.SchemaField,
            # Trying to resolve the schema before passing it to the formfield, since in Django < 4.0,
            # formfield is unbound during form validation and is not able to resolve forward refs defined in the model.
            schema=self.adapter.prepared_schema,
            config=self.config,
            **self.export_kwargs,
        )
        field_kwargs.update(kwargs)
        return super().formfield(**field_kwargs)  # type: ignore

    def value_to_string(self, obj: Model):
        value = super().value_from_object(obj)
        return self.get_prep_value(value)


class SchemaKeyTransformAdapter:
    """An adapter for creating key transforms for schema field lookups."""

    def __init__(self, transform: type[Transform]):
        self.transform = transform

    def __call__(self, col: Col | None = None, *args, **kwargs) -> Transform | None:
        """All transforms should bypass the SchemaField's adaptaion with `get_prep_value`,
        and routed to JSONField's `get_prep_value` for further processing."""
        if isinstance(col, BaseExpression):
            col = col.copy()
            col.output_field = super(PydanticSchemaField, col.output_field)  # type: ignore
        return self.transform(col, *args, **kwargs)


@ty.overload
def SchemaField(
    schema: type[types.ST | None] | ty.ForwardRef = ...,
    config: pydantic.ConfigDict = ...,
    default: types.SchemaT | None | ty.Callable[[], types.SchemaT | None] = ...,
    *args,
    null: ty.Literal[True],
    **kwargs: te.Unpack[_SchemaFieldKwargs],
) -> types.ST | None:
    ...


@ty.overload
def SchemaField(
    schema: type[types.ST] | ty.ForwardRef = ...,
    config: pydantic.ConfigDict = ...,
    default: ty.Union[types.SchemaT, ty.Callable[[], types.SchemaT]] = ...,
    *args,
    null: ty.Literal[False] = ...,
    **kwargs: te.Unpack[_SchemaFieldKwargs],
) -> types.ST:
    ...


def SchemaField(schema=None, config=None, default=NOT_PROVIDED, *args, **kwargs):  # type: ignore
    deprecation.truncate_deprecated_v1_export_kwargs(kwargs)
    return PydanticSchemaField(*args, schema=schema, config=config, default=default, **kwargs)
