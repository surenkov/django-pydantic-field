import io
import typing as t
from datetime import date

import pytest

from rest_framework import serializers, views, exceptions
from rest_framework.decorators import api_view, renderer_classes, parser_classes
from rest_framework.response import Response

from django_pydantic_field import rest_framework

from .conftest import InnerSchema


class Serializer(serializers.Serializer):
    field = rest_framework.PydanticSchemaField(schema=t.List[InnerSchema])


def test_schema_field():
    field = rest_framework.PydanticSchemaField(InnerSchema)
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = {"stub_str": "abc", "stub_int": 1, "stub_list": [date(2022, 7, 1)]}

    assert field.to_representation(existing_instance) == expected_encoded
    assert field.to_internal_value(expected_encoded) == existing_instance


def test_field_schema_with_custom_config():
    field = rest_framework.PydanticSchemaField(InnerSchema, exclude={"stub_int"})
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}

    assert field.to_representation(existing_instance) == expected_encoded
    assert field.to_internal_value(expected_encoded) == existing_instance


def test_serializer_marshalling_with_schema_field():
    existing_instance = {"field": [InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])]}
    expected_data = {"field": [{"stub_str": "abc", "stub_int": 1, "stub_list": [date(2022, 7, 1)]}]}

    serializer = Serializer(instance=existing_instance)
    assert serializer.data == expected_data

    serializer = Serializer(data=expected_data)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == existing_instance


def test_invalid_data_serialization():
    invalid_data = {"field": [{"stub_int": "abc", "stub_list": ["abc"]}]}
    serializer = Serializer(data=invalid_data)

    with pytest.raises(exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)

    assert e.match(r".*stub_str.*stub_int.*stub_list.*")


def test_schema_renderer():
    renderer = rest_framework.PydanticSchemaRenderer()
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'

    assert renderer.render(existing_instance) == expected_encoded


def test_typed_schema_renderer():
    renderer = rest_framework.PydanticSchemaRenderer[InnerSchema]()
    existing_data = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'

    assert renderer.render(existing_data) == expected_encoded


def test_schema_parser():
    parser = rest_framework.PydanticSchemaParser[InnerSchema]()
    existing_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    assert parser.parse(io.StringIO(existing_encoded)) == expected_instance


@api_view(["POST"])
@parser_classes([rest_framework.PydanticSchemaParser[InnerSchema]])
@renderer_classes([rest_framework.PydanticSchemaRenderer[t.List[InnerSchema]]])
def sample_view(request):
    assert isinstance(request.data, InnerSchema)
    return Response([request.data])


class ClassBasedView(views.APIView):
    parser_classes = [rest_framework.PydanticSchemaParser[InnerSchema]]
    renderer_classes = [rest_framework.PydanticSchemaRenderer[t.List[InnerSchema]]]

    def post(self, request, *args, **kwargs):
        assert isinstance(request.data, InnerSchema)
        return Response([request.data])


class ClassBasedViewWithSchemaContext(ClassBasedView):
    parser_classes = [rest_framework.PydanticSchemaParser]
    renderer_classes = [rest_framework.PydanticSchemaRenderer]

    def get_renderer_context(self):
        ctx = super().get_renderer_context()
        return dict(ctx, render_schema=t.List[InnerSchema])

    def get_parser_context(self, http_request):
        ctx = super().get_parser_context(http_request)
        return dict(ctx, parser_schema=InnerSchema)


@pytest.mark.parametrize("view", [
    sample_view,
    ClassBasedView.as_view(),
    ClassBasedViewWithSchemaContext.as_view(),
])
def test_end_to_end_api_view(view, request_factory):
    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    existing_encoded = b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'

    request = request_factory.post("/", existing_encoded, content_type="application/json")
    response = view(request)

    assert response.data == [expected_instance]
    assert response.data[0] is not expected_instance

    assert response.rendered_content == b'[%s]' % existing_encoded
