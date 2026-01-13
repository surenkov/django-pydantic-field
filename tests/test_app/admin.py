from django.contrib import admin

try:
    from django_jsonform.widgets import JSONFormWidget

    from django_pydantic_field.v2.fields import PydanticSchemaField
    from django_pydantic_field.v2.forms import JSONFormSchemaWidget

    json_formfield_overrides = {PydanticSchemaField: {"widget": JSONFormWidget}}
    json_schema_formfield_overrides = {PydanticSchemaField: {"widget": JSONFormSchemaWidget}}
except ImportError:
    json_formfield_overrides = {}
    json_schema_formfield_overrides = {}

from . import models


@admin.register(models.SampleModel)
class SampleModelAdmin(admin.ModelAdmin):
    pass


@admin.register(models.SampleForwardRefModel)
class SampleForwardRefModelAdmin(admin.ModelAdmin):
    formfield_overrides = json_formfield_overrides  # type: ignore


@admin.register(models.SampleModelWithRoot)
class SampleModelWithRootAdmin(admin.ModelAdmin):
    formfield_overrides = json_schema_formfield_overrides  # type: ignore


@admin.register(models.ExampleModel)
class ExampleModelAdmin(admin.ModelAdmin):
    pass
