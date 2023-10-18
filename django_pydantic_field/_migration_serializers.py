"""
Django Migration serializer helpers

[Built-in generic annotations](https://peps.python.org/pep-0585/)
    introduced in Python 3.9 are having a different semantics from `typing` collections.
    Due to how Django treats field serialization/reconstruction while writing migrations,
    it is not possible to distnguish between `types.GenericAlias` and any other regular types,
    thus annotations are being erased by `MigrationWriter` serializers.

    To mitigate this, I had to introduce custom container for schema deconstruction.

[Union types syntax](https://peps.python.org/pep-0604/)
    `typing.Union` and its special forms, like `typing.Optional`, have its own inheritance chain.
    Moreover, `types.UnionType`, introduced in 3.10, do not allow explicit type construction,
    only with `X | Y` syntax. Both cases require a dedicated serializer for migration writes.
"""
import sys
import types
import typing as t

try:
    from typing import get_args, get_origin
except ImportError:
    from typing_extensions import get_args, get_origin

from django.db.migrations.serializer import BaseSerializer, serializer_factory
from django.db.migrations.writer import MigrationWriter


class GenericContainer:
    __slots__ = "origin", "args"

    def __init__(self, origin, args: tuple = ()):
        self.origin = origin
        self.args = args

    @classmethod
    def wrap(cls, typ_):
        if isinstance(typ_, GenericTypes):
            wrapped_args = tuple(map(cls.wrap, get_args(typ_)))
            return cls(get_origin(typ_), wrapped_args)
        return typ_

    @classmethod
    def unwrap(cls, type_):
        if not isinstance(type_, GenericContainer):
            return type_

        if not type_.args:
            return type_.origin

        unwrapped_args = tuple(map(cls.unwrap, type_.args))
        try:
            # This is a fallback for Python < 3.8, please be careful with that
            return type_.origin[unwrapped_args]
        except TypeError:
            return GenericAlias(type_.origin, unwrapped_args)

    def __repr__(self):
        return repr(self.unwrap(self))

    __str__ = __repr__

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.origin == other.origin and self.args == other.args
        if isinstance(other, GenericTypes):
            return self == self.wrap(other)
        return NotImplemented


class GenericSerializer(BaseSerializer):
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


class TypingSerializer(BaseSerializer):
    def serialize(self):
        orig_module = self.value.__module__
        orig_repr = repr(self.value)

        if not orig_repr.startswith(orig_module):
            orig_repr = f"{orig_module}.{orig_repr}"

        return orig_repr, {f"import {orig_module}"}


if sys.version_info >= (3, 9):
    GenericAlias = types.GenericAlias
    GenericTypes: t.Tuple[t.Any, ...] = (
        GenericAlias,
        type(t.List[int]),
        type(t.List),
    )
else:
    # types.GenericAlias is missing, meaning python version < 3.9,
    # which has a different inheritance models for typed generics
    GenericAlias = type(t.List[int])
    GenericTypes = GenericAlias, type(t.List)


MigrationWriter.register_serializer(GenericContainer, GenericSerializer)
MigrationWriter.register_serializer(t.ForwardRef, TypingSerializer)
MigrationWriter.register_serializer(type(t.Union), TypingSerializer)  # type: ignore


if sys.version_info >= (3, 10):
    UnionType = types.UnionType

    class UnionTypeSerializer(BaseSerializer):
        value: UnionType

        def serialize(self):
            imports = set()
            if isinstance(self.value, type(t.Union)):  # type: ignore
                imports.add("import typing")

            for arg in get_args(self.value):
                _, arg_imports = serializer_factory(arg).serialize()
                imports.update(arg_imports)

            return repr(self.value), imports

    MigrationWriter.register_serializer(UnionType, UnionTypeSerializer)
