from __future__ import annotations

import sys
import typing as ty

try:
    from functools import cached_property as cached_property
except ImportError:
    from django.utils.functional import cached_property as cached_property

if ty.TYPE_CHECKING:
    from collections.abc import Mapping


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
    try:
        return dict(vars(cls))
    except TypeError:
        return {}


if sys.version_info >= (3, 9):

    def evaluate_forward_ref(ref: ty.ForwardRef, ns: Mapping[str, ty.Any]) -> ty.Any:
        return ref._evaluate(dict(ns), {}, frozenset())

else:

    def evaluate_forward_ref(ref: ty.ForwardRef, ns: Mapping[str, ty.Any]) -> ty.Any:
        return ref._evaluate(dict(ns), {})
