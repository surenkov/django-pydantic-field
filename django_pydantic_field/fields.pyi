from __future__ import annotations

import typing as ty

from pydantic import BaseModel, ConfigDict
from pydantic.dataclasses import DataclassClassOrWrapper

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


@ty.overload
def SchemaField(
    schema: type[ST | None] | ty.ForwardRef = ...,
    config: ConfigDict = ...,
    default: OptSchemaT | ty.Callable[[], OptSchemaT] = ...,
    *args,
    null: ty.Literal[True],
    **kwargs,
) -> ST | None:
    ...


@ty.overload
def SchemaField(
    schema: type[ST] | ty.ForwardRef = ...,
    config: ConfigDict = ...,
    default: ty.Union[SchemaT, ty.Callable[[], SchemaT]] = ...,
    *args,
    null: ty.Literal[False] = ...,
    **kwargs,
) -> ST:
    ...
