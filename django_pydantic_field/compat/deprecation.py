from __future__ import annotations

import typing as ty
import warnings

_NOT_PROVIDED = object()
_DEPRECATED_KWARGS = (
    "allow_nan",
    "indent",
    "separators",
    "skipkeys",
    "sort_keys",
)
_DEPRECATED_KWARGS_MESSAGE = (
    "The `%s=` argument is not supported by Pydantic v2 and will be removed in the future versions."
)


def truncate_deprecated_v1_export_kwargs(kwargs: dict[str, ty.Any]) -> None:
    for kwarg in _DEPRECATED_KWARGS:
        maybe_present_kwarg = kwargs.pop(kwarg, _NOT_PROVIDED)
        if maybe_present_kwarg is not _NOT_PROVIDED:
            warnings.warn(_DEPRECATED_KWARGS_MESSAGE % kwarg, DeprecationWarning, stacklevel=2)
