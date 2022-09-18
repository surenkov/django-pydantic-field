import pytest

from django.core.exceptions import ValidationError
from django_pydantic_field.form import SchemaField

from .conftest import InnerSchema


def test_form_schema_field():
    field = SchemaField(InnerSchema)

    cleaned_data =  field.clean('{"stub_str": "abc", "stub_list": ["1970-01-01"]}')
    assert cleaned_data == InnerSchema.parse_obj({"stub_str": "abc", "stub_list": ["1970-01-01"]})

def test_empty_form_values():
    field = SchemaField(InnerSchema, required=False)
    assert field.clean("") is None
    assert field.clean(None) is None


def test_invalid_raises():
    field = SchemaField(InnerSchema)
    with pytest.raises(ValidationError) as e:
        field.clean("")

    assert e.match("This field is required")

    with pytest.raises(ValidationError) as e:
        field.clean('{"stub_list": "abc"}')

    assert e.match("stub_str")
    assert e.match("stub_list")
