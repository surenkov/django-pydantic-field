from __future__ import annotations

import json
import typing as ty
import typing_extensions as te

import typing_extensions as te
from pydantic import BaseConfig, BaseModel, ConfigDict

try:
    from pydantic.dataclasses import DataclassClassOrWrapper as PydanticDataclass
except ImportError:
    from pydantic._internal._dataclasses import PydanticDataclass as PydanticDataclass

__all__ = ("SchemaField",)

SchemaT: ty.TypeAlias = ty.Union[
    BaseModel,
    PydanticDataclass,
    ty.Sequence[ty.Any],
    ty.Mapping[str, ty.Any],
    ty.Set[ty.Any],
    ty.FrozenSet[ty.Any],
]
OptSchemaT: ty.TypeAlias = ty.Optional[SchemaT]
ST = ty.TypeVar("ST", bound=SchemaT)
IncEx = ty.Union[ty.Set[int], ty.Set[str], ty.Dict[int, ty.Any], ty.Dict[str, ty.Any]]
ConfigType = ty.Union[ConfigDict, ty.Type[BaseConfig], type]

class _FieldKwargs(te.TypedDict, total=False):
    name: str | None
    verbose_name: str | None
    primary_key: bool
    max_length: int | None
    unique: bool
    blank: bool
    db_index: bool
    rel: ty.Any
    editable: bool
    serialize: bool
    unique_for_date: str | None
    unique_for_month: str | None
    unique_for_year: str | None
    choices: ty.Sequence[ty.Tuple[str, str]] | None
    help_text: str | None
    db_column: str | None
    db_tablespace: str | None
    auto_created: bool
    validators: ty.Sequence[ty.Callable] | None
    error_messages: ty.Mapping[str, str] | None
    db_comment: str | None

class _JSONFieldKwargs(_FieldKwargs, total=False):
    encoder: ty.Callable[[], json.JSONEncoder]
    decoder: ty.Callable[[], json.JSONDecoder]

class _ExportKwargs(te.TypedDict, total=False):
    strict: bool
    from_attributes: bool
    mode: te.Literal["json", "python"]
    include: IncEx | None
    exclude: IncEx | None
    by_alias: bool
    exclude_unset: bool
    exclude_defaults: bool
    exclude_none: bool
    round_trip: bool
    warnings: bool

class _SchemaFieldKwargs(_JSONFieldKwargs, _ExportKwargs, total=False): ...

class _DeprecatedSchemaFieldKwargs(_SchemaFieldKwargs, total=False):
    allow_nan: ty.Any
    indent: ty.Any
    separators: ty.Any
    skipkeys: ty.Any
    sort_keys: ty.Any

@ty.overload
def SchemaField(
    schema: ty.Type[ST] | None | ty.ForwardRef = ...,
    config: ConfigType = ...,
    default: OptSchemaT | ty.Callable[[], OptSchemaT] = ...,
    *args,
    null: ty.Literal[True],
    **kwargs: te.Unpack[_SchemaFieldKwargs],
) -> ST | None: ...
@ty.overload
def SchemaField(
    schema: ty.Type[ST] | ty.ForwardRef = ...,
    config: ConfigType = ...,
    default: ty.Union[SchemaT, ty.Callable[[], SchemaT]] = ...,
    *args,
    null: ty.Literal[False] = ...,
    **kwargs: te.Unpack[_SchemaFieldKwargs],
) -> ST: ...
@ty.overload
@te.deprecated("Passing `json.dump` kwargs to `SchemaField` is not supported by Pydantic 2 and will be removed in the future versions.")
def SchemaField(
    schema: ty.Type[ST] | None | ty.ForwardRef = ...,
    config: ConfigType = ...,
    default: ty.Union[SchemaT, ty.Callable[[], SchemaT]] = ...,
    *args,
    null: ty.Literal[True],
    **kwargs: te.Unpack[_DeprecatedSchemaFieldKwargs],
) -> ST | None: ...
@ty.overload
@te.deprecated("Passing `json.dump` kwargs to `SchemaField` is not supported by Pydantic 2 and will be removed in the future versions.")
def SchemaField(
    schema: ty.Type[ST] | ty.ForwardRef = ...,
    config: ConfigType = ...,
    default: ty.Union[SchemaT, ty.Callable[[], SchemaT]] = ...,
    *args,
    null: ty.Literal[False] = ...,
    **kwargs: te.Unpack[_DeprecatedSchemaFieldKwargs],
) -> ST: ...
