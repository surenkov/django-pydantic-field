import io
from datetime import date

from rest_framework.decorators import api_view, renderer_classes, parser_classes
from rest_framework.response import Response

from django_pydantic_field import rest_framework

from .conftest import InnerSchema


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


def test_end_to_end_api_view(request_factory):
    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    @api_view(["POST"])
    @parser_classes([rest_framework.PydanticSchemaParser[InnerSchema]])
    @renderer_classes([rest_framework.PydanticSchemaRenderer[InnerSchema]])
    def sample_view(request):
        assert request.data == expected_instance
        return Response(request.data)

    request = request_factory.post("/", expected_instance.json(), content_type="application/json")
    response = sample_view(request)

    assert response.data == expected_instance
    assert response.data is not expected_instance
