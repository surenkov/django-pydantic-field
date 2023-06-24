from __future__ import annotations

import json
import typing as ty

import django
import pydantic
from django.core.exceptions import FieldError, ValidationError
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.json import JSONField
from django.db.models.query_utils import DeferredAttribute

from ._migration_serializers import GenericContainer, GenericTypes
from .serialization import SchemaDecoder, SchemaEncoder, prepare_export_params
from .type_utils import SchemaT, cached_property, evaluate_forward_ref, get_raw_annotation, get_type_annotation, type_adapter


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

    field: PydanticSchemaField

    def __init__(self, field: PydanticSchemaField):
        owner_model, field_name = field.model, field.attname
        if field.schema is None and get_raw_annotation(owner_model, field_name) is None:
            raise FieldError(
                f"{owner_model._meta.label}.{field_name} needs to be either annotated "
                "or `schema=` field attribute should be explicitly passed"
            )
        super().__init__(field)

    def __set__(self, obj, value):
        obj.__dict__[self.field.attname] = self.field.to_python(value)


class PydanticSchemaField(JSONField, ty.Generic[SchemaT]):
    schema: type[SchemaT] | None
    descriptor_class = SchemaAttribute

    def __init__(self, schema: type[SchemaT] | None = None, config: pydantic.ConfigDict | None = None, *args, **kwargs):
        self.schema = schema
        self.config = config
        self.export_params = prepare_export_params(kwargs, dict.pop)

        super().__init__(*args, **kwargs)
        # Remove encoder/decorder assigned by JSONField
        del self.decoder
        del self.encoder

    def __copy__(self):
        _, _, args, kwargs = self.deconstruct()
        return self.__class__(*args, **kwargs)

    def decoder(self, **kwargs):
        return SchemaDecoder(self._type_adapter, **kwargs)

    def encoder(self, **kwargs):
        return SchemaEncoder(adapter=self._type_adapter, export_params=self.export_params, **kwargs)

    if django.VERSION[:2] >= (4, 2):

        def get_prep_value(self, value):
            prep_value = super().get_prep_value(value)
            prep_value = self.encoder().encode(prep_value)  # type: ignore
            return json.loads(prep_value)

    def deconstruct(self):
        # Bypass encoder/decoder deconstruction done by JSONField
        name, path, args, kwargs = super(JSONField, self).deconstruct()

        self._deconstruct_schema(kwargs)
        self._deconstruct_default(kwargs)
        self._deconstruct_config(kwargs)

        return name, path, args, kwargs

    def get_default(self) -> SchemaT:
        value = super().get_default()
        return self.to_python(value)

    def to_python(self, value) -> SchemaT:
        try:
            return self.decoder().decode(value)
        except pydantic.ValidationError as exc:
            # FIXME: fix validation error data: e.errors() failing for some reason
            raise ValidationError(exc.json())

    def formfield(self, **kwargs):
        from .forms import SchemaField

        schema = self._get_real_schema()
        field_kwargs = dict(form_class=SchemaField, schema=schema, config=self.config, **self.export_params)
        field_kwargs.update(kwargs)
        return super().formfield(**field_kwargs)

    @cached_property
    def _type_adapter(self):
        schema = self._get_real_schema()
        return type_adapter(schema, self.config, allow_null=self.null)  # type: ignore

    def _get_real_schema(self) -> type[SchemaT]:
        schema = self.schema
        if schema is None:
            schema = self._resolve_annotated_schema()
        if isinstance(schema, str):
            schema = ty.ForwardRef(schema)
        if isinstance(schema, ty.ForwardRef):
            schema = evaluate_forward_ref(self.model, schema)
        if isinstance(schema, GenericContainer):
            # Restore GenericContainer from deconstructed model
            schema = schema.reconstruct_type()
        return schema  # type: ignore

    def _resolve_annotated_schema(self) -> type[SchemaT]:
        model, field_name = self.model, self.attname
        try:
            return get_type_annotation(model, self.attname)
        except KeyError:
            raise FieldError(
                f"{model._meta.label}.{field_name} needs to be either annotated "
                "or `schema=` field attribute should be explicitly passed"
            )

    def _deconstruct_default(self, kwargs):
        default = kwargs.get("default", NOT_PROVIDED)

        if not (default is NOT_PROVIDED or callable(default)):
            plain_default = self.get_prep_value(default)
            kwargs.update(default=plain_default)

    def _deconstruct_schema(self, kwargs):
        schema = self.schema or self._resolve_annotated_schema()
        if isinstance(schema, GenericTypes):
            # Store generics as Django-serializable objects
            schema = GenericContainer.from_generic(self.schema)

        kwargs.update(schema=schema)

    def _deconstruct_config(self, kwargs):
        kwargs.update(**self.export_params, config=self.config)


@ty.overload
def SchemaField(
    schema: type[SchemaT] | ty.ForwardRef,  # type: ignore
    config: pydantic.ConfigDict = ...,
    default: SchemaT | None | ty.Callable[[], SchemaT | None] = ...,
    *args,
    null: ty.Literal[True],
    **kwargs,
) -> PydanticSchemaField[SchemaT]:  # type: ignore
    ...


@ty.overload
def SchemaField(
    schema: type[SchemaT] | ty.ForwardRef,  # type: ignore
    config: pydantic.ConfigDict = ...,
    default: SchemaT | ty.Callable[[], SchemaT] = ...,
    *args,
    null: ty.Literal[False] = ...,
    **kwargs,
) -> PydanticSchemaField[SchemaT]:
    ...


@ty.overload
def SchemaField(
    schema: None = ...,  # type: ignore
    config: pydantic.ConfigDict = ...,
    default: SchemaT | None | ty.Callable[[], SchemaT | None] = ...,  # type: ignore
    *args,
    null: ty.Literal[True],
    **kwargs,
) -> SchemaT | None:
    ...


@ty.overload
def SchemaField(
    schema: None = ...,  # type: ignore
    config: pydantic.ConfigDict = ...,
    default: SchemaT | None | ty.Callable[[], SchemaT | None] = ...,  # type: ignore
    *args,
    null: ty.Literal[False] = ...,
    **kwargs,
) -> SchemaT:
    ...


def SchemaField(schema=None, config=None, *args, **kwargs) -> ty.Any:
    kwargs.update(schema=schema, config=config)
    return PydanticSchemaField(*args, **kwargs)
