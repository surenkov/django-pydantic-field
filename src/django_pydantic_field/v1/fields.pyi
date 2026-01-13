import typing as ty

from django_pydantic_field import types
from django_pydantic_field.fields import PydanticSchemaField as _PydanticSchemaField

class PydanticSchemaField(_PydanticSchemaField[types.ST]): ...

@ty.overload
def SchemaField(
    schema: type[types.ST],
    config: types.ConfigType = None,
    default: ty.Callable[[], types.ST] | types.ST | ty.Any = ...,
    *args: ty.Any,
    null: ty.Literal[True],
    **kwargs: ty.Any,
) -> PydanticSchemaField[types.ST | None]: ...
@ty.overload
def SchemaField(
    schema: type[types.ST],
    config: types.ConfigType = None,
    default: ty.Callable[[], types.ST] | types.ST | ty.Any = ...,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> PydanticSchemaField[types.ST]: ...
@ty.overload
def SchemaField(
    schema: ty.ForwardRef | str,
    config: types.ConfigType = None,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> ty.Any: ...
@ty.overload
def SchemaField(
    schema: None = None,
    config: types.ConfigType = None,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> ty.Any: ...
