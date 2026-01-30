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

[typing.Annotated](https://peps.python.org/pep-0593/)
    `typing.Annotated` syntax is supported for direct field annotations, though I find it highly discouraged
    while using in `schema=` attribute.
    The limitation with `Annotated` types is that supplied metadata could be actually of any type.
    In case of Pydantic, it is a `FieldInfo` objects, which are not compatible with Django Migrations serializers.
    This module provides a few containers (`FieldInfoContainer` and `DataclassContainer`),
    which allow Model serializers to work.
"""

from __future__ import annotations

import abc
import dataclasses
import sys
import types
import typing as ty

import typing_extensions as te
from django.db.migrations.serializer import BaseSerializer, serializer_factory
from django.db.migrations.writer import MigrationWriter
from pydantic.fields import FieldInfo

from .pydantic import PYDANTIC_V1
from .typing import get_args, get_origin

try:
    from pydantic._internal._repr import Representation
    from pydantic.fields import _DefaultValues as FieldInfoDefaultValues
    from pydantic_core import PydanticUndefined
except ImportError:
    # Assuming this is a Pydantic v1
    from pydantic.fields import Undefined as PydanticUndefined  # type: ignore[unresolved-import]
    from pydantic.utils import Representation  # type: ignore[unresolved-import]

    FieldInfoDefaultValues = FieldInfo.__field_constraints__  # type: ignore[attr-defined]


UnionType = types.UnionType
AnnotatedAlias = te._AnnotatedAlias

if sys.version_info >= (3, 14):
    GenericTypes: ty.Tuple[ty.Any, ...] = (
        types.GenericAlias,
        type(ty.List[int]),
        type(ty.List),
        ty.Union,
    )
else:
    GenericTypes = (
        types.GenericAlias,
        type(ty.List[int]),
        type(ty.List),
    )


class BaseContainer(abc.ABC):
    __slot__ = ()

    @classmethod
    def unwrap(cls, value):
        if isinstance(value, BaseContainer) and type(value) is not BaseContainer:
            return value.unwrap(value)
        return value

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return all(getattr(self, attr) == getattr(other, attr) for attr in self.__slots__)
        return NotImplemented

    def __str__(self):
        return repr(self.unwrap(self))

    def __repr__(self):
        attrs = tuple(getattr(self, attr) for attr in self.__slots__)
        return f"{self.__class__.__name__}{attrs}"


class GenericContainer(BaseContainer):
    __slots__ = "origin", "args"

    def __init__(self, origin, args: tuple = ()):
        self.origin = origin
        self.args = args

    @classmethod
    def wrap(cls, value):
        # NOTE: due to a bug in typing_extensions for `3.8`, Annotated aliases are handled explicitly
        if isinstance(value, AnnotatedAlias):
            args = (value.__origin__, *value.__metadata__)
            wrapped_args = tuple(map(cls.wrap, args))
            return cls(te.Annotated, wrapped_args)
        if isinstance(value, GenericTypes):
            wrapped_args = tuple(map(cls.wrap, get_args(value)))
            return cls(get_origin(value), wrapped_args)
        if DataclassContainer.is_dataclass_instance(value):
            return DataclassContainer.wrap(value)
        if isinstance(value, FieldInfo):
            return FieldInfoContainer.wrap(value)
        return value

    @classmethod
    def unwrap(cls, value):
        if not isinstance(value, cls):
            return value

        if PYDANTIC_V1:
            origin = get_origin(BaseContainer.unwrap(value.origin)) or value.origin
        else:
            origin = value.origin

        if not value.args:
            return origin

        unwrapped_args = tuple(map(BaseContainer.unwrap, value.args))
        try:
            # This is a fallback for Python < 3.8, please be careful with that
            return origin[unwrapped_args]
        except TypeError:
            return types.GenericAlias(origin, unwrapped_args)

    def __eq__(self, other):
        if isinstance(other, GenericTypes):
            return self == self.wrap(other)
        return super().__eq__(other)


class DataclassContainer(BaseContainer):
    __slots__ = "datacls", "kwargs"

    def __init__(self, datacls: type, kwargs: ty.Dict[str, ty.Any]):
        self.datacls = datacls
        self.kwargs = kwargs

    @classmethod
    def wrap(cls, value):
        if cls.is_dataclass_instance(value):
            return cls(type(value), dataclasses.asdict(value))
        if isinstance(value, GenericTypes):
            return GenericContainer.wrap(value)
        return value

    @classmethod
    def unwrap(cls, value):
        if isinstance(value, cls):
            return value.datacls(**value.kwargs)
        return value

    @staticmethod
    def is_dataclass_instance(obj: ty.Any):
        return dataclasses.is_dataclass(obj) and not isinstance(obj, type)

    def __eq__(self, other):
        if self.is_dataclass_instance(other):
            return self == self.wrap(other)
        return super().__eq__(other)


class FieldInfoContainer(BaseContainer):
    __slots__ = "origin", "metadata", "kwargs"

    def __init__(self, origin, metadata, kwargs):
        self.origin = origin
        self.metadata = metadata
        self.kwargs = kwargs

    @classmethod
    def wrap(cls, field: FieldInfo):
        if not isinstance(field, FieldInfo):
            return field

        # `getattr` is important to preserve compatibility with Pydantic v1
        metadata = getattr(field, "metadata", ())
        origin = getattr(field, "annotation", None)
        if origin is type(None):
            origin = None

        origin = GenericContainer.wrap(origin)
        metadata = tuple(map(DataclassContainer.wrap, metadata))

        kwargs = dict(cls._iter_field_attrs(field))
        if PYDANTIC_V1:
            kwargs.update(kwargs.pop("extra", {}))

        return cls(origin, metadata, kwargs)

    @classmethod
    def unwrap(cls, value):
        if not isinstance(value, cls):
            return value
        if PYDANTIC_V1:
            return FieldInfo(**value.kwargs)

        origin = GenericContainer.unwrap(value.origin)
        metadata = tuple(map(BaseContainer.unwrap, value.metadata))
        try:
            annotated_args = (origin, *metadata)  # noqa: F841
            annotation = te.Annotated[annotated_args]  # type: ignore[invalid-type-form]
        except TypeError:
            annotation = None

        return FieldInfo(annotation=annotation, **value.kwargs)

    def __eq__(self, other):
        if isinstance(other, FieldInfo):
            return self == self.wrap(other)
        return super().__eq__(other)

    @staticmethod
    def _iter_field_attrs(field: FieldInfo):
        available_attrs = set(field.__slots__) - {"annotation", "metadata", "_attributes_set"}

        for attr in available_attrs:
            attr_value = getattr(field, attr)
            if attr_value is not PydanticUndefined and attr_value != FieldInfoDefaultValues.get(attr):
                yield attr, getattr(field, attr)

    @staticmethod
    def _wrap_metadata_object(obj):
        return DataclassContainer.wrap(obj)


class BaseContainerSerializer(BaseSerializer):
    value: BaseContainer

    def serialize(self):
        tp_repr, imports = serializer_factory(type(self.value)).serialize()
        attrs = []

        for attr in self._iter_container_attrs():
            attr_repr, attr_imports = serializer_factory(attr).serialize()
            attrs.append(attr_repr)
            imports.update(attr_imports)

        attrs_repr = ", ".join(attrs)
        return f"{tp_repr}({attrs_repr})", imports

    def _iter_container_attrs(self):
        container = self.value
        for attr in container.__slots__:
            yield getattr(container, attr)


class DataclassContainerSerializer(BaseSerializer):
    value: DataclassContainer

    def serialize(self):
        tp_repr, imports = serializer_factory(self.value.datacls).serialize()

        kwarg_pairs = []
        for arg, value in self.value.kwargs.items():
            value_repr, value_imports = serializer_factory(value).serialize()
            kwarg_pairs.append(f"{arg}={value_repr}")
            imports.update(value_imports)

        kwargs_repr = ", ".join(kwarg_pairs)
        return f"{tp_repr}({kwargs_repr})", imports


class TypingSerializer(BaseSerializer):
    def serialize(self):
        value = GenericContainer.wrap(self.value)
        if isinstance(value, GenericContainer):
            return serializer_factory(value).serialize()

        orig_module = self.value.__module__
        orig_repr = repr(self.value)

        if not orig_repr.startswith(orig_module):
            orig_repr = f"{orig_module}.{orig_repr}"

        return orig_repr, {f"import {orig_module}"}


class FieldInfoSerializer(BaseSerializer):
    value: FieldInfo

    def serialize(self):
        container = FieldInfoContainer.wrap(self.value)
        return serializer_factory(container).serialize()


class RepresentationSerializer(BaseSerializer):
    value: Representation

    def serialize(self):
        tp_repr, imports = serializer_factory(type(self.value)).serialize()
        repr_args = []

        for arg_name, arg_value in self.value.__repr_args__():
            arg_value_repr, arg_value_imports = serializer_factory(arg_value).serialize()
            imports.update(arg_value_imports)

            if arg_name is None:
                repr_args.append(arg_value_repr)
            else:
                repr_args.append(f"{arg_name}={arg_value_repr}")

        final_args_repr = ", ".join(repr_args)
        return f"{tp_repr}({final_args_repr})", imports


class UnionTypeSerializer(BaseSerializer):
    value: UnionType

    def serialize(self):
        imports = set()
        if isinstance(self.value, (type(ty.Union), UnionType)):  # type: ignore
            imports.add("import typing")

        for arg in get_args(self.value):
            _, arg_imports = serializer_factory(GenericContainer.wrap(arg)).serialize()
            imports.update(arg_imports)

        return repr(self.value), imports


# BaseContainerSerializer *must be* registered after all specialized container serializers
MigrationWriter.register_serializer(DataclassContainer, DataclassContainerSerializer)
MigrationWriter.register_serializer(BaseContainer, BaseContainerSerializer)

# Pydantic-specific datastructures serializers
MigrationWriter.register_serializer(FieldInfo, FieldInfoSerializer)
MigrationWriter.register_serializer(Representation, RepresentationSerializer)

# Typing serializers
for type_ in GenericTypes:
    MigrationWriter.register_serializer(type_, TypingSerializer)

MigrationWriter.register_serializer(ty.ForwardRef, TypingSerializer)
MigrationWriter.register_serializer(ty._SpecialForm, TypingSerializer)  # type: ignore
MigrationWriter.register_serializer(type(ty.Union), TypingSerializer)  # type: ignore
MigrationWriter.register_serializer(UnionType, UnionTypeSerializer)
