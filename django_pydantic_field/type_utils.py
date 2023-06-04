from __future__ import annotations

import sys
import typing as ty
import warnings

from pydantic import BaseModel, ConfigDict, PydanticUserError, TypeAdapter
from typing_extensions import Protocol

try:
    from functools import cached_property
except ImportError:
    from django.utils.functional import cached_property  # type: ignore[misc]


class Dataclass(Protocol):
    __dataclass_fields__: ty.ClassVar[dict[str, ty.Any]]
    __dataclass_params__: ty.ClassVar[ty.Any]  # in reality `dataclasses._DataclassParams`
    __post_init__: ty.ClassVar[ty.Callable[..., None]]

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass


SchemaT = ty.TypeVar(
    "SchemaT",
    BaseModel,
    TypeAdapter,
    Dataclass,
    ty.Sequence[ty.Any],
    ty.Mapping[str, ty.Any],
    ty.Set[ty.Any],
    ty.FrozenSet[ty.Any],
    None,
)


def type_adapter(schema: type[SchemaT] | None, config: ConfigDict | None = None, *, allow_null: bool = False):
    if allow_null:
        schema = ty.Optional[schema]  # type: ignore
    try:
        adapter = TypeAdapter(schema, config=config, _parent_depth=3)  # type: ignore
    except PydanticUserError as exc:
        warnings.warn(str(exc))
        adapter = TypeAdapter(schema, _parent_depth=3)  # type: ignore
    return adapter


def get_type_annotation(cls: type, field: str) -> type[SchemaT]:
    globalns, localns = get_namespaces(cls)
    annotations = ty.get_type_hints(cls, globalns, localns)
    return annotations[field]


def get_raw_annotation(cls: type, field: str) -> ty.Any:
    try:
        return cls.__annotations__[field]
    except (AttributeError, KeyError):
        return None


def evaluate_forward_ref(cls: type, ref: ty.ForwardRef):
    from pydantic._internal._typing_extra import evaluate_fwd_ref

    globalns, localns = get_namespaces(cls)
    return evaluate_fwd_ref(ref, globalns, localns)


def get_namespaces(cls: type) -> tuple[dict[str, ty.Any], dict[str, ty.Any]]:
    try:
        module = sys.modules[cls.__module__]
        globalns = vars(module)
    except KeyError:
        globalns = {}

    localns = dict(vars(cls))
    return globalns, localns
