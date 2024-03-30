import typing as ty
from datetime import date

import pydantic
import pytest
import typing_extensions as te
from rest_framework import exceptions, serializers

from tests.conftest import InnerSchema
from tests.test_app.models import SampleModel

rest_framework = pytest.importorskip("django_pydantic_field.v2.rest_framework")


class SampleSerializer(serializers.Serializer):
    field = rest_framework.SchemaField(schema=ty.List[InnerSchema])
    annotated = rest_framework.SchemaField(
        schema=te.Annotated[ty.List[InnerSchema], pydantic.Field(alias="annotated_field")],
        default=list,
        by_alias=True,
    )


class SampleModelSerializer(serializers.ModelSerializer):
    sample_field = rest_framework.SchemaField(schema=InnerSchema)
    sample_list = rest_framework.SchemaField(schema=ty.List[InnerSchema])
    sample_seq = rest_framework.SchemaField(schema=ty.List[InnerSchema], default=list)

    class Meta:
        model = SampleModel
        fields = "sample_field", "sample_list", "sample_seq"


def test_schema_field():
    field = rest_framework.SchemaField(InnerSchema)
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = {
        "stub_str": "abc",
        "stub_int": 1,
        "stub_list": ["2022-07-01"],
    }

    assert field.to_representation(existing_instance) == expected_encoded
    assert field.to_internal_value(expected_encoded) == existing_instance

    with pytest.raises(serializers.ValidationError):
        field.to_internal_value(None)

    with pytest.raises(serializers.ValidationError):
        field.to_internal_value("null")


def test_field_schema_with_custom_config():
    field = rest_framework.SchemaField(InnerSchema, allow_null=True, exclude={"stub_int"})
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = {"stub_str": "abc", "stub_list": ["2022-07-01"]}

    assert field.to_representation(existing_instance) == expected_encoded
    assert field.to_internal_value(expected_encoded) == existing_instance
    assert field.to_internal_value(None) is None
    assert field.to_internal_value("null") is None


def test_serializer_marshalling_with_schema_field():
    existing_instance = {"field": [InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])], "annotated_field": []}
    expected_data = {"field": [{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}], "annotated": []}
    expected_validated_data = {"field": [InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])], "annotated": []}

    serializer = SampleSerializer(instance=existing_instance)
    assert serializer.data == expected_data

    serializer = SampleSerializer(data=expected_data)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == expected_validated_data


def test_model_serializer_marshalling_with_schema_field():
    instance = SampleModel(
        sample_field=InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        sample_list=[InnerSchema(stub_str="abc", stub_int=2, stub_list=[date(2022, 7, 1)])] * 2,
        sample_seq=[InnerSchema(stub_str="abc", stub_int=3, stub_list=[date(2022, 7, 1)])] * 3,
    )
    serializer = SampleModelSerializer(instance)

    expected_data = {
        "sample_field": {"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]},
        "sample_list": [{"stub_str": "abc", "stub_int": 2, "stub_list": ["2022-07-01"]}] * 2,
        "sample_seq": [{"stub_str": "abc", "stub_int": 3, "stub_list": ["2022-07-01"]}] * 3,
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
    field = rest_framework.SchemaField(InnerSchema, **export_kwargs)
    assert field.to_representation(InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]))


def test_invalid_data_serialization():
    invalid_data = {"field": [{"stub_int": "abc", "stub_list": ["abc"]}]}
    serializer = SampleSerializer(data=invalid_data)

    with pytest.raises(exceptions.ValidationError) as e:
        serializer.is_valid(raise_exception=True)

    assert e.match(r".*stub_str.*stub_int.*stub_list.*")
