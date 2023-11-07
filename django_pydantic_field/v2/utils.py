from __future__ import annotations

import sys
import typing as ty

try:
    from functools import cached_property
except ImportError:
    from django.utils.functional import cached_property


def get_annotated_type(obj, field, default=None) -> ty.Any:
    try:
        if isinstance(obj, type):
            annotations = obj.__dict__["__annotations__"]
        else:
            annotations = obj.__annotations__

        return annotations[field]
    except (AttributeError, KeyError):
        return default


def get_global_namespace(cls) -> dict[str, ty.Any]:
    try:
        module = cls.__module__
        return vars(sys.modules[module])
    except (KeyError, AttributeError):
        return {}


def get_local_namespace(cls) -> dict[str, ty.Any]:
    return dict(vars(cls))
