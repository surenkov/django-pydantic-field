from .fields import SchemaField as SchemaField
from .parsers import SchemaParser as SchemaParser
from .renderers import SchemaRenderer as SchemaRenderer

_DEPRECATED_MESSAGE = (
    "`django_pydantic_field.rest_framework.AutoSchema` is deprecated, "
    "please use explicit imports for `django_pydantic_field.rest_framework.openapi.AutoSchema` "
    "or `django_pydantic_field.rest_framework.coreapi.AutoSchema` instead."
)

def __getattr__(key):
    if key == "AutoSchema":
        import warnings

        from .openapi import AutoSchema

        warnings.warn(_DEPRECATED_MESSAGE, DeprecationWarning)
        return AutoSchema

    raise AttributeError(key)
