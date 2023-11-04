from __future__ import annotations

import typing as ty

from pydantic import BaseModel
from pydantic.dataclasses import DataclassClassOrWrapper

from .compat.pydantic import PYDANTIC_V1, PYDANTIC_V2

__all__ = ("SchemaField",)

SchemaT: ty.TypeAlias = ty.Union[
    BaseModel,
    DataclassClassOrWrapper,
    ty.Sequence[ty.Any],
    ty.Mapping[str, ty.Any],
    ty.Set[ty.Any],
    ty.FrozenSet[ty.Any],
]
OptSchemaT: ty.TypeAlias = ty.Optional[SchemaT]
ST = ty.TypeVar("ST", bound=SchemaT)

ConfigType: ty.TypeAlias = ty.Any

if PYDANTIC_V1:
    from pydantic import ConfigDict, BaseConfig

    ConfigType = ty.Union[ConfigDict, type[BaseConfig], type]
elif PYDANTIC_V2:
    from pydantic import ConfigDict

    ConfigType = ConfigDict


@ty.overload
def SchemaField(
    schema: type[ST | None] | ty.ForwardRef = ...,
    config: ConfigType = ...,
    default: OptSchemaT | ty.Callable[[], OptSchemaT] = ...,
    *args,
    null: ty.Literal[True],
    **kwargs,
) -> ST | None:
    ...


@ty.overload
def SchemaField(
    schema: type[ST] | ty.ForwardRef = ...,
    config: ConfigType = ...,
    default: ty.Union[SchemaT, ty.Callable[[], SchemaT]] = ...,
    *args,
    null: ty.Literal[False] = ...,
    **kwargs,
) -> ST:
    ...

def SchemaField(*args, **kwargs) -> ty.Any:
    ...
