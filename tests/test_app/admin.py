from __future__ import annotations

import typing as ty

from django.contrib import admin
from django.db.models import Field

from . import models

json_formfield_overrides: dict[type[Field[ty.Any, ty.Any]], dict[str, ty.Any]]
json_schema_formfield_overrides: dict[type[Field[ty.Any, ty.Any]], dict[str, ty.Any]]

try:
    from django_jsonform.widgets import JSONFormWidget

    from django_pydantic_field.v2.fields import PydanticSchemaField
    from django_pydantic_field.v2.forms import JSONFormSchemaWidget

    json_formfield_overrides = {PydanticSchemaField: {"widget": JSONFormWidget}}
    json_schema_formfield_overrides = {PydanticSchemaField: {"widget": JSONFormSchemaWidget}}
except ImportError:
    json_formfield_overrides = {}
    json_schema_formfield_overrides = {}


@admin.register(models.SampleModel)
class SampleModelAdmin(admin.ModelAdmin):
    pass


@admin.register(models.SampleForwardRefModel)
class SampleForwardRefModelAdmin(admin.ModelAdmin):
    formfield_overrides = json_formfield_overrides


@admin.register(models.SampleModelWithRoot)
class SampleModelWithRootAdmin(admin.ModelAdmin):
    formfield_overrides = json_schema_formfield_overrides


@admin.register(models.ExampleModel)
class ExampleModelAdmin(admin.ModelAdmin):
    pass
