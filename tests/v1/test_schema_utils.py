import typing as t
from datetime import date

import pydantic
import pytest

from tests.conftest import InnerSchema

schema_utils = pytest.importorskip("django_pydantic_field.v1.schema_utils")


class SampleSchema(pydantic.BaseModel):
    __root__: InnerSchema


def test_schema_wrapper_transformers():
    existing_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'
    expected_decoded = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])

    parsed_wrapper = schema_utils.prepare_schema(InnerSchema).parse_raw(existing_encoded)
    assert parsed_wrapper.__root__ == expected_decoded

    existing_encoded = '[{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}]'
    parsed_wrapper = schema_utils.prepare_schema(t.List[InnerSchema]).parse_raw(existing_encoded)
    assert parsed_wrapper.__root__ == [expected_decoded]


def test_schema_wrapper_config_inheritance():
    parsed_wrapper = schema_utils.prepare_schema(InnerSchema, config={"allow_mutation": False})
    assert not parsed_wrapper.Config.allow_mutation
    assert not parsed_wrapper.Config.frozen

    parsed_wrapper = schema_utils.prepare_schema(t.List[InnerSchema], config={"frozen": True})
    assert parsed_wrapper.Config.allow_mutation
    assert parsed_wrapper.Config.frozen


@pytest.mark.parametrize(
    "forward_ref, sample_data",
    [
        (t.ForwardRef("t.List[int]"), "[1, 2]"),
        (t.ForwardRef("InnerSchema"), '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'),
        (t.ForwardRef("PostponedSchema"), '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'),
    ],
)
def test_forward_refs_preparation(forward_ref, sample_data):
    schema = schema_utils.prepare_schema(forward_ref, owner=test_forward_refs_preparation)
    assert schema.parse_raw(sample_data).json() == sample_data


class PostponedSchema(pydantic.BaseModel):
    __root__: InnerSchema
