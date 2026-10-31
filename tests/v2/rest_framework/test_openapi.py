from __future__ import annotations

import typing as ty

import pydantic
import pytest
from django.urls import path
from rest_framework import generics, pagination, serializers, views
from rest_framework.decorators import api_view, parser_classes, renderer_classes, schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.schemas.openapi import SchemaGenerator

from tests.conftest import InnerSchema
from tests.test_app.models import SampleModel

from .view_fixtures import create_views_urlconf

rest_framework = pytest.importorskip("django_pydantic_field.v2.rest_framework", exc_type=ImportError)
openapi = pytest.importorskip("django_pydantic_field.v2.rest_framework.openapi", exc_type=ImportError)


def assert_valid_openapi_302(doc: dict[str, ty.Any]) -> None:
    """Validate structural OpenAPI 3.0.2 invariants across the generated document."""
    assert doc.get("openapi") == "3.0.2"
    components_schemas = doc.get("components", {}).get("schemas", {})

    for path_item in doc.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for media_type, media_obj in operation.get("requestBody", {}).get("content", {}).items():
                assert "schema" in media_obj and "$ref" not in media_obj, f"Invalid requestBody media for {media_type}"
            for status_code, resp_obj in operation.get("responses", {}).items():
                resp_content = resp_obj.get("content", {})
                assert "text/html" not in resp_content, f"Leaked text/html in response {status_code}"
                for media_type, media_obj in resp_content.items():
                    assert "schema" in media_obj and "$ref" not in media_obj, f"Invalid response media for {media_type}"

    def _walk(node: ty.Any, location: str = "#") -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                assert ref.startswith("#/components/schemas/"), f"Non-component $ref {ref} at {location}"
                assert ref.split("#/components/schemas/", 1)[1] in components_schemas, f"Unresolvable $ref {ref}"
                assert len(node) == 1, f"$ref at {location} has invalid OAS 3.0.2 siblings: {list(node.keys())}"

            for forbidden in ("$defs", "definitions", "prefixItems", "const"):
                assert forbidden not in node, f"Leaked '{forbidden}' at {location}"
            assert node.get("type") != "null", f"Invalid OAS 3.0.2 type='null' at {location}"
            for bound_key in ("exclusiveMinimum", "exclusiveMaximum"):
                if bound_key in node:
                    assert isinstance(node[bound_key], bool), f"Numeric {bound_key} at {location}"
            if "discriminator" in node:
                assert "anyOf" not in node, f"Discriminator with anyOf at {location}"

            for k, v in node.items():
                _walk(v, f"{location}/{k}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                _walk(item, f"{location}[{idx}]")

    _walk(doc)


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/func"),
        ("POST", "/func"),
        ("GET", "/class"),
        ("PUT", "/class"),
    ],
)
def test_openapi_schema_generators(
    request_factory: ty.Any,
    method: str,
    path: str,
    snapshot_json: ty.Any,
) -> None:
    urlconf = create_views_urlconf(openapi.AutoSchema)
    generator = SchemaGenerator(urlconf=urlconf)
    request = Request(request_factory.generic(method, path))
    generated = generator.get_schema(request)
    assert_valid_openapi_302(generated)
    assert snapshot_json() == generated


class CatVariant(pydantic.BaseModel):
    pet_type: ty.Literal["cat"] = "cat"
    meows: int = pydantic.Field(gt=0, lt=10)


class DogVariant(pydantic.BaseModel):
    pet_type: ty.Literal["dog"] = "dog"
    barks: float = pydantic.Field(gt=0.0, lt=5.0)


class DialectModel(pydantic.BaseModel):
    opt_name: str | None = None
    opt_inner: InnerSchema | None = None
    fixed_pair: tuple[int, str]
    single_tuple: tuple[int]
    const_tag: ty.Literal["fixed"] = "fixed"
    pet: ty.Annotated[CatVariant | DogVariant, pydantic.Field(discriminator="pet_type")]
    opt_pet: ty.Annotated[CatVariant | DogVariant | None, pydantic.Field(discriminator="pet_type")] = None


class TreeNode(pydantic.BaseModel):
    label: str
    children: list[TreeNode] = pydantic.Field(default_factory=list)


TreeNode.model_rebuild()


def test_openapi_302_dialect_metadata_generics_and_recursion() -> None:
    """Draft 2020-12 normalization, discriminated unions (#31), shared model deduplication (#4),
    generic models, recursive models, DRF metadata preservation, and nested DRF serializers."""
    T = ty.TypeVar("T")

    class GenericBox(pydantic.BaseModel, ty.Generic[T]):
        value: T

    NullablePetUnion = ty.Annotated[
        CatVariant | DogVariant | None,
        pydantic.Field(discriminator="pet_type", title="Complex Pet"),
    ]

    class ChildDRFSerializer(serializers.Serializer):
        nested_schema = rest_framework.SchemaField(InnerSchema, help_text="Nested ref with description")

    class DialectSerializer(serializers.ModelSerializer):
        sample_field = rest_framework.SchemaField(InnerSchema, help_text="Primary inner schema", read_only=True)
        sample_list = rest_framework.SchemaField(list[InnerSchema], write_only=True, help_text="Write-only list")
        sample_seq = rest_framework.SchemaField(list[InnerSchema], default=[])
        data = rest_framework.SchemaField(DialectModel)
        secondary_inner = rest_framework.SchemaField(InnerSchema)
        nullable_model = rest_framework.SchemaField(InnerSchema, allow_null=True)
        opt_model = rest_framework.SchemaField(InnerSchema | None)
        nullable_discriminated_pet = rest_framework.SchemaField(NullablePetUnion, required=False)
        multi_union = rest_framework.SchemaField(CatVariant | DogVariant | None)
        allow_null_union = rest_framework.SchemaField(CatVariant | DogVariant, allow_null=True)
        root_box = rest_framework.SchemaField(GenericBox[int])
        nullable_box = rest_framework.SchemaField(GenericBox[int], allow_null=True)
        box_list = rest_framework.SchemaField(list[GenericBox[int]])
        tree = rest_framework.SchemaField(TreeNode)
        child = ChildDRFSerializer()
        children_list = ChildDRFSerializer(many=True)
        schema_list = serializers.ListField(
            child=rest_framework.SchemaField(InnerSchema, help_text="Item ref with description")
        )

        class Meta:
            model = SampleModel
            fields = (
                "sample_field",
                "sample_list",
                "sample_seq",
                "data",
                "secondary_inner",
                "nullable_model",
                "opt_model",
                "nullable_discriminated_pet",
                "multi_union",
                "allow_null_union",
                "root_box",
                "nullable_box",
                "box_list",
                "tree",
                "child",
                "children_list",
                "schema_list",
            )

    class DialectView(generics.RetrieveUpdateAPIView):
        serializer_class = DialectSerializer
        schema = openapi.AutoSchema()

    generator = SchemaGenerator(patterns=[path("dialect/", DialectView.as_view())])
    doc = generator.get_schema(request=None, public=True)
    assert_valid_openapi_302(doc)

    schemas = doc["components"]["schemas"]
    assert {"InnerSchema", "CatVariant", "DogVariant", "GenericBox_int_", "TreeNode"} <= schemas.keys()
    assert "GenericBox[int]" not in schemas
    assert schemas["TreeNode"]["properties"]["children"]["items"] == {"$ref": "#/components/schemas/TreeNode"}

    dialect_props = schemas["DialectModel"]["properties"]
    assert dialect_props["opt_name"]["nullable"] is True
    assert dialect_props["opt_inner"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "nullable": True,
        "default": None,
    }
    assert dialect_props["fixed_pair"] == {
        "title": "Fixed Pair",
        "type": "array",
        "items": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
        "minItems": 2,
        "maxItems": 2,
    }
    assert dialect_props["single_tuple"] == {
        "title": "Single Tuple",
        "type": "array",
        "items": {"type": "integer"},
        "minItems": 1,
        "maxItems": 1,
    }
    assert dialect_props["const_tag"]["enum"] == ["fixed"]
    cat_meows = schemas["CatVariant"]["properties"]["meows"]
    assert cat_meows["minimum"] == 0 and cat_meows["exclusiveMinimum"] is True
    assert cat_meows["maximum"] == 10 and cat_meows["exclusiveMaximum"] is True

    expected_discriminated = {
        "oneOf": [{"$ref": "#/components/schemas/CatVariant"}, {"$ref": "#/components/schemas/DogVariant"}],
        "discriminator": {
            "propertyName": "pet_type",
            "mapping": {"cat": "#/components/schemas/CatVariant", "dog": "#/components/schemas/DogVariant"},
        },
        "nullable": True,
    }
    assert dialect_props["opt_pet"] == {"title": "Opt Pet", **expected_discriminated, "default": None}

    ser_props = schemas["Dialect"]["properties"]
    assert ser_props["sample_field"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "description": "Primary inner schema",
        "readOnly": True,
    }
    assert ser_props["sample_list"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/InnerSchema"},
        "writeOnly": True,
        "description": "Write-only list",
    }
    assert ser_props["sample_seq"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/InnerSchema"},
        "default": [],
    }
    assert ser_props["secondary_inner"] == {"$ref": "#/components/schemas/InnerSchema"}
    assert ser_props["nullable_model"] == {"allOf": [{"$ref": "#/components/schemas/InnerSchema"}], "nullable": True}
    assert ser_props["opt_model"] == {"allOf": [{"$ref": "#/components/schemas/InnerSchema"}], "nullable": True}
    assert ser_props["nullable_discriminated_pet"] == expected_discriminated
    assert ser_props["multi_union"] == {
        "anyOf": [{"$ref": "#/components/schemas/CatVariant"}, {"$ref": "#/components/schemas/DogVariant"}],
        "nullable": True,
    }
    assert ser_props["allow_null_union"] == ser_props["multi_union"]
    assert ser_props["root_box"] == {"$ref": "#/components/schemas/GenericBox_int_"}
    assert ser_props["nullable_box"] == {"allOf": [{"$ref": "#/components/schemas/GenericBox_int_"}], "nullable": True}
    assert ser_props["box_list"] == {"type": "array", "items": {"$ref": "#/components/schemas/GenericBox_int_"}}
    assert ser_props["child"]["properties"]["nested_schema"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "description": "Nested ref with description",
    }
    assert ser_props["children_list"]["items"]["properties"]["nested_schema"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "description": "Nested ref with description",
    }
    assert ser_props["schema_list"]["items"] == {"$ref": "#/components/schemas/InnerSchema"}


class SplitAliasModel(pydantic.BaseModel):
    internal_id: int = pydantic.Field(validation_alias="input_id", serialization_alias="output_id")


class WriteOnlyNestedModel(pydantic.BaseModel):
    secret_token: str


class WriteRequestEnvelope(pydantic.BaseModel):
    nested: WriteOnlyNestedModel
    shared: SplitAliasModel


def test_views_components_modes_and_renderers() -> None:
    """Standalone get_components, DELETE views, validation vs serialization mode, untyped/paginated/context renderers."""

    class AliasSerializer(serializers.Serializer):
        item = rest_framework.SchemaField(SplitAliasModel)

    class WriteAliasSerializer(serializers.Serializer):
        envelope = rest_framework.SchemaField(WriteRequestEnvelope)

    class SplitReadWriteAutoSchema(openapi.AutoSchema):
        def get_request_serializer(self, path: str, method: str) -> serializers.BaseSerializer | None:
            return WriteAliasSerializer()

        def get_response_serializer(self, path: str, method: str) -> serializers.BaseSerializer | None:
            return AliasSerializer()

    class SplitReadWriteView(generics.RetrieveUpdateAPIView):
        serializer_class = AliasSerializer
        schema = SplitReadWriteAutoSchema(operation_id_base="SplitReadWriteAlias")

    @api_view(["POST", "DELETE"])
    @schema(openapi.AutoSchema())
    @parser_classes([rest_framework.SchemaParser[InnerSchema]])
    @renderer_classes([rest_framework.SchemaRenderer[InnerSchema]])
    def delete_and_post_view(request):
        return Response()

    class UntypedRendererView(views.APIView):
        renderer_classes = [rest_framework.SchemaRenderer]
        schema = openapi.AutoSchema()

        def get(self, request):
            return Response({})

    class ContextFallbackView(views.APIView):
        parser_classes = [rest_framework.SchemaParser]
        renderer_classes = [rest_framework.SchemaRenderer]
        schema = openapi.AutoSchema()

        def get_renderer_context(self):
            return dict(super().get_renderer_context(), renderer_schema=InnerSchema)

        def get_parser_context(self, http_request):
            return dict(super().get_parser_context(http_request), parser_schema=InnerSchema)

        def post(self, request):
            return Response({})

    class PaginatedRendererView(views.APIView):
        renderer_classes = [rest_framework.SchemaRenderer[list[InnerSchema]]]
        pagination_class = pagination.PageNumberPagination
        schema = openapi.AutoSchema()

        def get(self, request):
            return Response([])

    generator = SchemaGenerator(
        patterns=[
            path("split/", SplitReadWriteView.as_view()),
            path("items/", delete_and_post_view),
            path("untyped/", UntypedRendererView.as_view()),
            path("context/", ContextFallbackView.as_view()),
            path("paginated/", PaginatedRendererView.as_view()),
        ]
    )
    doc = generator.get_schema(request=None, public=True)
    assert_valid_openapi_302(doc)

    schemas = doc["components"]["schemas"]
    assert "output_id" in schemas["SplitAliasModel"]["properties"]
    assert "input_id" not in schemas["SplitAliasModel"]["properties"]
    assert {"WriteOnlyNestedModel", "WriteRequestEnvelope", "InnerSchema"} <= schemas.keys()
    assert doc["paths"]["/items/"]["delete"]["responses"] == {"204": {"description": ""}}
    assert doc["paths"]["/untyped/"]["get"]["responses"]["200"]["content"]["application/json"] == {"schema": {}}
    assert doc["paths"]["/context/"]["post"]["responses"]["201"]["content"]["application/json"] == {
        "schema": {"$ref": "#/components/schemas/InnerSchema"},
    }
    paginated_schema = doc["paths"]["/paginated/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert paginated_schema["properties"]["results"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/InnerSchema"},
    }

    # Standalone get_components (without get_operation) for POST, DELETE, and GET
    class WriteParserOnlyView(views.APIView):
        parser_classes = [rest_framework.SchemaParser[SplitAliasModel]]
        schema = openapi.AutoSchema()

        def get(self, request):
            return Response({})

        def post(self, request):
            return Response({})

        def delete(self, request):
            return Response(status=204)

    wp_view = WriteParserOnlyView()
    wp_view.request = None
    wp_view.format_kwarg = None
    assert "SplitAliasModel" not in wp_view.schema.get_components("/wp/", "GET")
    assert wp_view.schema.get_components("/wp/", "DELETE") == {}
    assert "input_id" in wp_view.schema.get_components("/wp/", "POST")["SplitAliasModel"]["properties"]
