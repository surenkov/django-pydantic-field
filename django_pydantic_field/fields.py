import json
import typing as t

from functools import partial

from django.db.models.fields import NOT_PROVIDED
from django.db.models.query_utils import DeferredAttribute
from django.db.models import JSONField

from django.db.migrations.writer import MigrationWriter
from django.db.migrations.serializer import serializer_factory, BaseSerializer

from . import base

__all__ = "SchemaField",


class SchemaDeferredAttribute(DeferredAttribute):
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

    def __set__(self, obj, value):
        obj.__dict__[self.field.attname] = self.field.to_python(value)


class PydanticSchemaField(base.SchemaWrapper["base.ST"], JSONField):
    descriptor_class = SchemaDeferredAttribute

    def __init__(
        self,
        schema: t.Union[t.Type["base.ST"], "GenericContainer"],
        config: "base.ConfigType" = None,
        *args,
        error_handler=base.default_error_handler,
        **kwargs
    ):
        if isinstance(schema, GenericContainer):
            schema = t.cast(t.Type["base.ST"], schema.reconstruct_type())

        self.schema = schema
        self.config = config
        self.export_cfg = self._extract_export_kwargs(kwargs, dict.pop)

        field_schema = self._wrap_schema(schema, config)
        decoder = partial(base.SchemaDecoder, schema=field_schema, error_handler=error_handler)
        encoder = partial(base.SchemaEncoder, schema=field_schema, export_cfg=self.export_cfg)

        kwargs.update(decoder=decoder, encoder=encoder)
        super().__init__(*args, **kwargs)

    def __copy__(self):
        _, _, args, kwargs = self.deconstruct()
        return type(self)(*args, **kwargs)

    def get_default(self):
        value = super().get_default()
        return self.to_python(value)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        self._deconstruct_schema(kwargs)
        self._deconstruct_default(kwargs)
        self._deconstruct_config(kwargs)

        kwargs.pop("decoder")
        kwargs.pop("encoder")

        return name, path, args, kwargs

    def to_python(self, value) -> "base.SchemaT":
        assert self.decoder is not None
        return self.decoder().decode(value)

    def _deconstruct_default(self, kwargs):
        default = kwargs.get("default", NOT_PROVIDED)

        if not (default is NOT_PROVIDED or callable(default)):
            plain_default = self.get_prep_value(default)
            if plain_default is not None:
                plain_default = json.loads(plain_default)

            kwargs.update(default=plain_default)

    def _deconstruct_schema(self, kwargs):
        schema = self.schema
        if isinstance(schema, GenericTypes):
            schema = GenericContainer.from_generic(self.schema)

        kwargs.update(schema=schema)

    def _deconstruct_config(self, kwargs):
        kwargs.update(self.export_cfg, config=self.config)


def SchemaField(
    schema: t.Union[t.Type["base.ST"], "GenericContainer"],
    config: "base.ConfigType" = None,
    *args,
    error_handler=base.default_error_handler,
    **kwargs
) -> t.Any:
    return PydanticSchemaField(schema, config, *args, error_handler=error_handler, **kwargs)


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


try:
    GenericAlias = type(list[int])
    GenericTypes: t.Tuple[t.Any, ...] = GenericAlias, type(t.List[int]), type(t.List)
except TypeError:
    # builtins.list is not subscriptable, meaning python < 3.9,
    # which has a different inheritance models for typed generics
    GenericAlias = type(t.List[int])
    GenericTypes = GenericAlias, type(t.List)

MigrationWriter.register_serializer(GenericContainer, _GenericSerializer)
