from __future__ import annotations

from django.apps import AppConfig

from .compat.pydantic import PYDANTIC_V2


class DjangoPydanticFieldConfig(AppConfig):
    name = "django_pydantic_field"
    verbose_name = "Django Pydantic Field"

    def ready(self) -> None:
        if not PYDANTIC_V2:
            return
        try:
            import drf_spectacular  # noqa: F401
        except ImportError:
            pass
        else:
            from . import spectacular  # noqa: F401
