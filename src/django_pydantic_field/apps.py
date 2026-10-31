from __future__ import annotations

from django.apps import AppConfig

from ._internal._openapi import register_spectacular_extensions


class DjangoPydanticFieldConfig(AppConfig):
    name = "django_pydantic_field"
    verbose_name = "Django Pydantic Field"

    def ready(self) -> None:
        register_spectacular_extensions()
