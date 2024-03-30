[![PyPI Version](https://img.shields.io/pypi/v/django-pydantic-field)](https://pypi.org/project/django-pydantic-field/)
[![Lint and Test Package](https://github.com/surenkov/django-pydantic-field/actions/workflows/python-test.yml/badge.svg)](https://github.com/surenkov/django-pydantic-field/actions/workflows/python-test.yml)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/django-pydantic-field)](https://pypistats.org/packages/django-pydantic-field)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/django-pydantic-field)](https://pypi.org/project/django-pydantic-field/)
[![Supported Django Versions](https://img.shields.io/pypi/frameworkversions/django/django-pydantic-field)](https://pypi.org/project/django-pydantic-field/)

# Django + Pydantic = 🖤

Django JSONField with Pydantic models as a Schema.

**Now supports both Pydantic v1 and v2!** [Please join the discussion](https://github.com/surenkov/django-pydantic-field/discussions/36) if you have any thoughts or suggestions!

## Usage

Install the package with `pip install django-pydantic-field`.

``` python
import pydantic
from datetime import date
from uuid import UUID

from django.db import models
from django_pydantic_field import SchemaField


class Foo(pydantic.BaseModel):
    count: int
    size: float = 1.0


class Bar(pydantic.BaseModel):
    slug: str = "foo_bar"


class MyModel(models.Model):
    # Infer schema from field annotation
    foo_field: Foo = SchemaField()

    # or explicitly pass schema to the field
    bar_list: typing.Sequence[Bar] = SchemaField(schema=list[Bar])

    # Pydantic exportable types are supported
    raw_date_map: dict[int, date] = SchemaField()
    raw_uids: set[UUID] = SchemaField()

...
    
model = MyModel(
    foo_field={"count": "5"},
    bar_list=[{}],
    raw_date_map={1: "1970-01-01"},
    raw_uids={"17a25db0-27a4-11ed-904a-5ffb17f92734"}
)
model.save()

assert model.foo_field == Foo(count=5, size=1.0)
assert model.bar_list == [Bar(slug="foo_bar")]
assert model.raw_date_map == {1: date(1970, 1, 1)}
assert model.raw_uids == {UUID("17a25db0-27a4-11ed-904a-5ffb17f92734")}
```

Practically, schema could be of any type supported by Pydantic.
In addition, an external `config` class can be passed for such schemes.

### Forward referencing annotations

It is also possible to use `SchemaField` with forward references and string literals, e.g the code below is also valid:

``` python

class MyModel(models.Model):
    foo_field: "Foo" = SchemaField()
    bar_list: typing.Sequence["Bar"] = SchemaField(schema=typing.ForwardRef("list[Bar]"))


class Foo(pydantic.BaseModel):
    count: int
    size: float = 1.0


class Bar(pydantic.BaseModel):
    slug: str = "foo_bar"
```

**Pydantic v2 specific**: this behaviour is achieved by the fact that the exact type resolution will be postponed the until initial access to the field. Usually this happens on the first instantiation of the model.

To reduce the number of runtime errors related to the postponed resolution, the field itself performs a few checks against the passed schema during `./manage.py check` command invocation, and consequently, in `runserver` and `makemigrations` commands.

Here's the list of currently implemented checks:
- `pydantic.E001`: The passed schema could not be resolved. Most likely it does not exist in the scope of the defined field.
- `pydantic.E002`: `default=` value could not be serialized to the schema.
- `pydantic.W003`: The default value could not be reconstructed to the schema due to `include`/`exclude` configuration.


### `typing.Annotated` support
As of `v0.3.5`, SchemaField also supports `typing.Annotated[...]` expressions, both through `schema=` attribute or field annotation syntax; though I find the `schema=typing.Annotated[...]` variant highly discouraged.

**The current limitation** is not in the field itself, but in possible `Annotated` metadata -- practically it can contain anything, and Django migrations serializers could refuse to write it to migrations.
For most relevant types in context of Pydantic, I wrote the specific serializers (particularly for `pydantic.FieldInfo`, `pydantic.Representation` and raw dataclasses), thus it should cover the majority of `Annotated` use cases.

## Django Forms support

It is possible to create Django forms, which would validate against the given schema:

``` python
from django import forms
from django_pydantic_field.forms import SchemaField


class Foo(pydantic.BaseModel):
    slug: str = "foo_bar"


class FooForm(forms.Form):
    field = SchemaField(Foo)  # `typing.ForwardRef("Foo")` is fine too, but only in Django 4+


form = FooForm(data={"field": '{"slug": "asdf"}'})
assert form.is_valid()
assert form.cleaned_data["field"] == Foo(slug="asdf")
```

`django_pydantic_field` also supports auto-generated fields for `ModelForm` and `modelform_factory`:

``` python
class FooModelForm(forms.ModelForm):
    class Meta:
        model = Foo
        fields = ["field"]

form = FooModelForm(data={"field": '{"slug": "asdf"}'})
assert form.is_valid()
assert form.cleaned_data["field"] == Foo(slug="asdf")

...

# ModelForm factory support
AnotherFooModelForm = modelform_factory(Foo, fields=["field"])
form = AnotherFooModelForm(data={"field": '{"slug": "bar_baz"}'})

assert form.is_valid()
assert form.cleaned_data["field"] == Foo(slug="bar_baz")
```

Note, that forward references would be resolved until field is being bound to the form instance.

## Django REST Framework support

``` python
from rest_framework import generics, serializers
from django_pydantic_field.rest_framework import SchemaField, AutoSchema


class MyModelSerializer(serializers.ModelSerializer):
    foo_field = SchemaField(schema=Foo)

    class Meta:
        model = MyModel
        fields = '__all__'


class SampleView(generics.RetrieveAPIView):
    serializer_class = MyModelSerializer

    # optional support of OpenAPI schema generation for Pydantic fields
    schema = AutoSchema()
```

Global approach with typed `parser` and `renderer` classes
``` python
from rest_framework import views
from rest_framework.decorators import api_view, parser_classes, renderer_classes
from django_pydantic_field.rest_framework import SchemaRenderer, SchemaParser, AutoSchema


@api_view(["POST"])
@parser_classes([SchemaParser[Foo]]):
@renderer_classes([SchemaRenderer[list[Foo]]])
def foo_view(request):
    assert isinstance(request.data, Foo)

    count = request.data.count + 1
    return Response([Foo(count=count)])


class FooClassBasedView(views.APIView):
    parser_classes = [SchemaParser[Foo]]
    renderer_classes = [SchemaRenderer[list[Foo]]]

    # optional support of OpenAPI schema generation for Pydantic parsers/renderers
    schema = AutoSchema()

    def get(self, request, *args, **kwargs):
        assert isinstance(request.data, Foo)
        return Response([request.data])

    def put(self, request, *args, **kwargs):
        assert isinstance(request.data, Foo)

        count = request.data.count + 1
        return Response([request.data])
```

## Contributing
To get `django-pydantic-field` up and running in development mode:
1. Clone this repo;
1. Create a virtual environment: `python -m venv .venv`;
1. Activate `.venv`: `. .venv/bin/activate`;
1. Install the project and its dependencies: `pip install -e .[dev,test]`;
1. Setup `pre-commit`: `pre-commit install`.

## Acknowledgement

* [Churkin Oleg](https://gist.github.com/Bahus/98a9848b1f8e2dcd986bf9f05dbf9c65) for his Gist as a source of inspiration;
* Boutique Air Flight Operations platform as a test ground;

