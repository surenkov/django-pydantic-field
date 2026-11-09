import typing as ty

import typing_extensions as te

from django_pydantic_field import types
from django_pydantic_field.fields import (
    PydanticDjangoJSONEncoder as PydanticDjangoJSONEncoder,
)
from django_pydantic_field.fields import (
    PydanticSchemaField as _PydanticSchemaField,
)

__all__ = ("PydanticDjangoJSONEncoder", "PydanticSchemaField", "SchemaField")

_SchemaT = te.TypeVar("_SchemaT", default=ty.Any)
_GetT = te.TypeVar("_GetT", default=_SchemaT)

class PydanticSchemaField(_PydanticSchemaField[_SchemaT, _GetT]):
    errors: types.ErrorHandlingMode
    @ty.overload
    def __init__(
        self: PydanticSchemaField[types.ST | None, types.ST | None],
        schema: type[types.ST] | type[types.ST | None],
        config: types.ConfigType = None,
        *args: ty.Any,
        null: ty.Literal[True],
        errors: types.ErrorHandlingMode = ...,
        **kwargs: ty.Any,
    ) -> None: ...
    @ty.overload
    def __init__(
        self: PydanticSchemaField[types.ST, types.ST],
        schema: type[types.ST],
        config: types.ConfigType = None,
        *args: ty.Any,
        errors: types.ErrorHandlingMode = ...,
        **kwargs: ty.Any,
    ) -> None: ...
    @ty.overload
    def __init__(
        self,
        schema: ty.ForwardRef | str | None = None,
        config: types.ConfigType = None,
        *args: ty.Any,
        errors: types.ErrorHandlingMode = ...,
        **kwargs: ty.Any,
    ) -> None: ...

@ty.overload
def SchemaField(
    schema: type[types.ST],
    config: types.ConfigType = None,
    default: ty.Callable[[], types.ST] | types.ST | ty.Any = ...,
    *args: ty.Any,
    null: ty.Literal[True],
    errors: types.ErrorHandlingMode = ...,
    **kwargs: ty.Any,
) -> PydanticSchemaField[types.ST | None, types.ST | None]: ...
@ty.overload
def SchemaField(
    schema: type[types.ST],
    config: types.ConfigType = None,
    default: ty.Callable[[], types.ST] | types.ST | ty.Any = ...,
    *args: ty.Any,
    errors: types.ErrorHandlingMode = ...,
    **kwargs: ty.Any,
) -> PydanticSchemaField[types.ST, types.ST]: ...
@ty.overload
def SchemaField(
    schema: ty.ForwardRef | str,
    config: types.ConfigType = None,
    *args: ty.Any,
    errors: types.ErrorHandlingMode = ...,
    **kwargs: ty.Any,
) -> ty.Any: ...
@ty.overload
def SchemaField(
    schema: None = None,
    config: types.ConfigType = None,
    *args: ty.Any,
    errors: types.ErrorHandlingMode = ...,
    **kwargs: ty.Any,
) -> ty.Any: ...
