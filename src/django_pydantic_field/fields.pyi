import typing as ty

import typing_extensions as te
from django.db.models import JSONField, Model
from django.db.models.expressions import BaseExpression

from django_pydantic_field import compat, types

__all__ = ("PydanticSchemaField", "SchemaField")

_AnnotatedAlias: ty.TypeAlias = ty.Any
_DT: ty.TypeAlias = ty.Any
_SchemaT = ty.TypeVar("_SchemaT")

@ty.type_check_only
class SchemaAttribute(ty.Generic[types.ST]):
    field: PydanticSchemaField[types.ST]
    @ty.overload
    def __get__(self, instance: None, owner: ty.Any) -> te.Self: ...
    @ty.overload
    def __get__(self, instance: Model, owner: ty.Any) -> types.ST: ...
    @ty.overload
    def __get__(self, instance: ty.Any, owner: ty.Any) -> types.ST: ...

class PydanticSchemaField(JSONField[_SchemaT, _SchemaT]):
    def __set__(self, instance: ty.Any, value: _SchemaT) -> None: ...
    @ty.overload
    def __get__(self, instance: None, owner: ty.Any) -> SchemaAttribute[_SchemaT]: ...
    @ty.overload
    def __get__(self, instance: Model, owner: ty.Any) -> _SchemaT: ...
    @ty.overload
    def __init__(
        self: PydanticSchemaField[types.ST | None],
        schema: type[types.ST] | type[types.ST | None],
        config: types.ConfigType | None = ...,
        *args: ty.Any,
        null: ty.Literal[True],
        **kwargs: ty.Any,
    ) -> None: ...
    @ty.overload
    def __init__(
        self: PydanticSchemaField[types.ST],
        schema: type[types.ST],
        config: types.ConfigType | None = ...,
        *args: ty.Any,
        **kwargs: ty.Any,
    ) -> None: ...
    @ty.overload
    def __init__(
        self,
        # fmt: off
        schema: type[_SchemaT] | ty.ForwardRef | str | _AnnotatedAlias | compat.django.GenericContainer | None = ...,
        # fmt: on
        config: types.ConfigType | None = ...,
        *args: ty.Any,
        **kwargs: ty.Any,
    ) -> None: ...

@ty.overload
def SchemaField(
    schema: type[types.ST] | type[types.ST | None],
    config: types.ConfigType = ...,
    default: ty.Callable[[], _DT] | ty.Callable[[], _DT | None] | _DT | None | BaseExpression = ...,
    *args: ty.Any,
    null: ty.Literal[True],
    **kwargs: ty.Any,
) -> PydanticSchemaField[types.ST | None]: ...
@ty.overload
def SchemaField(
    schema: type[types.ST],
    config: types.ConfigType = ...,
    default: ty.Callable[[], _DT] | _DT | BaseExpression = ...,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> PydanticSchemaField[types.ST]: ...
@ty.overload
def SchemaField(
    schema: ty.ForwardRef | str,
    config: types.ConfigType = ...,
    default: ty.Callable[[], _DT] | _DT | BaseExpression = ...,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> ty.Any: ...
@ty.overload
def SchemaField(
    schema: _AnnotatedAlias,
    config: types.ConfigType = ...,
    default: ty.Callable[[], _DT] | _DT | BaseExpression = ...,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> ty.Any: ...
@ty.overload
def SchemaField(
    schema: None = None,
    config: types.ConfigType = ...,
    default: ty.Callable[[], _DT] | _DT | BaseExpression = ...,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> ty.Any: ...
