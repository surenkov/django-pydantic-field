from django.db.models.fields import NOT_PROVIDED

from django_pydantic_field import types
from django_pydantic_field.fields import PydanticSchemaField as _PydanticSchemaField
from django_pydantic_field.v1 import forms
from django_pydantic_field.v1.types import V1SchemaAdapterResolver

__all__ = ("PydanticSchemaField", "SchemaField")


class PydanticSchemaField(V1SchemaAdapterResolver, _PydanticSchemaField[types.ST]):
    @classmethod
    def get_default_form_class(cls):
        return forms.SchemaField


def SchemaField(schema=None, config=None, default=NOT_PROVIDED, *args, **kwargs):
    return PydanticSchemaField(schema, config, default=default, *args, **kwargs)
