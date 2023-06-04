import sys
import typing as ty
from datetime import date
from uuid import UUID

import pydantic
import pytest

from django_pydantic_field.serialization import SchemaDecoder, SchemaEncoder
from django_pydantic_field.type_utils import type_adapter

from .conftest import InnerSchema, SampleDataclass

adapter = pydantic.TypeAdapter(InnerSchema)


def test_schema_encoder():
    encoder = SchemaEncoder(adapter=adapter)
    existing_model_inst = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = '{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}'
    assert encoder.encode(existing_model_inst) == expected_encoded


def test_schema_encoder_with_raw_dict():
    encoder = SchemaEncoder(adapter=adapter)
    existing_raw = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = '{"stub_str":"abc","stub_list":["2022-07-01"]}'
    assert encoder.encode(existing_raw) == expected_encoded


def test_schema_encoder_with_custom_config():
    encoder = SchemaEncoder(adapter=adapter, export_params={"exclude": {"stub_list"}})
    existing_raw = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = '{"stub_str":"abc"}'
    assert encoder.encode(existing_raw) == expected_encoded


def test_schema_decoder():
    decoder = SchemaDecoder(adapter=adapter)
    existing_encoded = '{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}'
    expected_decoded = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    assert decoder.decode(existing_encoded) == expected_decoded


def test_schema_decoder_error():
    existing_flawed_encoded = '{"stub_str":"abc","stub_list":1}'

    decoder = SchemaDecoder(adapter=adapter)

    with pytest.raises(pydantic.ValidationError) as e:
        decoder.decode(existing_flawed_encoded)

    assert e.match(".*stub_list.*")


def test_schema_wrapper_transformers():
    existing_encoded = '{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}'
    expected_decoded = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    parsed_value = type_adapter(InnerSchema).validate_json(existing_encoded)
    assert parsed_value == expected_decoded

    existing_encoded = '[{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}]'
    parsed_value = type_adapter(ty.List[InnerSchema]).validate_json(existing_encoded)
    assert parsed_value == [expected_decoded]


class test_schema_wrapper_config_inheritance:
    parsed_wrapper = type_adapter(InnerSchema, config={"allow_mutation": False})
    parsed_wrapper = type_adapter(ty.List[InnerSchema], config={"frozen": True})


@pytest.mark.parametrize(
    "type_, encoded, decoded",
    [
        (
            InnerSchema,
            '{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}',
            InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        ),
        (
            SampleDataclass,
            '{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}',
            SampleDataclass(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        ),
        (ty.List[int], "[1, 2, 3]", [1, 2, 3]),
        (ty.Mapping[int, date], '{"1": "1970-01-01"}', {1: date(1970, 1, 1)}),
        (ty.Set[UUID], '["ba6eb330-4f7f-11eb-a2fb-67c34e9ac07c"]', {UUID("ba6eb330-4f7f-11eb-a2fb-67c34e9ac07c")}),
    ],
)
def test_concrete_types(type_, encoded, decoded):
    adapter = type_adapter(type_)
    encoder = SchemaEncoder(adapter=adapter)
    decoder = SchemaDecoder(adapter=adapter)

    existing_decoded = decoder.decode(encoded)
    assert existing_decoded == decoded

    existing_encoded = encoder.encode(decoded)
    assert decoder.decode(existing_encoded) == decoded


@pytest.mark.skipif(sys.version_info < (3, 9), reason="Should test against builtin generic types")
@pytest.mark.parametrize(
    "type_factory, encoded, decoded",
    [
        (
            lambda: list[InnerSchema],
            '[{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}]',
            [InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])],
        ),
        (lambda: list[SampleDataclass], '[{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}]', [SampleDataclass(stub_str="abc", stub_list=[date(2022, 7, 1)])]),  # type: ignore
        (lambda: list[int], "[1, 2, 3]", [1, 2, 3]),
        (lambda: dict[int, date], '{"1": "1970-01-01"}', {1: date(1970, 1, 1)}),
        (lambda: set[UUID], '["ba6eb330-4f7f-11eb-a2fb-67c34e9ac07c"]', {UUID("ba6eb330-4f7f-11eb-a2fb-67c34e9ac07c")}),
    ],
)
def test_concrete_raw_types(type_factory, encoded, decoded):
    type_ = type_factory()

    adapter = type_adapter(type_)
    encoder = SchemaEncoder(adapter=adapter)
    decoder = SchemaDecoder(adapter=adapter)

    existing_decoded = decoder.decode(encoded)
    assert existing_decoded == decoded

    existing_encoded = encoder.encode(decoded)
    assert decoder.decode(existing_encoded) == decoded


@pytest.mark.parametrize(
    "forward_ref, sample_data",
    [
        (ty.ForwardRef("ty.List[int]"), b"[1,2]"),
        (ty.ForwardRef("InnerSchema"), b'{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}'),
        (ty.ForwardRef("PostponedSchema"), b'{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}'),
    ],
)
def test_forward_refs_preparation(forward_ref, sample_data):
    adapter = type_adapter(forward_ref)
    assert adapter.dump_json(adapter.validate_json(sample_data)) == sample_data


PostponedSchema = pydantic.RootModel[InnerSchema]
