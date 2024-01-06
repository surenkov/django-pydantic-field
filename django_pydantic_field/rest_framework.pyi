import typing as ty
import typing_extensions as te

from rest_framework import parsers, renderers
from rest_framework.fields import _DefaultInitial, Field
from rest_framework.validators import Validator

from django.utils.functional import _StrOrPromise

from .fields import ST, ConfigType, _ExportKwargs

__all__ = ("SchemaField", "SchemaParser", "SchemaRenderer")

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

class _SchemaFieldKwargs(_FieldKwargs[ST], _ExportKwargs, total=False):
    pass

class _DeprecatedSchemaFieldKwargs(_SchemaFieldKwargs[ST], total=False):
    allow_nan: ty.Any
    indent: ty.Any
    separators: ty.Any
    skipkeys: ty.Any
    sort_keys: ty.Any

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
    @te.deprecated("Passing `json.dump` kwargs to `SchemaField` is not supported by Pydantic 2 and will be removed in the future versions.")
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
