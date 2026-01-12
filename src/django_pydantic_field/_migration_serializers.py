import warnings

from .compat.django import *  # noqa: F403

DEPRECATION_MSG = (
    "Module 'django_pydantic_field._migration_serializers' is deprecated "
    "and will be removed in version 1.0.0. "
    "Please replace it with 'django_pydantic_field.compat.django' in migrations."
)
warnings.warn(DEPRECATION_MSG, category=DeprecationWarning)
