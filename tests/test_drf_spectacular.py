from __future__ import annotations

import enum
import typing as ty

import pydantic
import pytest
from django.urls import path
from rest_framework import generics, serializers
from rest_framework.response import Response

from django_pydantic_field.compat import PYDANTIC_V2
from tests.conftest import InnerSchema
from tests.test_app.models import SampleModel

drf_spectacular = pytest.importorskip("drf_spectacular")
from drf_spectacular.generators import SchemaGenerator  # noqa: E402
from drf_spectacular.openapi import AutoSchema  # noqa: E402
from drf_spectacular.plumbing import ComponentRegistry  # noqa: E402
from drf_spectacular.settings import patched_settings  # noqa: E402
from drf_spectacular.views import SpectacularAPIView  # noqa: E402

pytestmark = pytest.mark.skipif(not PYDANTIC_V2, reason="drf-spectacular integration requires Pydantic v2")

if PYDANTIC_V2:
    from django_pydantic_field.v2.rest_framework import SchemaField


class StatusEnum(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"


class AddressSchema(pydantic.BaseModel):
    street: str
    city: str
    zip_code: str | None = None


class CustomerSchema(pydantic.BaseModel):
    name: str
    address: AddressSchema
    status: StatusEnum = StatusEnum.ACTIVE


class OrderSchema(pydantic.BaseModel):
    order_id: int
    customer: CustomerSchema
    tags: list[str] = pydantic.Field(default_factory=list)


class AliasedSchema(pydantic.BaseModel):
    internal_id: int = pydantic.Field(validation_alias="input_id", serialization_alias="output_id")


class VariantA(pydantic.BaseModel):
    kind: ty.Literal["a"] = "a"
    a_val: int


class VariantB(pydantic.BaseModel):
    kind: ty.Literal["b"] = "b"
    b_val: str


def _generate_schema_for_serializer(serializer_cls: type[serializers.BaseSerializer]) -> dict[str, ty.Any]:
    class TestView(generics.RetrieveUpdateAPIView):
        serializer_class = serializer_cls
        schema = AutoSchema()

        def get_object(self):
            return None

    generator = SchemaGenerator(patterns=[path("api/test/", TestView.as_view())])
    return generator.get_schema(request=None, public=True)


def test_single_basemodel_field():
    class ProfileSerializer(serializers.Serializer):
        profile = SchemaField(AddressSchema)

    schema = _generate_schema_for_serializer(ProfileSerializer)
    components = schema["components"]["schemas"]

    assert "AddressSchema" in components
    assert components["AddressSchema"]["type"] == "object"
    assert "street" in components["AddressSchema"]["properties"]
    assert components["Profile"]["properties"]["profile"] == {
        "$ref": "#/components/schemas/AddressSchema",
    }


def test_container_basemodel_fields():
    class ContainerSerializer(serializers.Serializer):
        addresses = SchemaField(list[AddressSchema])
        address_map = SchemaField(dict[str, AddressSchema])

    schema = _generate_schema_for_serializer(ContainerSerializer)
    components = schema["components"]["schemas"]
    props = components["Container"]["properties"]

    assert "AddressSchema" in components
    assert props["addresses"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/AddressSchema"},
    }
    assert props["address_map"] == {
        "type": "object",
        "additionalProperties": {"$ref": "#/components/schemas/AddressSchema"},
    }


def test_nested_basemodel_hierarchy():
    class OrderSerializer(serializers.Serializer):
        order = SchemaField(OrderSchema)

    schema = _generate_schema_for_serializer(OrderSerializer)
    components = schema["components"]["schemas"]

    assert "OrderSchema" in components
    assert "CustomerSchema" in components
    assert "AddressSchema" in components
    assert "StatusEnum" in components
    assert components["Order"]["properties"]["order"] == {
        "$ref": "#/components/schemas/OrderSchema",
    }
    assert components["OrderSchema"]["properties"]["customer"] == {
        "$ref": "#/components/schemas/CustomerSchema",
    }
    assert components["CustomerSchema"]["properties"]["address"] == {
        "$ref": "#/components/schemas/AddressSchema",
    }


def test_nullable_and_optional_oas_30():
    class NullableSerializer(serializers.Serializer):
        opt_model = SchemaField(ty.Optional[AddressSchema])
        allow_null_model = SchemaField(AddressSchema, allow_null=True)
        allow_null_int = SchemaField(int, allow_null=True)

    with patched_settings({"OAS_VERSION": "3.0.3"}):
        schema = _generate_schema_for_serializer(NullableSerializer)
    components = schema["components"]["schemas"]
    props = components["Nullable"]["properties"]

    # Nested Optional[str] inside AddressSchema normalized to nullable: True
    assert components["AddressSchema"]["properties"]["zip_code"] == {
        "title": "Zip Code",
        "type": "string",
        "nullable": True,
        "default": None,
    }
    assert props["opt_model"] == {
        "allOf": [{"$ref": "#/components/schemas/AddressSchema"}],
        "nullable": True,
    }
    assert props["allow_null_model"] == {
        "allOf": [{"$ref": "#/components/schemas/AddressSchema"}],
        "nullable": True,
    }
    assert props["allow_null_int"] == {
        "type": "integer",
        "nullable": True,
    }


def test_nullable_and_optional_oas_31():
    class NullableSerializer(serializers.Serializer):
        opt_model = SchemaField(ty.Optional[AddressSchema])
        allow_null_model = SchemaField(AddressSchema, allow_null=True)
        allow_null_int = SchemaField(int, allow_null=True)

    with patched_settings({"OAS_VERSION": "3.1.0"}):
        schema = _generate_schema_for_serializer(NullableSerializer)
    components = schema["components"]["schemas"]
    props = components["Nullable"]["properties"]

    assert components["AddressSchema"]["properties"]["zip_code"] == {
        "title": "Zip Code",
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }
    assert props["opt_model"] == {
        "anyOf": [{"$ref": "#/components/schemas/AddressSchema"}, {"type": "null"}],
    }
    assert props["allow_null_model"] == {
        "oneOf": [{"$ref": "#/components/schemas/AddressSchema"}, {"type": "null"}],
    }
    assert props["allow_null_int"] == {
        "type": ["integer", "null"],
    }


def test_primitives_enums_and_unions():
    class MiscSerializer(serializers.Serializer):
        count = SchemaField(int)
        names = SchemaField(list[str])
        status = SchemaField(StatusEnum)
        variant = SchemaField(ty.Union[VariantA, VariantB])

    schema = _generate_schema_for_serializer(MiscSerializer)
    components = schema["components"]["schemas"]
    props = components["Misc"]["properties"]

    assert props["count"] == {"type": "integer"}
    assert props["names"] == {"type": "array", "items": {"type": "string"}}
    assert props["status"] == {"$ref": "#/components/schemas/StatusEnum"}
    assert components["StatusEnum"]["enum"] == ["active", "pending"]
    assert "VariantA" in components
    assert "VariantB" in components
    assert props["variant"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/VariantA"},
            {"$ref": "#/components/schemas/VariantB"},
        ]
    }


def test_forward_ref_schema():
    class ForwardRefSerializer(serializers.Serializer):
        deferred = SchemaField("DeferredTargetSchema")

    schema = _generate_schema_for_serializer(ForwardRefSerializer)
    components = schema["components"]["schemas"]

    assert "DeferredTargetSchema" in components
    assert components["ForwardRef"]["properties"]["deferred"] == {
        "$ref": "#/components/schemas/DeferredTargetSchema",
    }


class DeferredTargetSchema(pydantic.BaseModel):
    label: str


def test_direction_request_vs_response_mode():
    class DirectionSerializer(serializers.Serializer):
        items = SchemaField(list[AliasedSchema])

    class CreateView(generics.ListCreateAPIView):
        serializer_class = DirectionSerializer
        schema = AutoSchema()

        def get_queryset(self):
            return []

    with patched_settings({"COMPONENT_SPLIT_REQUEST": True}):
        generator = SchemaGenerator(patterns=[path("api/direction/", CreateView.as_view())])
        schema = generator.get_schema(request=None, public=True)
    components = schema["components"]["schemas"]

    # Check direct extension call for request vs response mode
    serializer = DirectionSerializer()
    field = serializer.fields["items"]
    view = CreateView()
    view.request = None

    from django_pydantic_field.spectacular import PydanticSchemaFieldExtension

    ext = PydanticSchemaFieldExtension(field)
    auto_schema_req = AutoSchema()
    auto_schema_req.view = view
    auto_schema_req.registry = ComponentRegistry()
    ext.map_serializer_field(auto_schema_req, "request")
    req_comp = auto_schema_req.registry[("AliasedSchema", "schemas")]
    assert "input_id" in req_comp.schema["properties"]

    auto_schema_resp = AutoSchema()
    auto_schema_resp.view = view
    auto_schema_resp.registry = ComponentRegistry()
    ext.map_serializer_field(auto_schema_resp, "response")
    resp_comp = auto_schema_resp.registry[("AliasedSchema", "schemas")]
    assert "output_id" in resp_comp.schema["properties"]
    assert "DirectionRequest" in components
    assert "Direction" in components


def test_model_serializer_and_field_metadata():
    class SampleModelSerializer(serializers.ModelSerializer):
        sample_field = SchemaField(schema=InnerSchema, help_text="Primary inner schema")
        sample_list = SchemaField(schema=list[InnerSchema], read_only=True)
        sample_seq = SchemaField(schema=list[InnerSchema], write_only=True, default=list)

        class Meta:
            model = SampleModel
            fields = ("sample_field", "sample_list", "sample_seq")

    schema = _generate_schema_for_serializer(SampleModelSerializer)
    components = schema["components"]["schemas"]
    props = components["SampleModel"]["properties"]

    assert "InnerSchema" in components
    assert props["sample_field"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "description": "Primary inner schema",
    }
    assert props["sample_list"]["readOnly"] is True
    assert props["sample_seq"]["writeOnly"] is True


def test_spectacular_api_view_endpoint(request_factory):
    class EndpointSerializer(serializers.Serializer):
        address = SchemaField(AddressSchema)

    class EndpointView(generics.RetrieveAPIView):
        serializer_class = EndpointSerializer
        schema = AutoSchema()

        def get(self, request, *args, **kwargs):
            return Response({})

    patterns = [path("api/endpoint/", EndpointView.as_view())]
    view = SpectacularAPIView.as_view(urlconf=patterns)
    request = request_factory.get("/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    response = view(request)

    assert response.status_code == 200
    assert "AddressSchema" in response.data["components"]["schemas"]
