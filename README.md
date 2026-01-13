[![PyPI Version](https://img.shields.io/pypi/v/django-pydantic-field)](https://pypi.org/project/django-pydantic-field/)
[![Lint and Test Package](https://github.com/surenkov/django-pydantic-field/actions/workflows/python-test.yml/badge.svg)](https://github.com/surenkov/django-pydantic-field/actions/workflows/python-test.yml)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/django-pydantic-field)](https://pypistats.org/packages/django-pydantic-field)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/django-pydantic-field)](https://pypi.org/project/django-pydantic-field/)
[![Supported Django Versions](https://img.shields.io/pypi/frameworkversions/django/django-pydantic-field)](https://pypi.org/project/django-pydantic-field/)

# Type-Safe Pydantic Schemas for Django JSONFields

`django-pydantic-field` provides a way to use Pydantic models as schemas for Django's `JSONField`.
It offers full support for Pydantic v1 and v2, type safety and integration with Django's ecosystem, including Forms and Django REST Framework.

## Highlights

- **Unified API**: Transparent support for Pydantic v1 and v2 through the `SchemaAdapter`s.
- **Type-Safe**: Support for static type checking (ty/mypy/pyright) with type inference for models and annotations.
- **Forward References**: Lazy resolution of forward references, allowing schemas to be defined anywhere.
- **Django Integration**: Support for Django Forms and the Admin interface.
- **DRF Support**: Typed Serializers, Parsers, and Renderers with automatic OpenAPI schema generation via DRF's native schema generator.

## Installation

```bash
pip install django-pydantic-field
```

## Basic Usage

The `SchemaField` can be used by passing the schema as the first argument (Django-like style) or by using type annotations.

```python
import pydantic
import typing

from django.db import models
from django_pydantic_field import SchemaField


class Foo(pydantic.BaseModel):
    count: int
    slug: str = "default"


class MyModel(models.Model):
    # Django-like style (explicit schema)
    bar = SchemaField(Foo, default={"count": 5})

    # Annotation-based style (Pydantic-like)
    foo: Foo = SchemaField()

    # Supports standard Python types and annotations
    items: list[Foo] = SchemaField(default=list)

    # null=True correctly infers t.Optional[Foo] for type checkers
    optional_foo = SchemaField(Foo, null=True, default=None)

model = MyModel(foo={"count": 42})
model.save()

# Data is automatically parsed into Pydantic models
assert isinstance(model.foo, Foo)
assert model.foo.count == 42

typing.assert_type(model.optional_foo, Foo | None)
```

### Supported Types

Any type supported by Pydantic can be used as a schema:
- `pydantic.BaseModel` and `pydantic.RootModel` (v2)
- Standard Python types (`list[str]`, `dict[int, float]`, etc.)
- `dataclasses.dataclass` and `TypedDict` protocols
- `typing.Annotated` with metadata.

```python
from typing import Annotated
from pydantic import Field


class AdvancedModel(models.Model):
    # Annotated with validation rules
    positive_ints: Annotated[list[int], Field(min_length=1)] = SchemaField()
```

### Forward References & Lazy Resolution

`SchemaField` supports forward references via string literals or `typing.ForwardRef`. Resolution is deferred until the first time the field is accessed.

```python
import typing


class MyModel(models.Model):
    foo = SchemaField(typing.ForwardRef("DeferredFoo"))
    another_foo: "DeferredFoo" = SchemaField()


class DeferredFoo(pydantic.BaseModel):
    ...
```

## Pydantic Version Support

The package automatically detects the Pydantic version in your environment and adapts accordingly.

For Pydantic v2 environments, you can still explicitly use Pydantic v1 models by importing from the `.v1` subpackage:

```python
from pydantic import v1 as pydantic_v1
from django_pydantic_field.v1 import SchemaField as SchemaFieldV1


class LegacySchema(pydantic_v1.BaseModel):
    ...


class LegacyModel(models.Model):
    legacy_field = SchemaFieldV1(LegacySchema)
```

## Django Forms & Admin

It is possible to create Django forms, which would validate against the given schema:

```python
from django import forms
from django_pydantic_field.forms import SchemaField


class FooForm(forms.Form):
    field = SchemaField(Foo)


form = FooForm(data={"field": '{"slug": "asdf", "count": 1}'})
assert form.is_valid()
```

### `django-jsonform` support

For a better user experience in the Admin, you can use [`django-jsonform`](https://django-jsonform.readthedocs.io), which provides a dynamic editor based on the Pydantic model's JSON schema.

```python
from django.contrib import admin
from django_pydantic_field import fields
from django_jsonform.widgets import JSONFormWidget

class MyModelAdmin(admin.ModelAdmin):
    formfield_overrides = {
        fields.PydanticSchemaField: {"widget": JSONFormWidget},
    }
```

## Django REST Framework

### Serializers

```python
from rest_framework import serializers
from django_pydantic_field.rest_framework import SchemaField


class MySerializer(serializers.Serializer):
    pydantic_field = SchemaField(Foo)
```

### Typed Views (Parsers & Renderers)

You can use `SchemaParser` and `SchemaRenderer` to handle Pydantic models directly in your views.

```python
from rest_framework.decorators import api_view, parser_classes, renderer_classes
from rest_framework.response import Response
from django_pydantic_field.rest_framework import SchemaParser, SchemaRenderer

@api_view(["POST"])
@parser_classes([SchemaParser[Foo]])
@renderer_classes([SchemaRenderer[list[Foo]]])
def foo_view(request):
    # request.data is a Foo instance
    instance: Foo = request.data
    return Response([instance])
```

### OpenAPI Generation

`django-pydantic-field` provides an `AutoSchema` that automatically generates OpenAPI definitions for your Pydantic-backed DRF components.
```python
from django_pydantic_field.rest_framework import AutoSchema

class SampleView(generics.RetrieveAPIView):
    serializer_class = MySerializer
    schema = AutoSchema()
```

## System Checks

The field performs validation during Django's `manage.py check` command:
- `pydantic.E001`: Schema resolution errors.
- `pydantic.E002`: Default value serialization errors.
- `pydantic.W003`: Data integrity warnings for `include`/`exclude` configurations.

## Contributing
To get `django-pydantic-field` up and running in development mode:
1.  [Install `uv`](https://docs.astral.sh/uv/getting-started/installation/);
2.  Install the project and its dependencies: `uv sync`;
3.  Setup `pre-commit`: `pre-commit install`.
4.  Run tests: `make test`.
5.  Run linters: `make lint`.

## Acknowledgement
* [Churkin Oleg](https://gist.github.com/Bahus/98a9848b1f8e2dcd986bf9f05dbf9c65) for his Gist as a source of inspiration
