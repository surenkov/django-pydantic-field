import json
import typing as t
import pydantic

from functools import partial

from django.core import exceptions as django_exceptions
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.json import JSONField
from django.db.models.query_utils import DeferredAttribute

from django.db.migrations.writer import MigrationWriter
from django.db.migrations.serializer import serializer_factory, BaseSerializer

from . import base, utils

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
    is_prepared_schema: bool = False

    def __init__(
        self,
        *args,
        schema: t.Union[t.Type["base.ST"], "GenericContainer", "t.ForwardRef", str] = None,
        config: "base.ConfigType" = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.config = config
        self.export_params = base.extract_export_kwargs(kwargs, dict.pop)
        self._resolve_schema(schema)

    def __copy__(self):
        _, _, args, kwargs = self.deconstruct()
        return type(self)(*args, **kwargs)

    def get_default(self):
        value = super().get_default()
        return self.to_python(value)

    def to_python(self, value) -> "base.SchemaT":
        # Attempt to resolve forward referencing schema if it was not succesful
        # during `.contribute_to_class` call
        if not self.is_prepared_schema:
            self._prepare_model_schema()
        try:
            assert self.decoder is not None
            return self.decoder().decode(value)
        except pydantic.ValidationError as e:
            raise django_exceptions.ValidationError(e.errors())

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
            # Pydantic was not able to resolve forward references,
            # which means that it should be postponed to field access
            self.is_prepared_schema = False

        super().contribute_to_class(cls, name, private_only)

    def _resolve_schema(self, schema):
        if isinstance(schema, GenericContainer):
            schema = t.cast(t.Type["base.ST"], schema.reconstruct_type())

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
            model_ns = utils.get_model_namespace(cls)
            self.serializer_schema.update_forward_refs(**model_ns)
            self.is_prepared_schema = True

    def _deconstruct_default(self, kwargs):
        default = kwargs.get("default", NOT_PROVIDED)

        if not (default is NOT_PROVIDED or callable(default)):
            # default value deconstruction with SchemaEncoder is meaningful
            # only if schema resolution is not deferred
            if self.is_prepared_schema:
                plain_default = self.get_prep_value(default)
                if plain_default is not None:
                    plain_default = json.loads(plain_default)
            else:
                plain_default = default

            kwargs.update(default=plain_default)

    def _deconstruct_schema(self, kwargs):
        schema = self.schema
        if isinstance(schema, GenericTypes):
            schema = GenericContainer.from_generic(self.schema)

        kwargs.update(schema=schema)

    def _deconstruct_config(self, kwargs):
        kwargs.update(self.export_params, config=self.config)


@t.overload
def SchemaField(
    schema: t.Union[t.Type["base.ST"], "t.ForwardRef", str] = ...,
    config: "base.ConfigType" = ...,
    default: t.Union["base.ST", t.Type[NOT_PROVIDED], None] = ...,
    null: t.Literal[True] = ...,
    *args,
    **kwargs,
) -> t.Any:
    ...


@t.overload
def SchemaField(
    schema: t.Union[t.Type["base.ST"], "t.ForwardRef", str] = ...,
    config: "base.ConfigType" = ...,
    default: t.Union["base.ST", t.Type[NOT_PROVIDED]] = ...,
    null: t.Literal[False] = ...,
    *args,
    **kwargs,
) -> t.Any:
    ...


def SchemaField(
    schema: t.Union[t.Type["base.ST"], "t.ForwardRef", str] = None,
    config: "base.ConfigType" = None,
    default: t.Union["base.ST", t.Type[NOT_PROVIDED], None] = NOT_PROVIDED,
    *args,
    **kwargs,
) -> t.Any:
    kwargs.update(schema=schema, config=config, default=default)
    return PydanticSchemaField(*args, **kwargs)


# Django Migration serializer helpers
#
# [Built-in generic annotations](https://peps.python.org/pep-0585/)
#   introduced in Python 3.9 are having a different semantics from `typing` collections.
#   Due to how Django treats field serialization/reconstruction while writing migrations,
#   it is not possible to distnguish between `types.GenericAlias` and any other regular types,
#   thus annotations are being erased by `MigrationWriter` serializers.
#
#   To mitigate this, I had to introduce custom container for schema deconstruction.


class GenericContainer:
    __slots__ = "origin", "args"

    def __init__(self, origin, args=()):
        self.origin = origin
        self.args = args

    @classmethod
    def from_generic(cls, type_alias):
        return cls(t.get_origin(type_alias), t.get_args(type_alias))

    def reconstruct_type(self):
        if not self.args:
            return self.origin
        return GenericAlias(self.origin, self.args)

    def __repr__(self):
        return repr(self.reconstruct_type())

    __str__ = __repr__

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.origin, self.args == other.origin, other.args
        if isinstance(other, GenericTypes):
            return self == self.from_generic(other)
        return NotImplemented


class _GenericSerializer(BaseSerializer):
    value: GenericContainer

    def serialize(self):
        value = self.value

        tp_repr, imports = serializer_factory(type(value)).serialize()
        orig_repr, orig_imports = serializer_factory(value.origin).serialize()
        imports.update(orig_imports)

        args = []
        for arg in value.args:
            arg_repr, arg_imports = serializer_factory(arg).serialize()
            args.append(arg_repr)
            imports.update(arg_imports)

        if args:
            args_repr = ", ".join(args)
            generic_repr = "%s(%s, (%s,))" % (tp_repr, orig_repr, args_repr)
        else:
            generic_repr = "%s(%s)" % (tp_repr, orig_repr)

        return generic_repr, imports


class _ForwardRefSerializer(BaseSerializer):
    value: t.ForwardRef

    def serialize(self):
        return f"typing.{repr(self.value)}", {"import typing"}


try:
    GenericAlias = type(list[int])
    GenericTypes: t.Tuple[t.Any, ...] = GenericAlias, type(t.List[int]), type(t.List)
except TypeError:
    # builtins.list is not subscriptable, meaning python < 3.9,
    # which has a different inheritance models for typed generics
    GenericAlias = type(t.List[int])
    GenericTypes = GenericAlias, type(t.List)

MigrationWriter.register_serializer(GenericContainer, _GenericSerializer)
MigrationWriter.register_serializer(t.ForwardRef, _ForwardRefSerializer)
