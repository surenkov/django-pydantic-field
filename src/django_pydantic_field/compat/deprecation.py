from __future__ import annotations

import typing as ty
import warnings

from django_pydantic_field.compat.pydantic import PYDANTIC_V1

_MISSING = object()
_DEPRECATED_KWARGS = (
    "allow_nan",
    "indent",
    "separators",
    "skipkeys",
    "sort_keys",
)
_DEPRECATED_KWARGS_MESSAGE = "The %s= argument is not supported by Pydantic v2 and will be removed in future versions."


def truncate_deprecated_v1_export_kwargs(kwargs: dict[str, ty.Any]) -> None:
    if PYDANTIC_V1:
        return
    for kwarg in _DEPRECATED_KWARGS:
        maybe_present_kwarg = kwargs.pop(kwarg, _MISSING)
        if maybe_present_kwarg is not _MISSING:
            warnings.warn(_DEPRECATED_KWARGS_MESSAGE % (kwarg,), DeprecationWarning, stacklevel=2)
