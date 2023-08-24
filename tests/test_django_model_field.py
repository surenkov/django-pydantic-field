import json
import sys
import typing as t
from collections import abc
from copy import copy
from datetime import date

import django
import pytest
from django.core.exceptions import FieldError, ValidationError
from django.db import models
from django.db.migrations.writer import MigrationWriter
from django_pydantic_field import fields

from .conftest import InnerSchema, SampleDataclass
from .sample_app.models import Building
from .test_app.models import SampleForwardRefModel, SampleModel, SampleSchema


def test_sample_field():
    sample_field = fields.PydanticSchemaField(schema=InnerSchema)
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    expected_encoded = {"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}
    if django.VERSION[:2] < (4, 2):
        expected_encoded = json.dumps(expected_encoded)

    assert sample_field.get_prep_value(existing_instance) == expected_encoded
    assert sample_field.to_python(expected_encoded) == existing_instance


def test_sample_field_with_raw_data():
    sample_field = fields.PydanticSchemaField(schema=InnerSchema)
    existing_raw = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}

    expected_encoded = {"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}
    if django.VERSION[:2] < (4, 2):
        expected_encoded = json.dumps(expected_encoded)

    assert sample_field.get_prep_value(existing_raw) == expected_encoded
    assert sample_field.to_python(expected_encoded) == InnerSchema(**existing_raw)


def test_simple_model_field():
    sample_field = SampleModel._meta.get_field("sample_field")
    assert sample_field.schema == InnerSchema

    sample_list_field = SampleModel._meta.get_field("sample_list")
    assert sample_list_field.schema == t.List[InnerSchema]

    sample_seq_field = SampleModel._meta.get_field("sample_seq")
    assert sample_seq_field.schema == t.List[InnerSchema]

    existing_raw_field = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    existing_raw_list = [{"stub_str": "abc", "stub_list": []}]

    instance = SampleModel(
        sample_field=existing_raw_field, sample_list=existing_raw_list
    )

    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_list = [InnerSchema(stub_str="abc", stub_list=[])]

    assert instance.sample_field == expected_instance
    assert instance.sample_list == expected_list


def test_null_field():
    field = fields.SchemaField(InnerSchema, null=True, default=None)
    assert field.to_python(None) is None
    assert field.get_prep_value(None) is None

    field = fields.SchemaField(t.Optional[InnerSchema], null=True, default=None)
    assert field.get_prep_value(None) is None


def test_untyped_model_field_raises():
    with pytest.raises(FieldError):

        class UntypedModel(models.Model):
            sample_field = fields.SchemaField()

            class Meta:
                app_label = "test_app"


def test_forwardrefs_deferred_resolution():
    obj = SampleForwardRefModel(field={}, annotated_field={})
    assert isinstance(obj.field, SampleSchema)
    assert isinstance(obj.annotated_field, SampleSchema)


@pytest.mark.parametrize(
    "forward_ref", ["InnerSchema", t.ForwardRef("SampleDataclass"), t.List["int"]]
)
def test_resolved_forwardrefs(forward_ref):
    class ModelWithForwardRefs(models.Model):
        field: forward_ref = fields.SchemaField()

        class Meta:
            app_label = "test_app"


@pytest.mark.parametrize(
    "field",
    [
        fields.PydanticSchemaField(
            schema=InnerSchema,
            default=InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        ),
        fields.PydanticSchemaField(
            schema=InnerSchema,
            default=(("stub_str", "abc"), ("stub_list", [date(2022, 7, 1)])),
        ),
        fields.PydanticSchemaField(
            schema=InnerSchema,
            default={"stub_str": "abc", "stub_list": [date(2022, 7, 1)]},
        ),
        fields.PydanticSchemaField(schema=InnerSchema, null=True, default=None),
        fields.PydanticSchemaField(
            schema=SampleDataclass,
            default={"stub_str": "abc", "stub_list": [date(2022, 7, 1)]},
        ),
        fields.PydanticSchemaField(
            schema=t.Optional[InnerSchema], null=True, default=None
        ),
    ],
)
def test_field_serialization(field):
    _test_field_serialization(field)


@pytest.mark.skipif(
    sys.version_info < (3, 9), reason="Built-in type subscription supports only in 3.9+"
)
@pytest.mark.parametrize(
    "field_factory",
    [
        lambda: fields.PydanticSchemaField(schema=list[InnerSchema], default=list),
        lambda: fields.PydanticSchemaField(schema=dict[str, InnerSchema], default=list),
        lambda: fields.PydanticSchemaField(
            schema=abc.Sequence[InnerSchema], default=list
        ),
        lambda: fields.PydanticSchemaField(
            schema=abc.Mapping[str, InnerSchema], default=dict
        ),
    ],
)
def test_field_builtin_annotations_serialization(field_factory):
    _test_field_serialization(field_factory())


@pytest.mark.skipif(
    sys.version_info < (3, 10), reason="Union type syntax supported only in 3.10+"
)
def test_field_union_type_serialization():
    field = fields.PydanticSchemaField(
        schema=(InnerSchema | None), null=True, default=None
    )
    _test_field_serialization(field)


@pytest.mark.skipif(
    sys.version_info >= (3, 9), reason="Should test against builtin generic types"
)
@pytest.mark.parametrize(
    "field",
    [
        fields.PydanticSchemaField(schema=t.List[InnerSchema], default=list),
        fields.PydanticSchemaField(schema=t.Dict[str, InnerSchema], default=list),
        fields.PydanticSchemaField(schema=t.Sequence[InnerSchema], default=list),
        fields.PydanticSchemaField(schema=t.Mapping[str, InnerSchema], default=dict),
    ],
)
def test_field_typing_annotations_serialization(field):
    _test_field_serialization(field)


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="Typing-to-builtin migrations is reasonable only on py >= 3.9",
)
@pytest.mark.parametrize(
    "old_field, new_field",
    [
        (
            lambda: fields.PydanticSchemaField(
                schema=t.List[InnerSchema], default=list
            ),
            lambda: fields.PydanticSchemaField(schema=list[InnerSchema], default=list),
        ),
        (
            lambda: fields.PydanticSchemaField(
                schema=t.Dict[str, InnerSchema], default=list
            ),
            lambda: fields.PydanticSchemaField(
                schema=dict[str, InnerSchema], default=list
            ),
        ),
        (
            lambda: fields.PydanticSchemaField(
                schema=t.Sequence[InnerSchema], default=list
            ),
            lambda: fields.PydanticSchemaField(
                schema=abc.Sequence[InnerSchema], default=list
            ),
        ),
        (
            lambda: fields.PydanticSchemaField(
                schema=t.Mapping[str, InnerSchema], default=dict
            ),
            lambda: fields.PydanticSchemaField(
                schema=abc.Mapping[str, InnerSchema], default=dict
            ),
        ),
        (
            lambda: fields.PydanticSchemaField(
                schema=t.Mapping[str, InnerSchema], default=dict
            ),
            lambda: fields.PydanticSchemaField(
                schema=abc.Mapping[str, InnerSchema], default=dict
            ),
        ),
    ],
)
def test_field_typing_to_builtin_serialization(old_field, new_field):
    old_field, new_field = old_field(), new_field()

    _, _, args, kwargs = old_field.deconstruct()

    reconstructed_field = fields.PydanticSchemaField(*args, **kwargs)
    assert (
        old_field.get_default()
        == new_field.get_default()
        == reconstructed_field.get_default()
    )
    assert new_field.schema == reconstructed_field.schema

    deserialized_field = reconstruct_field(serialize_field(old_field))
    assert (
        old_field.get_default()
        == deserialized_field.get_default()
        == new_field.get_default()
    )
    assert new_field.schema == deserialized_field.schema


@pytest.mark.parametrize(
    "field, flawed_data",
    [
        (fields.PydanticSchemaField(schema=InnerSchema), {}),
        (fields.PydanticSchemaField(schema=t.List[InnerSchema]), [{}]),
        (fields.PydanticSchemaField(schema=t.Dict[int, float]), {"1": "abc"}),
    ],
)
def test_field_validation_exceptions(field, flawed_data):
    with pytest.raises(ValidationError):
        field.to_python(flawed_data)


def test_model_validation_exceptions():
    with pytest.raises(ValidationError):
        SampleModel(sample_field=1)
    with pytest.raises(ValidationError):
        SampleModel(sample_field={"stub_list": {}, "stub_str": ""})

    valid_initial = SampleModel(
        sample_field={"stub_list": [], "stub_str": ""},
        sample_list=[],
        sample_seq=[],
    )
    with pytest.raises(ValidationError):
        valid_initial.sample_field = 1


@pytest.mark.parametrize(
    "export_kwargs",
    [
        {"include": {"stub_str", "stub_int"}},
        {"exclude": {"stub_list"}},
        {"by_alias": True},
        {"exclude_unset": True},
        {"exclude_defaults": True},
        {"exclude_none": True},
    ],
)
def test_export_kwargs_support(export_kwargs):
    field = fields.PydanticSchemaField(
        schema=InnerSchema,
        default=InnerSchema(stub_str="", stub_list=[]),
        **export_kwargs,
    )
    _test_field_serialization(field)

    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    assert field.get_prep_value(existing_instance)


def _test_field_serialization(field):
    _, _, args, kwargs = field.deconstruct()

    reconstructed_field = fields.PydanticSchemaField(*args, **kwargs)
    assert field.get_default() == reconstructed_field.get_default()
    assert field.schema == reconstructed_field.schema

    deserialized_field = reconstruct_field(serialize_field(field))
    assert deserialized_field.get_default() == field.get_default()
    assert field.schema == deserialized_field.schema


def serialize_field(field: fields.PydanticSchemaField) -> str:
    serialized_field, _ = MigrationWriter.serialize(field)
    return serialized_field


def reconstruct_field(field_repr: str) -> fields.PydanticSchemaField:
    return eval(field_repr, globals(), sys.modules)


def test_copy_field():
    copied = copy(Building.meta.field)

    assert copied.name == Building.meta.field.name
    assert copied.attname == Building.meta.field.attname
    assert copied.concrete == Building.meta.field.concrete
