import pytest
import typing as t
from datetime import date

from django.core.exceptions import FieldError

from tests.conftest import InnerSchema
from tests.test_app.models import SampleModel

fields = pytest.importorskip("django_pydantic_field.v1.fields")


def test_simple_model_field():
    sample_field = SampleModel._meta.get_field("sample_field")
    assert sample_field.schema == InnerSchema

    sample_list_field = SampleModel._meta.get_field("sample_list")
    assert sample_list_field.schema == t.List[InnerSchema]

    sample_seq_field = SampleModel._meta.get_field("sample_seq")
    assert sample_seq_field.schema == t.List[InnerSchema]

    existing_raw_field = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    existing_raw_list = [{"stub_str": "abc", "stub_list": []}]

    instance = SampleModel(sample_field=existing_raw_field, sample_list=existing_raw_list)

    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_list = [InnerSchema(stub_str="abc", stub_list=[])]

    assert instance.sample_field == expected_instance
    assert instance.sample_list == expected_list


def test_untyped_model_field_raises():
    with pytest.raises(FieldError):

        class UntypedModel(models.Model):
            sample_field = fields.SchemaField()

            class Meta:
                app_label = "test_app"
