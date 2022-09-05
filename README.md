![PyPI Version](https://img.shields.io/pypi/v/django-pydantic-field)

# Django + Pydantic = 🖤

Django JSONField with Pydantic models as a Schema

## Usage

Install the package with `pip install django-pydantic-field`.

``` python
import pydantic

from django.db import models
from django_pydantic_field import PydanticSchemaField


class Foo(pydantic.BaseModel):
    count: int
    size: float = 1.0


class Bar(pydantic.BaseModel):
    slug: str = "foo_bar"


class MyModel(models.Model):
    foo_field = PydanticSchemaField(schema=Foo)
    bar_list = PydanticSchemaField(schema=list[Bar])

...
    
model = MyModel(foo_field={"count": "5"}, bar_list=[{}])
model.save()

assert model.foo_field == Foo(count=5, size=1.0)
assert model.bar_list == [Bar(slug="foo_bar")]
```


### Django REST Framework support

``` python
from rest_framework import serializers
from django_pydantic_field.rest_framework import PydanticSchemaField


class MyModelSerializer(serializers.ModelSerializer):
    foo_field = PydanticSchemaField(schema=Foo)

    class Meta:
        model = MyModel
        fields = '__all__'
```

Global approach with typed `parser` and `renderer` classes
``` python
from rest_framework import views
from rest_framework.decorators import api_view, parser_classes, renderer_classes
from django_pydantic_field.rest_framework import PydanticSchemaRenderer, PydanticSchemaParser


@api_view(["POST"])
@parser_classes([PydanticSchemaParser[Foo]]):
@renderer_classes([PydanticSchemaRenderer[list[Foo]]])
def foo_view(request):
    assert isinstance(request.data, Foo)

    count = request.data.count + 1
    return Response([Foo(count=count)])


class FooClassBasedView(views.APIView):
    parser_classes = [PydanticSchemaParser[Foo]]
    renderer_classes = [PydanticSchemaRenderer[list[Foo]]]

    def get(self, request, *args, **kwargs):
        assert isinstance(request.data, Foo)
        return Response([request.data])

    def put(self, request, *args, **kwargs):
        assert isinstance(request.data, Foo)

        count = request.data.count + 1
        return Response([request.data])
```

## Acknowledgement

* [Churkin Oleg](https://gist.github.com/Bahus/98a9848b1f8e2dcd986bf9f05dbf9c65) for his Gist as a source of inspiration;
* Boutique Air Flight Operations platform as a test ground;

