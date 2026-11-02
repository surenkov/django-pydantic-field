from __future__ import annotations

from django.apps import AppConfig

from ._internal._openapi import register_spectacular_extensions
from ._internal._rest_framework import register_serializer_field


class DjangoPydanticFieldConfig(AppConfig):
    name = "django_pydantic_field"
    verbose_name = "Django Pydantic Field"

    def ready(self) -> None:
        register_spectacular_extensions()
        register_serializer_field()
