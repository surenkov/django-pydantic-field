from __future__ import annotations

import json
import typing as ty
import typing_extensions as te

from django.forms.fields import JSONField
from django.forms.widgets import Widget
from django.utils.functional import _StrOrPromise

from .fields import ST, ConfigType, _ExportKwargs

__all__ = ("SchemaField",)

class _FieldKwargs(ty.TypedDict, total=False):
    required: bool
    widget: Widget | type[Widget] | None
    label: _StrOrPromise | None
    initial: ty.Any | None
    help_text: _StrOrPromise
    error_messages: ty.Mapping[str, _StrOrPromise] | None
    show_hidden_initial: bool
    validators: ty.Sequence[ty.Callable[[ty.Any], None]]
    localize: bool
    disabled: bool
    label_suffix: str | None

class _CharFieldKwargs(_FieldKwargs, total=False):
    max_length: int | None
    min_length: int | None
    strip: bool
    empty_value: ty.Any

class _JSONFieldKwargs(_CharFieldKwargs, total=False):
    encoder: ty.Callable[[], json.JSONEncoder] | None
    decoder: ty.Callable[[], json.JSONDecoder] | None

class _SchemaFieldKwargs(_ExportKwargs, _JSONFieldKwargs, total=False):
    allow_null: bool | None


class _DeprecatedSchemaFieldKwargs(_SchemaFieldKwargs, total=False):
    allow_nan: ty.Any
    indent: ty.Any
    separators: ty.Any
    skipkeys: ty.Any
    sort_keys: ty.Any


class SchemaField(JSONField, ty.Generic[ST]):
    @ty.overload
    def __init__(
        self,
        schema: ty.Type[ST] | ty.ForwardRef | str,
        config: ConfigType | None = ...,
        *args,
        **kwargs: te.Unpack[_SchemaFieldKwargs],
    ) -> None: ...
    @ty.overload
    @te.deprecated("Passing `json.dump` kwargs to `SchemaField` is not supported by Pydantic 2 and will be removed in the future versions.")
    def __init__(
        self,
        schema: ty.Type[ST] | ty.ForwardRef | str,
        config: ConfigType | None = ...,
        *args,
        **kwargs: te.Unpack[_DeprecatedSchemaFieldKwargs],
    ) -> None: ...
