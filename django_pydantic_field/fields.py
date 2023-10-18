import json
import typing as t
from functools import partial

import django
import pydantic
from django.core import exceptions as django_exceptions
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.json import JSONField
from django.db.models.query_utils import DeferredAttribute

from . import base, forms, utils
from ._migration_serializers import GenericContainer, GenericTypes

__all__ = ("SchemaField",)


class SchemaAttribute(DeferredAttribute):
    """
    Forces Django to call to_python on fields when setting them.
    This is useful when you want to add some custom field data postprocessing.

    Should be added to field like a so:

    ```
    def contribute_to_class(self, cls, name, *args, **kwargs):
        super().contribute_to_class(cls, name,  *args, **kwargs)
        setattr(cls, name, SchemaDeferredAttribute(self))
    ```
    """

    field: "PydanticSchemaField"

    def __set__(self, obj, value):
        obj.__dict__[self.field.attname] = self.field.to_python(value)


class PydanticSchemaField(JSONField, t.Generic[base.ST]):
    descriptor_class = SchemaAttribute
    _is_prepared_schema: bool = False

    def __init__(
        self,
        *args,
        schema: t.Union[t.Type["base.ST"], "GenericContainer", "t.ForwardRef", str, None] = None,
        config: "base.ConfigType" = None,
        **kwargs,
    ):
        self.export_params = base.extract_export_kwargs(kwargs, dict.pop)
        super().__init__(*args, **kwargs)

        self.config = config
        self._resolve_schema(schema)

    def __copy__(self):
        _, _, args, kwargs = self.deconstruct()
        copied = type(self)(*args, **kwargs)
        copied.set_attributes_from_name(self.name)
        return copied

    def get_default(self):
        value = super().get_default()
        return self.to_python(value)

    def to_python(self, value) -> "base.SchemaT":
        # Attempt to resolve forward referencing schema if it was not succesful
        # during `.contribute_to_class` call
        if not self._is_prepared_schema:
            self._prepare_model_schema()
        try:
            assert self.decoder is not None
            return self.decoder().decode(value)
        except pydantic.ValidationError as e:
            raise django_exceptions.ValidationError(e.errors())

    if django.VERSION[:2] >= (4, 2):

        def get_prep_value(self, value):
            if not self._is_prepared_schema:
                self._prepare_model_schema()
            prep_value = super().get_prep_value(value)
            prep_value = self.encoder().encode(prep_value)  # type: ignore
            return json.loads(prep_value)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        self._deconstruct_schema(kwargs)
        self._deconstruct_default(kwargs)
        self._deconstruct_config(kwargs)

        kwargs.pop("decoder")
        kwargs.pop("encoder")

        return name, path, args, kwargs

    def contribute_to_class(self, cls, name, private_only=False):
        if self.schema is None:
            self._resolve_schema_from_type_hints(cls, name)

        try:
            self._prepare_model_schema(cls)
        except NameError:
            # Pydantic was not able to resolve forward references, which means
            # that it should be postponed until initial access to the field
            self._is_prepared_schema = False

        super().contribute_to_class(cls, name, private_only)

    def formfield(self, **kwargs):
        if self.schema is None:
            self._resolve_schema_from_type_hints(self.model, self.attname)

        owner_model = getattr(self, "model", None)
        field_kwargs = dict(
            form_class=forms.SchemaField,
            schema=self.schema,
            config=self.config,
            __module__=getattr(owner_model, "__module__", None),
            **self.export_params,
        )
        field_kwargs.update(kwargs)
        return super().formfield(**field_kwargs)

    def _resolve_schema(self, schema):
        schema = t.cast(t.Type["base.ST"], GenericContainer.unwrap(schema))

        self.schema = schema
        if schema is not None:
            self.serializer_schema = serializer = base.wrap_schema(schema, self.config, self.null)
            self.decoder = partial(base.SchemaDecoder, serializer)  # type: ignore
            self.encoder = partial(base.SchemaEncoder, schema=serializer, export=self.export_params)  # type: ignore

    def _resolve_schema_from_type_hints(self, cls, name):
        annotated_schema = utils.get_annotated_type(cls, name)
        if annotated_schema is None:
            raise django_exceptions.FieldError(
                f"{cls._meta.label}.{name} needs to be either annotated "
                "or `schema=` field attribute should be explicitly passed"
            )
        self._resolve_schema(annotated_schema)

    def _prepare_model_schema(self, cls=None):
        cls = cls or getattr(self, "model", None)
        if cls is not None:
            base.prepare_schema(self.serializer_schema, cls)
            self._is_prepared_schema = True

    def _deconstruct_default(self, kwargs):
        default = kwargs.get("default", NOT_PROVIDED)

        if not (default is NOT_PROVIDED or callable(default)):
            if self._is_prepared_schema:
                default = self.get_prep_value(default)
            kwargs.update(default=default)

    def _deconstruct_schema(self, kwargs):
        kwargs.update(schema=GenericContainer.wrap(self.schema))

    def _deconstruct_config(self, kwargs):
        kwargs.update(base.deconstruct_export_kwargs(self.export_params))
        kwargs.update(config=self.config)


if t.TYPE_CHECKING:
    OptSchemaT = t.Optional[base.SchemaT]


@t.overload
def SchemaField(
    schema: "t.Union[t.Type[t.Optional[base.ST]], t.ForwardRef]" = ...,
    config: "base.ConfigType" = ...,
    default: "t.Union[OptSchemaT, t.Callable[[], OptSchemaT]]" = ...,
    *args,
    null: "t.Literal[True]",
    **kwargs,
) -> "t.Optional[base.ST]":
    ...


@t.overload
def SchemaField(
    schema: "t.Union[t.Type[base.ST], t.ForwardRef]" = ...,
    config: "base.ConfigType" = ...,
    default: "t.Union[base.SchemaT, t.Callable[[], base.SchemaT]]" = ...,
    *args,
    null: "t.Literal[False]" = ...,
    **kwargs,
) -> "base.ST":
    ...


def SchemaField(schema=None, config=None, *args, **kwargs) -> t.Any:
    kwargs.update(schema=schema, config=config)
    return PydanticSchemaField(*args, **kwargs)
