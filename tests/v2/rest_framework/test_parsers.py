import io
from datetime import date

import pytest

from tests.conftest import InnerSchema

rest_framework = pytest.importorskip("django_pydantic_field.v2.rest_framework")


@pytest.mark.parametrize(
    "schema_type, existing_encoded, expected_decoded",
    [
        (
            InnerSchema,
            '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}',
            InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        )
    ],
)
def test_schema_parser(schema_type, existing_encoded, expected_decoded):
    parser = rest_framework.SchemaParser[schema_type]()
    assert parser.parse(io.StringIO(existing_encoded)) == expected_decoded
