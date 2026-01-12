import sys
from datetime import date

import pytest
from django.db import models

from django_pydantic_field.v1 import fields
from tests.conftest import InnerSchema
from tests.test_app.models import SampleModel

pytestmark = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="Pydantic V1 is incompatible with Python 3.14+",
)


def test_simple_model_field():
    sample_field = SampleModel._meta.get_field("sample_field")
    assert sample_field.adapter.prepared_schema == InnerSchema

    sample_list_field = SampleModel._meta.get_field("sample_list")
    assert sample_list_field.adapter.prepared_schema == list[InnerSchema]

    sample_seq_field = SampleModel._meta.get_field("sample_seq")
    assert sample_seq_field.adapter.prepared_schema == list[InnerSchema]

    existing_raw_field = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    existing_raw_list = [{"stub_str": "abc", "stub_list": []}]

    instance = SampleModel(sample_field=existing_raw_field, sample_list=existing_raw_list)

    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_list = [InnerSchema(stub_str="abc", stub_list=[])]

    assert instance.sample_field == expected_instance
    assert instance.sample_list == expected_list


def test_untyped_model_field_check_failed():
    class UntypedModel(models.Model):
        sample_field = fields.SchemaField()

        class Meta:
            app_label = "test_app"

    errors = UntypedModel._meta.get_field("sample_field").check()
    assert any(e.id == "pydantic.E001" for e in errors)
