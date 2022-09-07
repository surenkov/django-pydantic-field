import typing as t
from datetime import date
from uuid import UUID

import pytest
import pydantic

from django_pydantic_field import base
from .conftest import InnerSchema, SampleDataclass


class SampleSchema(pydantic.BaseModel):
    __root__: InnerSchema


def test_schema_encoder():
    encoder = base.SchemaEncoder(schema=SampleSchema)
    existing_model_inst = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    assert encoder.encode(existing_model_inst) == expected_encoded


def test_schema_encoder_with_raw_dict():
    encoder = base.SchemaEncoder(schema=SampleSchema)
    existing_raw = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    assert encoder.encode(existing_raw) == expected_encoded


def test_schema_encoder_with_custom_config():
    encoder = base.SchemaEncoder(schema=SampleSchema, export={"exclude": {"__root__": {"stub_list"}}})
    existing_raw = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = '{"stub_str": "abc", "stub_int": 1}'
    assert encoder.encode(existing_raw) == expected_encoded


def test_schema_decoder():
    decoder = base.SchemaDecoder(schema=SampleSchema)
    existing_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    expected_decoded = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    assert decoder.decode(existing_encoded) == expected_decoded


def test_schema_decoder_with_custom_error_handler():
    existing_flawed_encoded = '{"stub_str": "abc", "stub_list": 1}'

    def custom_handler(obj, payload):
        schema, exc = payload
        assert schema is SampleSchema
        raise exc

    decoder = base.SchemaDecoder(schema=SampleSchema, error_handler=custom_handler)

    with pytest.raises(pydantic.ValidationError) as e:
        decoder.decode(existing_flawed_encoded)

    assert e.match(".*stub_list.*")


def test_schema_wrapper_transformers():
    wrapper = base.SchemaWrapper()
    existing_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    expected_decoded = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    parsed_wrapper = wrapper._wrap_schema(InnerSchema).parse_raw(existing_encoded)
    assert parsed_wrapper.__root__ == expected_decoded

    existing_encoded = '[{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}]'
    parsed_wrapper = wrapper._wrap_schema(t.List[InnerSchema]).parse_raw(existing_encoded)
    assert parsed_wrapper.__root__ == [expected_decoded]


@pytest.mark.parametrize("type_, encoded, decoded", [
    (InnerSchema, '{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}', InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])),
    (SampleDataclass, '{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}', SampleDataclass(stub_str="abc", stub_list=[date(2022, 7, 1)])),
    (list[InnerSchema], '[{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}]', [InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])]),
    (list[SampleDataclass], '[{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}]', [SampleDataclass(stub_str="abc", stub_list=[date(2022, 7, 1)])]), # type: ignore
    (list[int], '[1, 2, 3]', [1, 2, 3]),
    (t.List[int], '[1, 2, 3]', [1, 2, 3]),
    (dict[int, date], '{"1": "1970-01-01"}', {1: date(1970, 1, 1)}),
    (t.Mapping[int, date], '{"1": "1970-01-01"}', {1: date(1970, 1, 1)}),
    (set[UUID], '["ba6eb330-4f7f-11eb-a2fb-67c34e9ac07c"]', {UUID("ba6eb330-4f7f-11eb-a2fb-67c34e9ac07c")}),
    (t.Set[UUID], '["ba6eb330-4f7f-11eb-a2fb-67c34e9ac07c"]', {UUID("ba6eb330-4f7f-11eb-a2fb-67c34e9ac07c")}),
])
def test_concrete_types(type_, encoded, decoded):
    schema = base.SchemaWrapper()._wrap_schema(type_)
    encoder = base.SchemaEncoder(schema=schema)
    decoder = base.SchemaDecoder(schema=schema)

    existing_decoded = decoder.decode(encoded)
    assert existing_decoded == decoded

    existing_encoded = encoder.encode(decoded)
    assert decoder.decode(existing_encoded) == decoded
