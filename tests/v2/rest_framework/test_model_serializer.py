from __future__ import annotations

from datetime import date

import pydantic
import pytest
from django.db import models
from django.urls import path
from rest_framework import exceptions, generics, schemas, serializers

from django_pydantic_field import SchemaField as ModelSchemaField
from tests.conftest import InnerSchema
from tests.sample_app.models import Building, BuildingMeta, BuildingTypes
from tests.test_app.models import SampleForwardRefModel, SampleModel, SampleSchema

rest_framework = pytest.importorskip("django_pydantic_field.v2.rest_framework", exc_type=ImportError)


class AutoSampleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SampleModel
        fields = ("sample_field", "sample_list", "sample_seq")


class ConfiguredSchema(pydantic.BaseModel):
    aliased_name: str = pydantic.Field(alias="aliasedName", validation_alias="aliased_name")
    secret: str = "hidden"


class ConfiguredModel(models.Model):
    configured_field: list[ConfiguredSchema] = ModelSchemaField(
        config=pydantic.ConfigDict(str_strip_whitespace=True),
        by_alias=True,
        exclude={"__all__": {"secret"}},
    )
    readonly_field: InnerSchema = ModelSchemaField(
        editable=False,
        default=lambda: InnerSchema(stub_str="ro", stub_list=[date(2022, 7, 1)]),
    )
    nullable_field: InnerSchema | None = ModelSchemaField(null=True, default=None)

    class Meta:
        app_label = "test_app"


def test_auto_model_serializer_resolves_schema_fields():
    serializer = AutoSampleModelSerializer()

    assert isinstance(serializer.fields["sample_field"], rest_framework.SchemaField)
    assert isinstance(serializer.fields["sample_list"], rest_framework.SchemaField)
    assert isinstance(serializer.fields["sample_seq"], rest_framework.SchemaField)

    assert serializer.fields["sample_field"].required is True
    assert serializer.fields["sample_field"].allow_null is False
    assert serializer.fields["sample_list"].required is True
    assert serializer.fields["sample_seq"].required is False


def test_auto_model_serializer_serialization_and_deserialization():
    instance = SampleModel(
        sample_field=InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        sample_list=[InnerSchema(stub_str="def", stub_int=2, stub_list=[date(2022, 7, 2)])],
        sample_seq=[InnerSchema(stub_str="ghi", stub_int=3, stub_list=[date(2022, 7, 3)])],
    )
    serializer = AutoSampleModelSerializer(instance=instance)
    expected_data = {
        "sample_field": {"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]},
        "sample_list": [{"stub_str": "def", "stub_int": 2, "stub_list": ["2022-07-02"]}],
        "sample_seq": [{"stub_str": "ghi", "stub_int": 3, "stub_list": ["2022-07-03"]}],
    }
    assert serializer.data == expected_data

    input_serializer = AutoSampleModelSerializer(
        data={
            "sample_field": {"stub_str": "abc", "stub_list": ["2022-07-01"]},
            "sample_list": [{"stub_str": "def", "stub_int": 2, "stub_list": ["2022-07-02"]}],
        }
    )
    assert input_serializer.is_valid(raise_exception=True)
    assert input_serializer.validated_data == {
        "sample_field": InnerSchema(stub_str="abc", stub_int=1, stub_list=[date(2022, 7, 1)]),
        "sample_list": [InnerSchema(stub_str="def", stub_int=2, stub_list=[date(2022, 7, 2)])],
    }


def test_auto_model_serializer_validation_errors():
    serializer = AutoSampleModelSerializer(
        data={
            "sample_field": {"stub_int": "not_an_int", "stub_list": ["invalid-date"]},
            "sample_list": "not_a_list",
        }
    )
    assert not serializer.is_valid()
    assert "sample_field" in serializer.errors
    assert "sample_list" in serializer.errors

    with pytest.raises(exceptions.ValidationError):
        serializer.is_valid(raise_exception=True)


@pytest.mark.django_db
def test_auto_model_serializer_create_and_partial_update():
    create_serializer = AutoSampleModelSerializer(
        data={
            "sample_field": {"stub_str": "created", "stub_list": ["2022-07-01"]},
            "sample_list": [{"stub_str": "item1", "stub_int": 5, "stub_list": ["2022-07-02"]}],
        }
    )
    assert create_serializer.is_valid(raise_exception=True)
    instance = create_serializer.save()

    assert instance.pk is not None
    assert instance.sample_field == InnerSchema(stub_str="created", stub_int=1, stub_list=[date(2022, 7, 1)])
    assert instance.sample_list == [InnerSchema(stub_str="item1", stub_int=5, stub_list=[date(2022, 7, 2)])]
    assert instance.sample_seq == []

    patch_serializer = AutoSampleModelSerializer(
        instance=instance,
        data={"sample_seq": [{"stub_str": "patched", "stub_int": 9, "stub_list": ["2022-08-01"]}]},
        partial=True,
    )
    assert patch_serializer.is_valid(raise_exception=True)
    updated = patch_serializer.save()

    assert updated.pk == instance.pk
    assert updated.sample_field == InnerSchema(stub_str="created", stub_int=1, stub_list=[date(2022, 7, 1)])
    assert updated.sample_seq == [InnerSchema(stub_str="patched", stub_int=9, stub_list=[date(2022, 8, 1)])]


def test_model_field_kwargs_config_and_export_kwargs_forwarding():
    class ConfiguredModelSerializer(serializers.ModelSerializer):
        class Meta:
            model = ConfiguredModel
            fields = ("configured_field", "readonly_field", "nullable_field")

    serializer = ConfiguredModelSerializer()
    assert serializer.fields["readonly_field"].read_only is True
    assert serializer.fields["nullable_field"].allow_null is True
    assert serializer.fields["nullable_field"].required is False
    assert serializer.fields["configured_field"].config == pydantic.ConfigDict(str_strip_whitespace=True)

    input_serializer = ConfiguredModelSerializer(
        data={
            "configured_field": [{"aliased_name": "hello"}],
            "nullable_field": None,
        }
    )
    assert input_serializer.is_valid(raise_exception=True)
    validated_cfg: list[ConfiguredSchema] = input_serializer.validated_data["configured_field"]
    assert validated_cfg[0].aliased_name == "hello"
    assert input_serializer.validated_data["nullable_field"] is None

    instance = ConfiguredModel(
        configured_field=validated_cfg,
        nullable_field=None,
    )
    output_data = ConfiguredModelSerializer(instance=instance).data
    assert output_data["configured_field"] == [{"aliasedName": "hello"}]
    assert output_data["nullable_field"] is None


def test_forward_ref_model_serializer():
    class ForwardRefModelSerializer(serializers.ModelSerializer):
        class Meta:
            model = SampleForwardRefModel
            fields = ("annotated_field", "field")

    serializer = ForwardRefModelSerializer(
        data={
            "annotated_field": {"field": 10},
            "field": {"field": 20},
        }
    )
    assert serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == {
        "annotated_field": SampleSchema(field=10),
        "field": SampleSchema(field=20),
    }

    instance = SampleForwardRefModel(
        annotated_field=SampleSchema(field=10),
        field=SampleSchema(field=20),
    )
    assert ForwardRefModelSerializer(instance=instance).data == {
        "annotated_field": {"field": 10},
        "field": {"field": 20},
    }


def test_extra_kwargs_and_explicit_schema_field_overrides():
    class CustomSampleModelSerializer(serializers.ModelSerializer):
        # Schema-less explicit override inherits schema from SampleModel.sample_field
        sample_field = rest_framework.SchemaField(help_text="Custom field override", exclude={"stub_int"})

        class Meta:
            model = SampleModel
            fields = ("sample_field", "sample_list", "sample_seq")
            extra_kwargs = {
                "sample_list": {"help_text": "Extra kwargs help", "read_only": True},
                "sample_seq": {"exclude": {"__all__": {"stub_int"}}},
            }

    serializer = CustomSampleModelSerializer()
    assert serializer.fields["sample_field"].help_text == "Custom field override"
    assert serializer.fields["sample_list"].help_text == "Extra kwargs help"
    assert serializer.fields["sample_list"].read_only is True

    instance = SampleModel(
        sample_field=InnerSchema(stub_str="abc", stub_int=1, stub_list=[date(2022, 7, 1)]),
        sample_list=[InnerSchema(stub_str="def", stub_int=2, stub_list=[date(2022, 7, 2)])],
        sample_seq=[InnerSchema(stub_str="ghi", stub_int=3, stub_list=[date(2022, 7, 3)])],
    )
    data = CustomSampleModelSerializer(instance=instance).data
    assert data["sample_field"] == {"stub_str": "abc", "stub_list": ["2022-07-01"]}
    assert data["sample_seq"] == [{"stub_str": "ghi", "stub_list": ["2022-07-03"]}]


def test_serializer_type_annotation_inference():
    class AnnotatedSerializer(serializers.Serializer):
        item: InnerSchema = rest_framework.SchemaField()
        items: list[InnerSchema] = rest_framework.SchemaField(default=list)
        forward_item: "DeferredSerializerSchema" = rest_framework.SchemaField()

    class AnnotatedModelSerializer(serializers.ModelSerializer):
        sample_field: SampleSchema = rest_framework.SchemaField()

        class Meta:
            model = SampleModel
            fields = ("sample_field",)

    serializer = AnnotatedSerializer(
        data={
            "item": {"stub_str": "ann", "stub_list": ["2022-07-01"]},
            "forward_item": {"title": "resolved"},
        }
    )
    assert serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == {
        "item": InnerSchema(stub_str="ann", stub_int=1, stub_list=[date(2022, 7, 1)]),
        "items": [],
        "forward_item": DeferredSerializerSchema(title="resolved"),
    }

    model_serializer = AnnotatedModelSerializer(data={"sample_field": {"field": 99}})
    assert model_serializer.is_valid(raise_exception=True)
    assert model_serializer.validated_data == {"sample_field": SampleSchema(field=99)}


class DeferredSerializerSchema(pydantic.BaseModel):
    title: str


def test_auto_model_serializer_openapi_generation(request_factory):
    import yaml

    class BuildingSerializer(serializers.ModelSerializer):
        class Meta:
            model = Building
            fields = ("opt_meta", "meta", "meta_typing_list")

    class BuildingView(generics.RetrieveUpdateAPIView):
        serializer_class = BuildingSerializer
        schema = rest_framework.openapi.AutoSchema()

        def get_object(self):
            return Building(
                opt_meta=BuildingMeta(buildingType=BuildingTypes.FRAME),
                meta=BuildingMeta(buildingType=BuildingTypes.BRICK),
            )

    patterns = [path("api/buildings/", BuildingView.as_view())]
    schema_view = schemas.get_schema_view(patterns=patterns)
    response = schema_view(request_factory.get("api/buildings/", format="json"))
    results = yaml.load(response.rendered_content, yaml.Loader)

    components = results["components"]["schemas"]
    assert "Building" in components
    assert "BuildingMeta" in components
    props = components["Building"]["properties"]
    assert props["opt_meta"] == {
        "allOf": [{"$ref": "#/components/schemas/BuildingMeta"}],
        "nullable": True,
    }
    assert props["meta"] == {"$ref": "#/components/schemas/BuildingMeta"}
    assert props["meta_typing_list"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/BuildingMeta"},
    }

    pytest.importorskip("drf_spectacular")
    from drf_spectacular.generators import SchemaGenerator
    from drf_spectacular.openapi import AutoSchema as SpectacularAutoSchema

    class SpectacularBuildingView(generics.RetrieveUpdateAPIView):
        serializer_class = BuildingSerializer
        schema = SpectacularAutoSchema()

    generator = SchemaGenerator(patterns=[path("api/spectacular-buildings/", SpectacularBuildingView.as_view())])
    spec_schema = generator.get_schema(request=None, public=True)
    spec_components = spec_schema["components"]["schemas"]
    assert "Building" in spec_components
    assert "BuildingMeta" in spec_components
    assert spec_components["Building"]["properties"]["meta"] == {"$ref": "#/components/schemas/BuildingMeta"}
