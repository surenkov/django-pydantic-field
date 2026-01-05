from __future__ import annotations

import json
import typing as ty

import pydantic
import typing_extensions as te
from django.core import checks, exceptions
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.expressions import BaseExpression, Col, Value
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.json import JSONField, KeyTransform
from django.db.models.lookups import Transform
from django.db.models.query_utils import DeferredAttribute

from django_pydantic_field.compat import deprecation
from django_pydantic_field.compat.django import BaseContainer, GenericContainer

from . import forms, types

if ty.TYPE_CHECKING:
    import json

    from django.db.models import Model

    @ty.type_check_only
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


__all__ = ("SchemaField", "PydanticSchemaField")


class SchemaAttribute(DeferredAttribute):
    field: PydanticSchemaField

    def __set_name__(self, owner, name):
        self.field.adapter.bind(owner, name, self.field)

    def __set__(self, obj, value):
        obj.__dict__[self.field.attname] = self.field.to_python(value)


class UninitializedSchemaAttribute(SchemaAttribute):
    def __set__(self, obj, value):
        if value is not None:
            value = self.field.to_python(value)
        obj.__dict__[self.field.attname] = value


class PydanticSchemaField(JSONField, ty.Generic[types.ST]):
    adapter: types.SchemaAdapter

    def __init__(
        self,
        *args,
        schema: type[types.ST] | te.Annotated[type[types.ST], ...] | BaseContainer | ty.ForwardRef | str | None = None,
        config: types.ConfigType | None = None,
        **kwargs,
    ):
        kwargs.setdefault("encoder", DjangoJSONEncoder)
        self.export_kwargs = export_kwargs = types.SchemaAdapter.extract_export_kwargs(kwargs)
        super().__init__(*args, **kwargs)

        self.schema = BaseContainer.unwrap(schema)
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
        elif import_path.startswith("django_pydantic_field.v1."):
            import_path = import_path.replace("django_pydantic_field.v1", "django_pydantic_field", 1)

        default = kwargs.get("default", NOT_PROVIDED)
        if default is not NOT_PROVIDED and not callable(default):
            kwargs["default"] = self._prepare_raw_value(default, include=None, exclude=None, round_trip=True)

        prep_schema = GenericContainer.wrap(self.adapter.prepared_schema)
        kwargs.update(schema=prep_schema, config=self.config, **self.export_kwargs)

        return field_name, import_path, args, kwargs

    @staticmethod
    def descriptor_class(field: PydanticSchemaField) -> DeferredAttribute:
        if field.has_default():
            return SchemaAttribute(field)
        return UninitializedSchemaAttribute(field)

    def contribute_to_class(self, cls: types.DjangoModelType, name: str, private_only: bool = False) -> None:
        try:
            self.adapter.bind(cls, name, self)
        except types.ImproperlyConfiguredSchema as exc:
            raise exceptions.FieldError(exc.args[0]) from exc
        super().contribute_to_class(cls, name, private_only)

    def check(self, **kwargs: ty.Any) -> list[checks.CheckMessage]:
        performed_checks = [check for check in super().check(**kwargs) if check.id != "fields.E010"]
        try:
            self.adapter.validate_schema()
        except types.ImproperlyConfiguredSchema as exc:
            message = f"Cannot resolve the schema. Original error: \n{exc.args[0]}"
            performed_checks.append(checks.Error(message, obj=self, id="pydantic.E001"))

        try:
            if self.has_default():
                self.get_prep_value(self.get_default())
        except pydantic.ValidationError as exc:
            message = f"Default value cannot be adapted to the schema. Pydantic error: \n{str(exc)}"
            performed_checks.append(checks.Error(message, obj=self, id="pydantic.E002"))

        if {"include", "exclude"} & self.export_kwargs.keys():
            schema_default = self.get_default()
            if schema_default is None:
                prep_value = self.adapter.get_default_value()
                if prep_value is not None:
                    schema_default = prep_value

            if schema_default is not None:
                try:
                    self.adapter.validate_python(self.get_prep_value(schema_default))
                except pydantic.ValidationError as exc:
                    message = f"Export arguments may lead to data integrity problems. Pydantic error: \n{str(exc)}"
                    hint = "Please review `import` and `export` arguments."
                    performed_checks.append(checks.Warning(message, obj=self, hint=hint, id="pydantic.W003"))

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
            raise exceptions.ValidationError(str(exc), code="invalid") from exc

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value

        if isinstance(expression, KeyTransform):
            return super().from_db_value(value, expression, connection)

        try:
            return self.adapter.validate_json(value)
        except ValueError:
            return super().from_db_value(value, expression, connection)

    def get_prep_value(self, value: ty.Any):
        value = self._prepare_raw_value(value)
        return super().get_prep_value(value)

    def get_transform(self, lookup_name: str):
        transform: ty.Any = super().get_transform(lookup_name)
        if transform is not None:
            transform = SchemaKeyTransformAdapter(transform)
        return transform

    def get_default(self) -> ty.Any:
        default_value = super().get_default()
        if self.has_default():
            return self.adapter.validate_python(default_value)
        return default_value

    def formfield(self, form_class=None, choices_form_class=None, **kwargs):
        field_kwargs = dict(
            form_class=form_class or forms.SchemaField,
            choices_form_class=choices_form_class,
            schema=self.adapter.prepared_schema,
            config=self.config,
            **self.export_kwargs,
        )
        field_kwargs.update(kwargs)
        return super().formfield(**field_kwargs)

    def value_to_string(self, obj: Model):
        value = super().value_from_object(obj)
        return self._prepare_raw_value(value)

    def _prepare_raw_value(self, value: ty.Any, **dump_kwargs):
        if isinstance(value, Value) and isinstance(value.output_field, self.__class__):
            value = Value(self._prepare_raw_value(value.value), value.output_field)
        elif not isinstance(value, BaseExpression):
            try:
                value = self.adapter.validate_python(value)
            except pydantic.ValidationError:
                pass
            value = self.adapter.dump_python(value, mode="json", **dump_kwargs)

        return value


class SchemaKeyTransformAdapter:
    def __init__(self, transform: type[Transform]):
        self.transform = transform

    def __call__(self, col: Col | None = None, *args, **kwargs) -> Transform | None:
        if isinstance(col, BaseExpression):
            col = col.copy()
            col.output_field = super(PydanticSchemaField, col.output_field)
        return self.transform(col, *args, **kwargs)


@ty.overload
def SchemaField(
    schema: ty.Annotated[type[types.ST | None], ...] = ...,
    config: types.ConfigType = ...,
    default: types.SchemaT | ty.Callable[[], types.SchemaT | None] | BaseExpression | None = ...,
    *args,
    null: ty.Literal[True],
    **kwargs: te.Unpack[_SchemaFieldKwargs],
) -> types.ST | None: ...


@ty.overload
def SchemaField(
    schema: ty.Annotated[type[types.ST], ...] = ...,
    config: types.ConfigType = ...,
    default: types.SchemaT | ty.Callable[[], types.SchemaT] | BaseExpression = ...,
    *args,
    null: ty.Literal[False] = ...,
    **kwargs: te.Unpack[_SchemaFieldKwargs],
) -> types.ST: ...


@ty.overload
def SchemaField(
    schema: type[types.ST | None] | ty.ForwardRef = ...,
    config: types.ConfigType = ...,
    default: types.SchemaT | ty.Callable[[], types.SchemaT | None] | BaseExpression | None = ...,
    *args,
    null: ty.Literal[True],
    **kwargs: te.Unpack[_SchemaFieldKwargs],
) -> types.ST | None: ...


@ty.overload
def SchemaField(
    schema: type[types.ST] | ty.ForwardRef = ...,
    config: types.ConfigType = ...,
    default: types.SchemaT | ty.Callable[[], types.SchemaT] | BaseExpression = ...,
    *args,
    null: ty.Literal[False] = ...,
    **kwargs: te.Unpack[_SchemaFieldKwargs],
) -> types.ST: ...


def SchemaField(schema=None, config=None, default=NOT_PROVIDED, *args, **kwargs):
    deprecation.truncate_deprecated_v1_export_kwargs(kwargs)
    return PydanticSchemaField(*args, schema=schema, config=config, default=default, **kwargs)
