import io
import json
import typing as t
from datetime import date

import pytest
import yaml
from django.urls import path
from django_pydantic_field import rest_framework
from rest_framework import exceptions, generics, schemas, serializers, views
from rest_framework.decorators import api_view, parser_classes, renderer_classes, schema
from rest_framework.response import Response

from .conftest import InnerSchema
from .test_app.models import SampleModel


class SampleSerializer(serializers.Serializer):
    field = rest_framework.SchemaField(schema=t.List[InnerSchema])


class SampleModelSerializer(serializers.ModelSerializer):
    sample_field = rest_framework.SchemaField(schema=InnerSchema)
    sample_list = rest_framework.SchemaField(schema=t.List[InnerSchema])
    sample_seq = rest_framework.SchemaField(schema=t.List[InnerSchema], default=list)

    class Meta:
        model = SampleModel
        fields = "sample_field", "sample_list", "sample_seq"


def test_schema_field():
    field = rest_framework.SchemaField(InnerSchema)
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = {
        "stub_str": "abc",
        "stub_int": 1,
        "stub_list": [date(2022, 7, 1)],
    }

    assert field.to_representation(existing_instance) == expected_encoded
    assert field.to_internal_value(expected_encoded) == existing_instance

    with pytest.raises(serializers.ValidationError):
        field.to_internal_value(None)

    with pytest.raises(serializers.ValidationError):
        field.to_internal_value("null")


def test_field_schema_with_custom_config():
    field = rest_framework.SchemaField(
        InnerSchema, allow_null=True, exclude={"stub_int"}
    )
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}

    assert field.to_representation(existing_instance) == expected_encoded
    assert field.to_internal_value(expected_encoded) == existing_instance
    assert field.to_internal_value(None) is None
    assert field.to_internal_value("null") is None


def test_serializer_marshalling_with_schema_field():
    existing_instance = {
        "field": [InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])]
    }
    expected_data = {
        "field": [{"stub_str": "abc", "stub_int": 1, "stub_list": [date(2022, 7, 1)]}]
    }

    serializer = SampleSerializer(instance=existing_instance)
    assert serializer.data == expected_data

    serializer = SampleSerializer(data=expected_data)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == existing_instance


def test_model_serializer_marshalling_with_schema_field():
    instance = SampleModel(
        sample_field=InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        sample_list=[InnerSchema(stub_str="abc", stub_int=2, stub_list=[date(2022, 7, 1)])] * 2,
        sample_seq=[InnerSchema(stub_str="abc", stub_int=3, stub_list=[date(2022, 7, 1)])]  * 3,
    )
    serializer = SampleModelSerializer(instance)

    expected_data = {
        "sample_field": {"stub_str": "abc", "stub_int": 1, "stub_list": [date(2022, 7, 1)]},
        "sample_list": [{"stub_str": "abc", "stub_int": 2, "stub_list": [date(2022, 7, 1)]}] * 2,
        "sample_seq": [{"stub_str": "abc", "stub_int": 3, "stub_list": [date(2022, 7, 1)]}] * 3,
    }
    assert serializer.data == expected_data


@pytest.mark.parametrize("export_kwargs", [
    {"include": {"stub_str", "stub_int"}},
    {"exclude": {"stub_list"}},
    {"exclude_unset": True},
    {"exclude_defaults": True},
    {"exclude_none": True},
    {"by_alias": True},
])
def test_field_export_kwargs(export_kwargs):
    field = rest_framework.SchemaField(InnerSchema, **export_kwargs)
    assert field.to_representation(InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]))


def test_invalid_data_serialization():
    invalid_data = {"field": [{"stub_int": "abc", "stub_list": ["abc"]}]}
    serializer = SampleSerializer(data=invalid_data)

    with pytest.raises(exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)

    assert e.match(r".*stub_str.*stub_int.*stub_list.*")


def test_schema_renderer():
    renderer = rest_framework.SchemaRenderer()
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = (
        b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    )

    assert renderer.render(existing_instance) == expected_encoded


def test_typed_schema_renderer():
    renderer = rest_framework.SchemaRenderer[InnerSchema]()
    existing_data = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = (
        b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    )

    assert renderer.render(existing_data) == expected_encoded


def test_schema_parser():
    parser = rest_framework.SchemaParser[InnerSchema]()
    existing_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    assert parser.parse(io.StringIO(existing_encoded)) == expected_instance


@api_view(["POST"])
@schema(rest_framework.AutoSchema())
@parser_classes([rest_framework.SchemaParser[InnerSchema]])
@renderer_classes([rest_framework.SchemaRenderer[t.List[InnerSchema]]])
def sample_view(request):
    assert isinstance(request.data, InnerSchema)
    return Response([request.data])


class ClassBasedViewWithSerializer(generics.RetrieveAPIView):
    serializer_class = SampleSerializer
    schema = rest_framework.AutoSchema()


class ClassBasedViewWithModel(generics.ListCreateAPIView):
    queryset = SampleModel.objects.all()
    serializer_class = SampleModelSerializer


class ClassBasedView(views.APIView):
    parser_classes = [rest_framework.SchemaParser[InnerSchema]]
    renderer_classes = [rest_framework.SchemaRenderer[t.List[InnerSchema]]]

    def post(self, request, *args, **kwargs):
        assert isinstance(request.data, InnerSchema)
        return Response([request.data])


class ClassBasedViewWithSchemaContext(ClassBasedView):
    parser_classes = [rest_framework.SchemaParser]
    renderer_classes = [rest_framework.SchemaRenderer]

    def get_renderer_context(self):
        ctx = super().get_renderer_context()
        return dict(ctx, render_schema=t.List[InnerSchema])

    def get_parser_context(self, http_request):
        ctx = super().get_parser_context(http_request)
        return dict(ctx, parser_schema=InnerSchema)


@pytest.mark.parametrize(
    "view",
    [
        sample_view,
        ClassBasedView.as_view(),
        ClassBasedViewWithSchemaContext.as_view(),
    ],
)
def test_end_to_end_api_view(view, request_factory):
    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    existing_encoded = (
        b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    )

    request = request_factory.post(
        "/", existing_encoded, content_type="application/json"
    )
    response = view(request)

    assert response.data == [expected_instance]
    assert response.data[0] is not expected_instance

    assert response.rendered_content == b"[%s]" % existing_encoded


@pytest.mark.django_db
def test_end_to_end_list_create_api_view(request_factory):
    field_data = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]).json()
    expected_result = {
        "sample_field": {"stub_str": "abc", "stub_list": [date(2022, 7, 1)], "stub_int": 1},
        "sample_list": [{"stub_str": "abc", "stub_list": [date(2022, 7, 1)], "stub_int": 1}],
        "sample_seq": [],
    }

    payload = '{"sample_field": %s, "sample_list": [%s], "sample_seq": []}' % ((field_data,) * 2)
    request = request_factory.post("/", payload.encode(), content_type="application/json")
    response = ClassBasedViewWithModel.as_view()(request)

    assert response.data == expected_result

    request = request_factory.get("/", content_type="application/json")
    response = ClassBasedViewWithModel.as_view()(request)
    assert response.data == [expected_result]


def test_openapi_serializer_schema_generation(request_factory):
    schema_url_patterns = [
        path("api/", ClassBasedViewWithSerializer.as_view()),
    ]

    schema_view = schemas.get_schema_view(patterns=schema_url_patterns)
    request = request_factory.get("api/", format="json")
    response = schema_view(request)

    results = yaml.load(response.rendered_content, yaml.Loader)
    assert results["components"]["schemas"]["Sample"]["properties"]["field"] == {
        "title": "FieldSchema[List[tests.conftest.InnerSchema]]",
        "type": "array",
        "items": {"$ref": "#/definitions/InnerSchema"},
        "definitions": {
            "InnerSchema": {
                "title": "InnerSchema",
                "type": "object",
                "properties": {
                    "stub_str": {"title": "Stub Str", "type": "string"},
                    "stub_int": {
                        "title": "Stub Int",
                        "default": 1,
                        "type": "integer",
                    },
                    "stub_list": {
                        "title": "Stub List",
                        "type": "array",
                        "items": {"type": "string", "format": "date"},
                    },
                },
                "required": ["stub_str", "stub_list"],
            }
        },
    }


def test_openapi_parser_renderer_schema_generation(request_factory):
    schema_url_patterns = [
        path("api/", sample_view),
    ]

    schema_view = schemas.get_schema_view(patterns=schema_url_patterns)
    request = request_factory.get("api/", format="json")
    response = schema_view(request)

    results = yaml.load(response.rendered_content, yaml.Loader)
    assert results["paths"]["/api/"]["post"]["requestBody"]["content"][
        "application/json"
    ] == {
        "schema": {
            "title": "FieldSchema[InnerSchema]",
            "$ref": "#/definitions/InnerSchema",
            "definitions": {
                "InnerSchema": {
                    "title": "InnerSchema",
                    "type": "object",
                    "properties": {
                        "stub_str": {
                            "title": "Stub Str",
                            "type": "string",
                        },
                        "stub_int": {
                            "title": "Stub Int",
                            "default": 1,
                            "type": "integer",
                        },
                        "stub_list": {
                            "title": "Stub List",
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "date",
                            },
                        },
                    },
                    "required": ["stub_str", "stub_list"],
                }
            },
        }
    }
    assert results["paths"]["/api/"]["post"]["responses"]["201"] == {
        "content": {
            "application/json": {
                "schema": {
                    "title": "FieldSchema[List[tests.conftest.InnerSchema]]",
                    "type": "array",
                    "items": {"$ref": "#/definitions/InnerSchema"},
                    "definitions": {
                        "InnerSchema": {
                            "title": "InnerSchema",
                            "type": "object",
                            "properties": {
                                "stub_str": {
                                    "title": "Stub Str",
                                    "type": "string",
                                },
                                "stub_int": {
                                    "title": "Stub Int",
                                    "default": 1,
                                    "type": "integer",
                                },
                                "stub_list": {
                                    "title": "Stub List",
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "format": "date",
                                    },
                                },
                            },
                            "required": ["stub_str", "stub_list"],
                        }
                    },
                }
            }
        },
        "description": "",
    }
