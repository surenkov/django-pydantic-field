from datetime import date

import pytest

from tests.conftest import InnerSchema

rest_framework = pytest.importorskip("django_pydantic_field.v2.rest_framework", exc_type=ImportError)


def test_schema_renderer():
    renderer = rest_framework.SchemaRenderer()
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = b'{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}'

    assert renderer.render(existing_instance) == expected_encoded


def test_typed_schema_renderer():
    renderer = rest_framework.SchemaRenderer[InnerSchema]()
    existing_data = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = b'{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}'

    assert renderer.render(existing_data) == expected_encoded
