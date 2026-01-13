import json
import sys
import typing as ty
from collections import abc
from copy import copy
from datetime import date

import pydantic
import pytest
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.migrations.writer import MigrationWriter
from django.test.utils import isolate_apps

from django_pydantic_field import fields
from django_pydantic_field.compat.pydantic import PYDANTIC_V2

from .conftest import (
    InnerSchema,
    SampleDataclass,
    SampleTypedDict,
    SchemaWithCustomTypes,
)
from .sample_app.models import Building
from .test_app.models import SampleForwardRefModel, SampleModel, SampleSchema

if PYDANTIC_V2:

    class SampleRootModel(pydantic.RootModel):
        root: ty.List[str]

else:

    class SampleRootModel(pydantic.BaseModel):
        __root__: ty.List[str]


@pytest.mark.parametrize(
    "exported_primitive_name",
    ["SchemaField"],
)
def test_module_imports(exported_primitive_name):
    assert exported_primitive_name in dir(fields)
    assert getattr(fields, exported_primitive_name, None) is not None


def test_sample_field():
    sample_field = fields.PydanticSchemaField(schema=InnerSchema)
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    expected_encoded = {"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}
    expected_prepared = json.dumps(expected_encoded)

    assert sample_field.get_db_prep_value(existing_instance, connection) == expected_prepared
    assert sample_field.to_python(expected_encoded) == existing_instance


def test_sample_field_with_raw_data():
    sample_field = fields.PydanticSchemaField(schema=InnerSchema)
    existing_raw = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}

    expected_encoded = {"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}
    expected_prepared = json.dumps(expected_encoded)

    assert sample_field.get_db_prep_value(existing_raw, connection) == expected_prepared
    assert sample_field.to_python(expected_encoded) == InnerSchema(**existing_raw)


def test_null_field():
    field = fields.SchemaField(InnerSchema, null=True, default=None)
    assert field.to_python(None) is None
    assert field.get_prep_value(None) is None

    field = fields.SchemaField(ty.Optional[InnerSchema], null=True, default=None)
    assert field.get_prep_value(None) is None


def test_forwardrefs_deferred_resolution():
    obj = SampleForwardRefModel(field={}, annotated_field={})
    assert isinstance(obj.field, SampleSchema)
    assert isinstance(obj.annotated_field, SampleSchema)


@pytest.mark.parametrize(
    "forward_ref",
    [
        "InnerSchema",
        ty.ForwardRef("SampleDataclass"),
        ty.List["int"],
    ],
)
def test_resolved_forwardrefs(forward_ref):
    with isolate_apps("tests.test_app"):

        class ModelWithForwardRefs(models.Model):
            field = fields.SchemaField(forward_ref)

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
            default={"stub_str": "abc", "stub_list": [date(2022, 7, 1)]},
        ),
        fields.PydanticSchemaField(schema=InnerSchema, null=True, default=None),
        fields.PydanticSchemaField(
            schema=SampleDataclass,
            default={"stub_str": "abc", "stub_list": [date(2022, 7, 1)]},
        ),
        fields.PydanticSchemaField(schema=ty.Optional[InnerSchema], null=True, default=None),
        fields.PydanticSchemaField(schema=SampleRootModel, default=[""]),
        fields.PydanticSchemaField(schema=ty.Optional[SampleRootModel], default=[""]),
        fields.PydanticSchemaField(schema=ty.Optional[SampleRootModel], null=True, default=None),
        fields.PydanticSchemaField(schema=ty.Optional[SampleRootModel], null=True, blank=True),
        fields.PydanticSchemaField(schema=SchemaWithCustomTypes, default={}),
        pytest.param(
            fields.PydanticSchemaField(
                schema=ty.Optional[SampleRootModel],
                default=(SampleRootModel.model_validate([]) if PYDANTIC_V2 else SampleRootModel.parse_obj([])),
            ),
        ),
        pytest.param(
            fields.PydanticSchemaField(
                schema=SampleRootModel,
                default=(SampleRootModel.model_validate([""]) if PYDANTIC_V2 else SampleRootModel.parse_obj([""])),
            ),
        ),
        pytest.param(
            fields.PydanticSchemaField(
                schema=InnerSchema,
                default=(("stub_str", "abc"), ("stub_list", [date(2022, 7, 1)])),
            ),
            marks=[
                pytest.mark.xfail(
                    PYDANTIC_V2,
                    reason="Tuple-based default reconstruction is not supported with Pydantic 2",
                    raises=pydantic.ValidationError,
                ),
                pytest.mark.filterwarnings("ignore::UserWarning"),
            ],
        ),
    ],
)
def test_field_serialization(field):
    _test_field_serialization(field)


@pytest.mark.parametrize(
    "field_factory",
    [
        lambda: fields.PydanticSchemaField(schema=list[InnerSchema], default=list),
        lambda: fields.PydanticSchemaField(schema=dict[str, InnerSchema], default=dict),
        lambda: fields.PydanticSchemaField(schema=abc.Sequence[InnerSchema], default=list),
        lambda: fields.PydanticSchemaField(schema=abc.Mapping[str, InnerSchema], default=dict),
    ],
)
def test_field_builtin_annotations_serialization(field_factory):
    _test_field_serialization(field_factory())


def test_field_union_type_serialization():
    field = fields.PydanticSchemaField(schema=(InnerSchema | None), null=True, default=None)
    _test_field_serialization(field)


@pytest.mark.parametrize(
    "old_field, new_field",
    [
        (
            lambda: fields.PydanticSchemaField(schema=ty.List[InnerSchema], default=list),
            lambda: fields.PydanticSchemaField(schema=list[InnerSchema], default=list),
        ),
        (
            lambda: fields.PydanticSchemaField(schema=ty.Dict[str, InnerSchema], default=dict),
            lambda: fields.PydanticSchemaField(schema=dict[str, InnerSchema], default=dict),
        ),
        (
            lambda: fields.PydanticSchemaField(schema=ty.Sequence[InnerSchema], default=list),
            lambda: fields.PydanticSchemaField(schema=abc.Sequence[InnerSchema], default=list),
        ),
        (
            lambda: fields.PydanticSchemaField(schema=ty.Mapping[str, InnerSchema], default=dict),
            lambda: fields.PydanticSchemaField(schema=abc.Mapping[str, InnerSchema], default=dict),
        ),
        (
            lambda: fields.PydanticSchemaField(schema=ty.Mapping[str, InnerSchema], default=dict),
            lambda: fields.PydanticSchemaField(schema=abc.Mapping[str, InnerSchema], default=dict),
        ),
    ],
)
def test_field_typing_to_builtin_serialization(old_field, new_field):
    old_field, new_field = old_field(), new_field()

    _, _, args, kwargs = old_field.deconstruct()

    reconstructed_field = fields.PydanticSchemaField(*args, **kwargs)
    assert old_field.get_default() == new_field.get_default() == reconstructed_field.get_default()
    assert new_field.schema == reconstructed_field.schema

    deserialized_field = reconstruct_field(serialize_field(old_field))
    assert old_field.get_default() == deserialized_field.get_default() == new_field.get_default()
    assert new_field.schema == deserialized_field.schema


@pytest.mark.parametrize(
    "field, flawed_data",
    [
        (fields.PydanticSchemaField(schema=InnerSchema), {}),
        (fields.PydanticSchemaField(schema=ty.List[InnerSchema]), [{}]),
        (fields.PydanticSchemaField(schema=ty.Dict[int, float]), {"1": "abc"}),
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
    _, _, args, kwargs = field_data = field.deconstruct()

    reconstructed_field = fields.PydanticSchemaField(*args, **kwargs)
    assert field.get_default() == reconstructed_field.get_default()

    assert reconstructed_field.deconstruct() == field_data

    deserialized_field = reconstruct_field(serialize_field(field))
    assert deserialized_field.get_default() == field.get_default()
    assert deserialized_field.deconstruct() == field_data


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


def test_model_init_no_default():
    try:
        SampleModel()
    except Exception:
        pytest.fail("Model with schema field without a default value should be able to initialize")


def test_typeddict_field_serialization():
    field = fields.SchemaField(SampleTypedDict, default={"stub_str": "abc", "stub_int": 1})
    _, _, args, kwargs = field.deconstruct()
    reconstructed_field = fields.SchemaField(*args, **kwargs)

    assert field.get_default() == reconstructed_field.get_default()
    assert field.to_python({"stub_str": "abc", "stub_int": 1}) == {"stub_str": "abc", "stub_int": 1}


def test_typeddict_field_validation():
    field = fields.SchemaField(SampleTypedDict)
    with pytest.raises(ValidationError):
        field.to_python({"stub_str": "abc"})  # missing stub_int


@isolate_apps("tests.test_app")
def test_typeddict_model_field():
    class TypedDictModel(models.Model):
        class Meta:
            app_label = "test_app"

        field = fields.SchemaField(SampleTypedDict)

    data = {"stub_str": "abc", "stub_int": 2}
    obj = TypedDictModel(field=data)
    assert obj.field == data
