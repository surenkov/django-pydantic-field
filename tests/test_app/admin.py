from django.contrib import admin

from . import models


@admin.register(models.SampleModel)
class SampleModelAdmin(admin.ModelAdmin):
    pass


@admin.register(models.SampleForwardRefModel)
class SampleForwardRefModelAdmin(admin.ModelAdmin):
    pass


@admin.register(models.ExampleModel)
class ExampleModelAdmin(admin.ModelAdmin):
    pass
