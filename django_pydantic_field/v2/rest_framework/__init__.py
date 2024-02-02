from django_pydantic_field.compat import PYDANTIC_V2

from . import coreapi as coreapi
from . import openapi as openapi
from .fields import SchemaField as SchemaField
from .parsers import SchemaParser as SchemaParser
from .renderers import SchemaRenderer as SchemaRenderer

_DEPRECATED_MESSAGE = (
    "`django_pydantic_field.rest_framework.AutoSchema` is deprecated, "
    "please use explicit imports for `django_pydantic_field.rest_framework.openapi.AutoSchema` "
    "or `django_pydantic_field.rest_framework.coreapi.AutoSchema` instead."
)

__all__ = (
    "coreapi",
    "openapi",
    "SchemaField",
    "SchemaParser",
    "SchemaRenderer",
    "AutoSchema",  # type: ignore
)


def __getattr__(key):
    if key == "AutoSchema" and PYDANTIC_V2:
        import warnings

        from .openapi import AutoSchema

        warnings.warn(_DEPRECATED_MESSAGE, DeprecationWarning)
        return AutoSchema

    raise AttributeError(key)
