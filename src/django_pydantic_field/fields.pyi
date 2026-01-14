import typing as ty

import typing_extensions as te
from django.db.models import JSONField, Model
from django.db.models.expressions import BaseExpression

from django_pydantic_field import types

__all__ = ("PydanticSchemaField", "SchemaField")

_AnnotatedAlias: ty.TypeAlias = type(te.Annotated[types.ST, ...])
_DT: ty.TypeAlias = ty.Any

@ty.type_check_only
class SchemaAttribute(ty.Generic[types.ST]):
    field: PydanticSchemaField[types.ST]
    @ty.overload
    def __get__(self, instance: None, owner: ty.Any) -> te.Self: ...
    @ty.overload
    def __get__(self, instance: Model, owner: ty.Any) -> types.ST: ...
    @ty.overload
    def __get__(self, instance: ty.Any, owner: ty.Any) -> types.ST: ...

class PydanticSchemaField(JSONField[types.ST, types.ST]):
    def __set__(self, instance: ty.Any, value: types.ST) -> None: ...
    @ty.overload
    def __get__(self, instance: None, owner: ty.Any) -> SchemaAttribute[types.ST]: ...
    @ty.overload
    def __get__(self, instance: Model, owner: ty.Any) -> types.ST: ...
    @ty.overload
    def __get__(self, instance: ty.Any, owner: ty.Any) -> types.ST: ...  # type: ignore[invalid-method-override]

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
