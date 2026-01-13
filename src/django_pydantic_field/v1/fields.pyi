import typing as ty

from django.db.models.fields import NOT_PROVIDED
from django_pydantic_field.fields import PydanticSchemaField as _PydanticSchemaField
from django_pydantic_field import types

class PydanticSchemaField(_PydanticSchemaField[types.ST]): ...

@ty.overload
def SchemaField(
    schema: ty.ForwardRef | str | None = None,
    config: types.ConfigType = None,
    default: ty.Any = NOT_PROVIDED,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> ty.Any: ...
@ty.overload
def SchemaField(
    schema: type[types.ST],
    config: types.ConfigType = None,
    default: ty.Any = NOT_PROVIDED,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> PydanticSchemaField[types.ST]: ...
def SchemaField(
    schema: ty.Any = None,
    config: types.ConfigType = None,
    default: ty.Any = NOT_PROVIDED,
    *args: ty.Any,
    **kwargs: ty.Any,
) -> ty.Any: ...
