from __future__ import annotations

import sys
import typing as ty

from django_pydantic_field.compat import typing

if ty.TYPE_CHECKING:
    get_annotations: ty.Callable[[ty.Any], dict[str, ty.Any]]

try:
    from annotationlib import get_annotations  # type: ignore[unresolved-import] # Python >= 3.14
except ImportError:

    def get_annotations(obj: ty.Any) -> dict[str, ty.Any]:
        if isinstance(obj, type):
            return obj.__dict__["__annotations__"]
        else:
            return obj.__annotations__


def get_annotated_type(obj, field, default=None) -> ty.Any:
    try:
        annotations = get_annotations(obj)

        return annotations[field]
    except (AttributeError, KeyError):
        return default


def get_namespace(cls) -> dict[str, ty.Any]:
    return dict(get_global_namespace(cls), **get_local_namespace(cls))


def get_global_namespace(cls) -> dict[str, ty.Any]:
    try:
        module = cls.__module__
        return vars(sys.modules[module])
    except (KeyError, AttributeError):
        return {}


def get_local_namespace(cls) -> dict[str, ty.Any]:
    try:
        return vars(cls)
    except TypeError:
        return {}


def get_origin_type(cls: type):
    origin_tp = typing.get_origin(cls)
    if origin_tp is not None:
        return origin_tp
    return cls
