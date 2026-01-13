import typing as ty

import typing_extensions as te
from django.utils.functional import _StrOrPromise
from rest_framework import parsers, renderers
from rest_framework.fields import Field, _DefaultInitial
from rest_framework.schemas.openapi import AutoSchema as _OpenAPIAutoSchema
from rest_framework.validators import Validator

from django_pydantic_field.types import ST, ConfigType, DeprecatedExportKwargs, ExportKwargs

__all__ = ("AutoSchema", "SchemaField", "SchemaParser", "SchemaRenderer")

@ty.type_check_only
class _FieldKwargs(te.TypedDict, ty.Generic[ST], total=False):
    read_only: bool
    write_only: bool
    required: bool
    default: _DefaultInitial[ST]
    initial: _DefaultInitial[ST]
    source: str
    label: _StrOrPromise
    help_text: _StrOrPromise
    style: dict[str, ty.Any]
    error_messages: dict[str, _StrOrPromise]
    validators: ty.Sequence[Validator[ST]]
    allow_null: bool

@ty.type_check_only
class _SchemaFieldKwargs(_FieldKwargs[ST], ExportKwargs, total=False):
    pass

@ty.type_check_only
class _DeprecatedSchemaFieldKwargs(_SchemaFieldKwargs[ST], DeprecatedExportKwargs, total=False):
    pass

class SchemaField(Field, ty.Generic[ST]):
    @ty.overload
    def __init__(
        self,
        schema: ty.Type[ST] | ty.ForwardRef | str,
        config: ConfigType | None = ...,
        *args,
        **kwargs: te.Unpack[_SchemaFieldKwargs[ST]],
    ) -> None: ...
    @ty.overload
    @te.deprecated(
        "Passing Pydantic V1 kwargs to `SchemaField` is not supported by Pydantic 2 and will be removed in future."
    )
    def __init__(
        self,
        schema: ty.Type[ST] | ty.ForwardRef | str,
        config: ConfigType | None = ...,
        *args,
        **kwargs: te.Unpack[_DeprecatedSchemaFieldKwargs[ST]],
    ) -> None: ...

class SchemaParser(parsers.JSONParser, ty.Generic[ST]):
    schema_context_key: ty.ClassVar[str]
    config_context_key: ty.ClassVar[str]

class SchemaRenderer(renderers.JSONRenderer, ty.Generic[ST]):
    schema_context_key: ty.ClassVar[str]
    config_context_key: ty.ClassVar[str]

class AutoSchema(_OpenAPIAutoSchema): ...
