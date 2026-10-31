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


class DeferredTargetSchema(pydantic.BaseModel):
    label: str


def _generate_schema_for_serializer(serializer_cls: type[serializers.BaseSerializer]) -> dict[str, ty.Any]:
    class TestView(generics.RetrieveUpdateAPIView):
        serializer_class = serializer_cls
        schema = AutoSchema()

        def get_object(self):
            return None

    generator = SchemaGenerator(patterns=[path("api/test/", TestView.as_view())])
    return generator.get_schema(request=None, public=True)


def test_spectacular_schema_types_and_containers():
    T = ty.TypeVar("T")

    class GenericBox(pydantic.BaseModel, ty.Generic[T]):
        value: T

    class KitchenSinkSerializer(serializers.Serializer):
        profile = SchemaField(AddressSchema)
        shipping = SchemaField(AddressSchema)
        addresses = SchemaField(list[AddressSchema])
        address_map = SchemaField(dict[str, AddressSchema])
        order = SchemaField(OrderSchema)
        count = SchemaField(int)
        names = SchemaField(list[str])
        status = SchemaField(StatusEnum)
        variant = SchemaField(VariantA | VariantB)
        deferred = SchemaField("DeferredTargetSchema")
        root_box = SchemaField(GenericBox[int])
        nullable_box = SchemaField(GenericBox[int], allow_null=True)
        box_list = SchemaField(list[GenericBox[int]])

    with patched_settings({"OAS_VERSION": "3.0.3"}):
        schema = _generate_schema_for_serializer(KitchenSinkSerializer)
    components = schema["components"]["schemas"]
    props = components["KitchenSink"]["properties"]

    for name in (
        "AddressSchema",
        "CustomerSchema",
        "OrderSchema",
        "StatusEnum",
        "VariantA",
        "VariantB",
        "DeferredTargetSchema",
        "GenericBox_int_",
    ):
        assert name in components
    assert "GenericBox[int]" not in components

    assert props["profile"] == {"$ref": "#/components/schemas/AddressSchema"}
    assert props["shipping"] == {"$ref": "#/components/schemas/AddressSchema"}
    assert props["addresses"] == {"type": "array", "items": {"$ref": "#/components/schemas/AddressSchema"}}
    assert props["address_map"] == {
        "type": "object",
        "additionalProperties": {"$ref": "#/components/schemas/AddressSchema"},
    }
    assert props["order"] == {"$ref": "#/components/schemas/OrderSchema"}
    assert components["OrderSchema"]["properties"]["customer"] == {"$ref": "#/components/schemas/CustomerSchema"}
    assert components["CustomerSchema"]["properties"]["address"] == {"$ref": "#/components/schemas/AddressSchema"}
    assert props["count"] == {"type": "integer"}
    assert props["names"] == {"type": "array", "items": {"type": "string"}}
    assert props["status"] == {"$ref": "#/components/schemas/StatusEnum"}
    assert props["variant"] == {
        "anyOf": [{"$ref": "#/components/schemas/VariantA"}, {"$ref": "#/components/schemas/VariantB"}]
    }
    assert props["deferred"] == {"$ref": "#/components/schemas/DeferredTargetSchema"}
    assert props["root_box"] == {"$ref": "#/components/schemas/GenericBox_int_"}
    assert props["nullable_box"] == {"allOf": [{"$ref": "#/components/schemas/GenericBox_int_"}], "nullable": True}
    assert props["box_list"] == {"type": "array", "items": {"$ref": "#/components/schemas/GenericBox_int_"}}


def test_nullable_and_discriminated_unions_oas_30_and_31():
    ComplexVariant = ty.Annotated[VariantA | VariantB | None, pydantic.Field(discriminator="kind")]
    NonNullVariant = ty.Annotated[VariantA | VariantB, pydantic.Field(discriminator="kind")]

    class NullableSerializer(serializers.Serializer):
        opt_model = SchemaField(AddressSchema | None)
        allow_null_model = SchemaField(AddressSchema, allow_null=True)
        allow_null_int = SchemaField(int, allow_null=True)
        value_complex = SchemaField(ComplexVariant, required=False)
        allow_null_complex = SchemaField(NonNullVariant, allow_null=True)

    with patched_settings({"OAS_VERSION": "3.0.3"}):
        schema_30 = _generate_schema_for_serializer(NullableSerializer)
    comp_30 = schema_30["components"]["schemas"]
    props_30 = comp_30["Nullable"]["properties"]

    assert comp_30["AddressSchema"]["properties"]["zip_code"] == {
        "title": "Zip Code",
        "type": "string",
        "nullable": True,
        "default": None,
    }
    assert props_30["opt_model"] == {"allOf": [{"$ref": "#/components/schemas/AddressSchema"}], "nullable": True}
    assert props_30["allow_null_model"] == {"allOf": [{"$ref": "#/components/schemas/AddressSchema"}], "nullable": True}
    assert props_30["allow_null_int"] == {"type": "integer", "nullable": True}

    expected_union = {
        "oneOf": [{"$ref": "#/components/schemas/VariantA"}, {"$ref": "#/components/schemas/VariantB"}],
        "discriminator": {
            "propertyName": "kind",
            "mapping": {"a": "#/components/schemas/VariantA", "b": "#/components/schemas/VariantB"},
        },
        "nullable": True,
    }
    assert props_30["value_complex"] == expected_union
    assert props_30["allow_null_complex"] == expected_union

    with patched_settings({"OAS_VERSION": "3.1.0"}):
        schema_31 = _generate_schema_for_serializer(NullableSerializer)
    comp_31 = schema_31["components"]["schemas"]
    props_31 = comp_31["Nullable"]["properties"]

    assert comp_31["AddressSchema"]["properties"]["zip_code"] == {
        "title": "Zip Code",
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }
    assert props_31["opt_model"] == {"anyOf": [{"$ref": "#/components/schemas/AddressSchema"}, {"type": "null"}]}
    assert props_31["allow_null_model"] == {"oneOf": [{"$ref": "#/components/schemas/AddressSchema"}, {"type": "null"}]}
    assert props_31["allow_null_int"] == {"type": ["integer", "null"]}


def test_direction_model_serializer_and_endpoint(request_factory):
    class SampleModelSerializer(serializers.ModelSerializer):
        sample_field = SchemaField(schema=InnerSchema, help_text="Primary inner schema")
        sample_list = SchemaField(schema=list[InnerSchema], read_only=True)
        sample_seq = SchemaField(schema=list[InnerSchema], write_only=True, default=list)
        aliased = SchemaField(list[AliasedSchema])

        class Meta:
            model = SampleModel
            fields = ("sample_field", "sample_list", "sample_seq", "aliased")

    class EndpointView(generics.ListCreateAPIView):
        serializer_class = SampleModelSerializer
        schema = AutoSchema()

        def get_queryset(self):
            return []

        def get(self, request, *args, **kwargs):
            return Response([])

    patterns = [path("api/endpoint/", EndpointView.as_view())]
    with patched_settings({"COMPONENT_SPLIT_REQUEST": True}):
        view = SpectacularAPIView.as_view(urlconf=patterns)
        response = view(request_factory.get("/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json"))

    assert response.status_code == 200
    components = response.data["components"]["schemas"]
    assert "SampleModelRequest" in components
    assert "SampleModel" in components
    assert "InnerSchema" in components
    assert components["SampleModel"]["properties"]["sample_field"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "description": "Primary inner schema",
    }
    assert components["SampleModel"]["properties"]["sample_list"]["readOnly"] is True
    assert components["SampleModelRequest"]["properties"]["sample_seq"]["writeOnly"] is True
