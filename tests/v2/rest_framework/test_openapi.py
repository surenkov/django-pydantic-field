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

    # 1. Every Media Type Object inside requestBody / responses must wrap its schema in {"schema": ...}
    #    and BrowsableAPIRenderer ("text/html") must not leak into responses.
    for path_item in doc.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            req_content = operation.get("requestBody", {}).get("content", {})
            for media_type, media_obj in req_content.items():
                assert "schema" in media_obj, f"Missing 'schema' in requestBody media object for {media_type}"
                assert "$ref" not in media_obj, f"Unwrapped '$ref' in requestBody media object for {media_type}"
            for status_code, resp_obj in operation.get("responses", {}).items():
                resp_content = resp_obj.get("content", {})
                assert "text/html" not in resp_content, f"Leaked text/html in response {status_code}"
                for media_type, media_obj in resp_content.items():
                    assert "schema" in media_obj, f"Missing 'schema' in response {status_code} for {media_type}"
                    assert "$ref" not in media_obj, f"Unwrapped '$ref' in response {status_code} for {media_type}"

    # 2. Walk the entire document to verify:
    #    - Every $ref points to #/components/schemas/<Name> and <Name> exists in components.schemas
    #    - No $ref object has sibling properties (must use allOf in OpenAPI 3.0.2)
    #    - No JSON Schema Draft 2020-12 / Draft 7 keywords ($defs, definitions, prefixItems, const, type: "null", numeric exclusiveMinimum/Maximum)
    def _walk(node: ty.Any, location: str = "#") -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                assert ref.startswith("#/components/schemas/"), f"Non-component $ref {ref} at {location}"
                target = ref.split("#/components/schemas/", 1)[1]
                assert target in components_schemas, f"Unresolvable $ref {ref} at {location}"
                assert len(node) == 1, f"$ref at {location} has invalid OAS 3.0.2 siblings: {list(node.keys())}"

            assert "$defs" not in node, f"Leaked '$defs' at {location}"
            assert "definitions" not in node, f"Leaked 'definitions' at {location}"
            assert "prefixItems" not in node, f"Leaked Draft 2020-12 'prefixItems' at {location}"
            assert "const" not in node, f"Leaked Draft 2020-12 'const' at {location}"
            assert node.get("type") != "null", f"Invalid OAS 3.0.2 type='null' at {location}"
            if "exclusiveMinimum" in node:
                assert isinstance(node["exclusiveMinimum"], bool), f"Numeric exclusiveMinimum at {location}"
            if "exclusiveMaximum" in node:
                assert isinstance(node["exclusiveMaximum"], bool), f"Numeric exclusiveMaximum at {location}"
            if "discriminator" in node:
                assert "anyOf" not in node, f"Discriminator with anyOf (instead of oneOf) at {location}"

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


def test_standalone_get_components_without_get_operation() -> None:
    """F3: Calling view.schema.get_components(path, method) directly without calling get_operation first."""

    class DirectView(views.APIView):
        parser_classes = [rest_framework.SchemaParser[InnerSchema]]
        renderer_classes = [rest_framework.SchemaRenderer[list[InnerSchema]]]
        schema = openapi.AutoSchema()

        def post(self, request):
            return Response([])

    view = DirectView()
    view.request = None
    view.format_kwarg = None
    components = view.schema.get_components("/direct", "POST")
    assert "InnerSchema" in components
    assert components["InnerSchema"]["type"] == "object"


def test_delete_view_alongside_schema_parser_renderer(request_factory: ty.Any) -> None:
    """F3: Views supporting DELETE alongside POST/GET with SchemaParser/SchemaRenderer."""

    @api_view(["POST", "DELETE"])
    @schema(openapi.AutoSchema())
    @parser_classes([rest_framework.SchemaParser[InnerSchema]])
    @renderer_classes([rest_framework.SchemaRenderer[InnerSchema]])
    def delete_and_post_view(request):
        return Response()

    generator = SchemaGenerator(patterns=[path("items/", delete_and_post_view)])
    doc = generator.get_schema(request=None, public=True)
    assert_valid_openapi_302(doc)
    assert "InnerSchema" in doc["components"]["schemas"]
    assert doc["paths"]["/items/"]["delete"]["responses"] == {"204": {"description": ""}}

    class DeleteOnlyView(views.APIView):
        parser_classes = [rest_framework.SchemaParser[InnerSchema]]
        renderer_classes = [rest_framework.SchemaRenderer[InnerSchema]]
        schema = openapi.AutoSchema()

        def delete(self, request):
            return Response(status=204)

    delete_view = DeleteOnlyView()
    delete_view.request = None
    delete_view.format_kwarg = None
    delete_components = delete_view.schema.get_components("/items/", "DELETE")
    assert "InnerSchema" in delete_components


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


def test_openapi_302_dialect_normalization() -> None:
    """F4 & F9: Draft 2020-12 constructs normalized to valid OpenAPI 3.0.2."""

    class DialectSerializer(serializers.Serializer):
        data = rest_framework.SchemaField(DialectModel)
        nullable_model = rest_framework.SchemaField(InnerSchema, allow_null=True)
        opt_model = rest_framework.SchemaField(ty.Optional[InnerSchema])

    class DialectView(generics.RetrieveUpdateAPIView):
        serializer_class = DialectSerializer
        schema = openapi.AutoSchema()

    generator = SchemaGenerator(patterns=[path("dialect/", DialectView.as_view())])
    doc = generator.get_schema(request=None, public=True)
    assert_valid_openapi_302(doc)

    schemas = doc["components"]["schemas"]
    dialect_props = schemas["DialectModel"]["properties"]

    # Optional primitive -> nullable: True
    assert dialect_props["opt_name"]["type"] == "string"
    assert dialect_props["opt_name"]["nullable"] is True

    # Optional $ref -> allOf + nullable: True
    assert dialect_props["opt_inner"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "nullable": True,
        "default": None,
    }

    # Fixed tuple -> items with anyOf + minItems + maxItems
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

    # Literal["fixed"] -> enum: ["fixed"]
    assert dialect_props["const_tag"]["enum"] == ["fixed"]
    assert "const" not in dialect_props["const_tag"]

    # Exclusive numeric bounds -> minimum/maximum + boolean exclusiveMinimum/Maximum
    cat_meows = schemas["CatVariant"]["properties"]["meows"]
    assert cat_meows["minimum"] == 0
    assert cat_meows["exclusiveMinimum"] is True
    assert cat_meows["maximum"] == 10
    assert cat_meows["exclusiveMaximum"] is True

    # Discriminated union -> oneOf + discriminator
    assert "oneOf" in dialect_props["pet"]
    assert "anyOf" not in dialect_props["pet"]
    assert dialect_props["pet"]["discriminator"]["propertyName"] == "pet_type"

    # Serializer-level allow_null and Optional[InnerSchema]
    ser_props = schemas["Dialect"]["properties"]
    assert ser_props["nullable_model"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "nullable": True,
    }
    assert ser_props["opt_model"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "nullable": True,
    }

    # Direct translate_adapter_schema with unwrap_root_nullable=False on nullable root BaseModel
    from django_pydantic_field._internal._openapi import translate_adapter_schema
    from django_pydantic_field.v2.types import SchemaAdapter

    nullable_adapter = SchemaAdapter(InnerSchema, None, None, None, allow_null=True)
    translated = translate_adapter_schema(nullable_adapter, unwrap_root_nullable=False)
    assert translated.schema == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "nullable": True,
    }
    assert "InnerSchema" in translated.components


def test_drf_field_metadata_preservation_and_ref_wrapping() -> None:
    """F5: Preserve readOnly, writeOnly, nullable, default, description and wrap $ref siblings in allOf."""

    class MetadataSerializer(serializers.ModelSerializer):
        sample_field = rest_framework.SchemaField(
            schema=InnerSchema,
            help_text="Primary inner schema",
            read_only=True,
        )
        sample_list = rest_framework.SchemaField(
            schema=list[InnerSchema],
            write_only=True,
            help_text="Write-only list",
        )
        sample_seq = rest_framework.SchemaField(
            schema=list[InnerSchema],
            default=[],
        )

        class Meta:
            model = SampleModel
            fields = ("sample_field", "sample_list", "sample_seq")

    class MetadataView(generics.RetrieveUpdateAPIView):
        serializer_class = MetadataSerializer
        schema = openapi.AutoSchema()

    generator = SchemaGenerator(patterns=[path("meta/", MetadataView.as_view())])
    doc = generator.get_schema(request=None, public=True)
    assert_valid_openapi_302(doc)

    props = doc["components"]["schemas"]["Metadata"]["properties"]
    assert props["sample_field"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "description": "Primary inner schema",
        "readOnly": True,
    }
    assert props["sample_list"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/InnerSchema"},
        "writeOnly": True,
        "description": "Write-only list",
    }
    assert props["sample_seq"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/InnerSchema"},
        "default": [],
    }


class SplitAliasModel(pydantic.BaseModel):
    internal_id: int = pydantic.Field(validation_alias="input_id", serialization_alias="output_id")


class WriteOnlyNestedModel(pydantic.BaseModel):
    secret_token: str


class WriteRequestEnvelope(pydantic.BaseModel):
    nested: WriteOnlyNestedModel
    shared: SplitAliasModel


def test_request_vs_response_serialization_mode_on_read_and_write_views() -> None:
    """F6: Read-only and combined read/write views preserve 'serialization' mode for shared components
    while retaining validation-only nested $defs models from request serializers."""

    class AliasSerializer(serializers.Serializer):
        item = rest_framework.SchemaField(SplitAliasModel)

    class WriteAliasSerializer(serializers.Serializer):
        envelope = rest_framework.SchemaField(WriteRequestEnvelope)

    class ReadOnlyView(generics.RetrieveAPIView):
        serializer_class = AliasSerializer
        schema = openapi.AutoSchema(operation_id_base="ReadOnlyAlias")

    class ReadWriteView(generics.RetrieveUpdateAPIView):
        serializer_class = AliasSerializer
        schema = openapi.AutoSchema(operation_id_base="ReadWriteAlias")

    class SplitReadWriteView(generics.RetrieveUpdateAPIView):
        schema = openapi.AutoSchema(operation_id_base="SplitReadWriteAlias")

        def get_serializer_class(self):
            if getattr(self, "request", None) and self.request.method in ("PUT", "PATCH"):
                return WriteAliasSerializer
            return AliasSerializer

    class SplitReadWriteAutoSchema(openapi.AutoSchema):
        def get_request_serializer(self, path: str, method: str) -> serializers.BaseSerializer | None:
            return WriteAliasSerializer()

        def get_response_serializer(self, path: str, method: str) -> serializers.BaseSerializer | None:
            return AliasSerializer()

    SplitReadWriteView.schema = SplitReadWriteAutoSchema(operation_id_base="SplitReadWriteAlias")

    generator = SchemaGenerator(
        patterns=[
            path("read/", ReadOnlyView.as_view()),
            path("read-write/", ReadWriteView.as_view()),
            path("split-read-write/", SplitReadWriteView.as_view()),
        ]
    )
    doc = generator.get_schema(request=None, public=True)
    assert_valid_openapi_302(doc)
    schemas = doc["components"]["schemas"]
    assert "output_id" in schemas["SplitAliasModel"]["properties"]
    assert "input_id" not in schemas["SplitAliasModel"]["properties"]
    assert "WriteOnlyNestedModel" in schemas
    assert "WriteRequestEnvelope" in schemas


def test_untyped_schema_renderer_and_context_fallback() -> None:
    """F7 & F9: Untyped SchemaRenderer does not raise KeyError; render_schema fallback works."""

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
            ctx = super().get_renderer_context()
            return dict(ctx, render_schema=InnerSchema)

        def get_parser_context(self, http_request):
            ctx = super().get_parser_context(http_request)
            return dict(ctx, parser_schema=InnerSchema)

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
            path("untyped/", UntypedRendererView.as_view()),
            path("context/", ContextFallbackView.as_view()),
            path("paginated/", PaginatedRendererView.as_view()),
        ]
    )
    doc = generator.get_schema(request=None, public=True)
    assert_valid_openapi_302(doc)

    assert doc["paths"]["/untyped/"]["get"]["responses"]["200"]["content"]["application/json"] == {
        "schema": {},
    }
    assert doc["paths"]["/context/"]["post"]["responses"]["201"]["content"]["application/json"] == {
        "schema": {"$ref": "#/components/schemas/InnerSchema"},
    }
    paginated_schema = doc["paths"]["/paginated/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert paginated_schema["type"] == "object"
    assert paginated_schema["properties"]["results"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/InnerSchema"},
    }


class TreeNode(pydantic.BaseModel):
    label: str
    children: list[TreeNode] = pydantic.Field(default_factory=list)


TreeNode.model_rebuild()


def test_recursive_model_and_nested_drf_serializers() -> None:
    """Verify recursive Pydantic models, multi-branch nullable unions, and nested DRF serializers."""

    class ChildDRFSerializer(serializers.Serializer):
        nested_schema = rest_framework.SchemaField(InnerSchema, help_text="Nested ref with description")

    class RootDRFSerializer(serializers.Serializer):
        tree = rest_framework.SchemaField(TreeNode)
        multi_union = rest_framework.SchemaField(CatVariant | DogVariant | None)
        allow_null_union = rest_framework.SchemaField(CatVariant | DogVariant, allow_null=True)
        child = ChildDRFSerializer()
        children_list = ChildDRFSerializer(many=True)
        schema_list = serializers.ListField(
            child=rest_framework.SchemaField(InnerSchema, help_text="Item ref with description")
        )

    class NestedView(generics.RetrieveUpdateAPIView):
        serializer_class = RootDRFSerializer
        schema = openapi.AutoSchema()

    generator = SchemaGenerator(patterns=[path("nested/", NestedView.as_view())])
    doc = generator.get_schema(request=None, public=True)
    assert_valid_openapi_302(doc)

    schemas = doc["components"]["schemas"]
    assert "TreeNode" in schemas
    assert schemas["TreeNode"]["properties"]["children"]["items"] == {"$ref": "#/components/schemas/TreeNode"}
    assert "InnerSchema" in schemas
    assert "CatVariant" in schemas
    assert "DogVariant" in schemas

    root_props = schemas["RootDRF"]["properties"]
    assert root_props["multi_union"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/CatVariant"},
            {"$ref": "#/components/schemas/DogVariant"},
        ],
        "nullable": True,
    }
    assert root_props["allow_null_union"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/CatVariant"},
            {"$ref": "#/components/schemas/DogVariant"},
        ],
        "nullable": True,
    }
    assert root_props["child"]["properties"]["nested_schema"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "description": "Nested ref with description",
    }
    assert root_props["children_list"]["items"]["properties"]["nested_schema"] == {
        "allOf": [{"$ref": "#/components/schemas/InnerSchema"}],
        "description": "Nested ref with description",
    }
    assert root_props["schema_list"]["items"] == {
        "$ref": "#/components/schemas/InnerSchema",
    }
