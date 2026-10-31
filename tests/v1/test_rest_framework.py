import io
import sys
import typing as t
from datetime import date

import pytest
import yaml
from django.urls import path
from rest_framework import exceptions, generics, schemas, serializers, views
from rest_framework.decorators import api_view, parser_classes, renderer_classes, schema
from rest_framework.response import Response

from django_pydantic_field.v1 import rest_framework
from tests.test_app.models import InnerSchemaV1, SampleModelV1

pytestmark = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="Pydantic V1 is incompatible with Python 3.14+",
)


class SampleSerializer(serializers.Serializer):
    field = rest_framework.SchemaField(schema=t.List[InnerSchemaV1])


class SampleModelSerializer(serializers.ModelSerializer):
    sample_field = rest_framework.SchemaField(schema=InnerSchemaV1)
    sample_list = rest_framework.SchemaField(schema=t.List[InnerSchemaV1])
    sample_seq = rest_framework.SchemaField(schema=t.List[InnerSchemaV1], default=list)

    class Meta:
        model = SampleModelV1
        fields = "sample_field", "sample_list", "sample_seq"


def test_schema_field():
    field = rest_framework.SchemaField(InnerSchemaV1)
    existing_instance = InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)])
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
    field = rest_framework.SchemaField(InnerSchemaV1, allow_null=True, exclude={"stub_int"})
    existing_instance = InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}

    assert field.to_representation(existing_instance) == expected_encoded
    assert field.to_internal_value(expected_encoded) == existing_instance
    assert field.to_internal_value(None) is None
    assert field.to_internal_value("null") is None


def test_serializer_marshalling_with_schema_field():
    existing_instance = {"field": [InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)])]}
    expected_data = {"field": [{"stub_str": "abc", "stub_int": 1, "stub_list": [date(2022, 7, 1)]}]}

    serializer = SampleSerializer(instance=existing_instance)
    assert serializer.data == expected_data

    serializer = SampleSerializer(data=expected_data)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == existing_instance


def test_model_serializer_marshalling_with_schema_field():
    instance = SampleModelV1(
        sample_field=InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        sample_list=[InnerSchemaV1(stub_str="abc", stub_int=2, stub_list=[date(2022, 7, 1)])] * 2,
        sample_seq=[InnerSchemaV1(stub_str="abc", stub_int=3, stub_list=[date(2022, 7, 1)])] * 3,
    )
    serializer = SampleModelSerializer(instance)

    expected_data = {
        "sample_field": {"stub_str": "abc", "stub_int": 1, "stub_list": [date(2022, 7, 1)]},
        "sample_list": [{"stub_str": "abc", "stub_int": 2, "stub_list": [date(2022, 7, 1)]}] * 2,
        "sample_seq": [{"stub_str": "abc", "stub_int": 3, "stub_list": [date(2022, 7, 1)]}] * 3,
    }
    assert serializer.data == expected_data


@pytest.mark.parametrize(
    "export_kwargs",
    [
        {"include": {"stub_str", "stub_int"}},
        {"exclude": {"stub_list"}},
        {"exclude_unset": True},
        {"exclude_defaults": True},
        {"exclude_none": True},
        {"by_alias": True},
    ],
)
def test_field_export_kwargs(export_kwargs):
    field = rest_framework.SchemaField(InnerSchemaV1, **export_kwargs)
    assert field.to_representation(InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)]))


def test_invalid_data_serialization():
    invalid_data = {"field": [{"stub_int": "abc", "stub_list": ["abc"]}]}
    serializer = SampleSerializer(data=invalid_data)

    with pytest.raises(exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)

    assert e.match(r".*stub_str.*stub_int.*stub_list.*")


def test_schema_renderer():
    renderer = rest_framework.SchemaRenderer()
    existing_instance = InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'

    assert renderer.render(existing_instance) == expected_encoded


def test_typed_schema_renderer():
    renderer = rest_framework.SchemaRenderer[InnerSchemaV1]()
    existing_data = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'

    assert renderer.render(existing_data) == expected_encoded


def test_schema_parser():
    parser = rest_framework.SchemaParser[InnerSchemaV1]()
    existing_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    expected_instance = InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)])

    assert parser.parse(io.StringIO(existing_encoded)) == expected_instance


@api_view(["POST"])
@schema(rest_framework.AutoSchema())
@parser_classes([rest_framework.SchemaParser[InnerSchemaV1]])
@renderer_classes([rest_framework.SchemaRenderer[t.List[InnerSchemaV1]]])
def sample_view(request):
    assert isinstance(request.data, InnerSchemaV1)
    return Response([request.data])


class ClassBasedViewWithSerializer(generics.RetrieveAPIView):
    serializer_class = SampleSerializer
    schema = rest_framework.AutoSchema()


class ClassBasedViewWithModel(generics.ListCreateAPIView):
    queryset = SampleModelV1.objects.all()
    serializer_class = SampleModelSerializer


class ClassBasedView(views.APIView):
    parser_classes = [rest_framework.SchemaParser[InnerSchemaV1]]
    renderer_classes = [rest_framework.SchemaRenderer[t.List[InnerSchemaV1]]]

    def post(self, request, *args, **kwargs):
        assert isinstance(request.data, InnerSchemaV1)
        return Response([request.data])


class ClassBasedViewWithSchemaContext(ClassBasedView):
    parser_classes = [rest_framework.SchemaParser]
    renderer_classes = [rest_framework.SchemaRenderer]

    def get_renderer_context(self):
        ctx = super().get_renderer_context()
        return dict(ctx, render_schema=t.List[InnerSchemaV1])

    def get_parser_context(self, http_request):
        ctx = super().get_parser_context(http_request)
        return dict(ctx, parser_schema=InnerSchemaV1)


@pytest.mark.parametrize(
    "view",
    [
        sample_view,
        ClassBasedView.as_view(),
        ClassBasedViewWithSchemaContext.as_view(),
    ],
)
def test_end_to_end_api_view(view, request_factory):
    expected_instance = InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)])
    existing_encoded = b'{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'

    request = request_factory.post("/", existing_encoded, content_type="application/json")
    response = view(request)

    assert response.data == [expected_instance]
    assert response.data[0] is not expected_instance

    assert response.rendered_content == b"[%s]" % existing_encoded


@pytest.mark.django_db
def test_end_to_end_list_create_api_view(request_factory):
    field_data = InnerSchemaV1(stub_str="abc", stub_list=[date(2022, 7, 1)]).json()
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
        "type": "array",
        "items": {"$ref": "#/components/schemas/InnerSchemaV1"},
    }
    assert results["components"]["schemas"]["InnerSchemaV1"] == {
        "title": "InnerSchemaV1",
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


def test_openapi_parser_renderer_schema_generation(request_factory):
    schema_url_patterns = [
        path("api/", sample_view),
    ]

    schema_view = schemas.get_schema_view(patterns=schema_url_patterns)
    request = request_factory.get("api/", format="json")
    response = schema_view(request)

    results = yaml.load(response.rendered_content, yaml.Loader)
    assert results["paths"]["/api/"]["post"]["requestBody"]["content"]["application/json"] == {
        "schema": {
            "$ref": "#/components/schemas/InnerSchemaV1",
        }
    }
    assert results["paths"]["/api/"]["post"]["responses"]["201"] == {
        "content": {
            "application/json": {
                "schema": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/InnerSchemaV1"},
                }
            }
        },
        "description": "",
    }
    assert results["components"]["schemas"]["InnerSchemaV1"] == {
        "title": "InnerSchemaV1",
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


def test_openapi_v1_list_view_metadata_and_discriminated_union(request_factory):
    from django_pydantic_field.v1.compat import pydantic_v1

    class CatV1(pydantic_v1.BaseModel):
        pet_type: t.Literal["cat"] = "cat"
        meows: int = pydantic_v1.Field(gt=0, lt=10)

    class DogV1(pydantic_v1.BaseModel):
        pet_type: t.Literal["dog"] = "dog"
        barks: float = pydantic_v1.Field(gt=0.0, lt=5.0)

    PetUnionV1 = t.Annotated[t.Union[CatV1, DogV1], pydantic_v1.Field(discriminator="pet_type")]

    @api_view(["GET"])
    @schema(rest_framework.AutoSchema())
    @renderer_classes([rest_framework.SchemaRenderer[InnerSchemaV1]])
    def list_renderer_view(request):
        return Response([])

    class MetaSerializerV1(serializers.Serializer):
        item = rest_framework.SchemaField(InnerSchemaV1, allow_null=True, help_text="Nullable V1 item")
        second_item = rest_framework.SchemaField(InnerSchemaV1)
        items_list = rest_framework.SchemaField(t.List[InnerSchemaV1])
        pair = rest_framework.SchemaField(t.Tuple[int, str])
        pet = rest_framework.SchemaField(PetUnionV1)
        nullable_pet = rest_framework.SchemaField(PetUnionV1, allow_null=True)

    class MetaViewV1(generics.RetrieveAPIView):
        serializer_class = MetaSerializerV1
        schema = rest_framework.AutoSchema()

    class DeleteOnlyViewV1(views.APIView):
        parser_classes = [rest_framework.SchemaParser[InnerSchemaV1]]
        renderer_classes = [rest_framework.SchemaRenderer[InnerSchemaV1]]
        schema = rest_framework.AutoSchema()

        def delete(self, request):
            return Response(status=204)

    delete_view = DeleteOnlyViewV1()
    delete_view.request = None
    delete_view.format_kwarg = None
    assert delete_view.schema.get_components("/items/", "DELETE") == {}

    schema_url_patterns = [path("items/", list_renderer_view), path("meta/", MetaViewV1.as_view())]
    schema_view = schemas.get_schema_view(patterns=schema_url_patterns)
    results = yaml.load(schema_view(request_factory.get("items/", format="json")).rendered_content, yaml.Loader)

    assert results["paths"]["/items/"]["get"]["responses"]["200"]["content"]["application/json"] == {
        "schema": {"type": "array", "items": {"$ref": "#/components/schemas/InnerSchemaV1"}},
    }
    components = results["components"]["schemas"]
    assert {"InnerSchemaV1", "CatV1", "DogV1"} <= components.keys()
    assert components["CatV1"]["properties"]["meows"]["minimum"] == 0
    assert components["CatV1"]["properties"]["meows"]["exclusiveMinimum"] is True

    props = components["MetaV1"]["properties"]
    assert props["item"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchemaV1"}],
        "nullable": True,
        "description": "Nullable V1 item",
    }
    assert props["second_item"] == {"$ref": "#/components/schemas/InnerSchemaV1"}
    assert props["items_list"] == {"type": "array", "items": {"$ref": "#/components/schemas/InnerSchemaV1"}}
    assert props["pair"] == {
        "type": "array",
        "items": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
        "minItems": 2,
        "maxItems": 2,
    }
    expected_union = {
        "oneOf": [{"$ref": "#/components/schemas/CatV1"}, {"$ref": "#/components/schemas/DogV1"}],
        "discriminator": {
            "propertyName": "pet_type",
            "mapping": {"cat": "#/components/schemas/CatV1", "dog": "#/components/schemas/DogV1"},
        },
    }
    assert props["pet"] == expected_union
    assert props["nullable_pet"] == {**expected_union, "nullable": True}
