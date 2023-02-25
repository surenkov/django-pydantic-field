import typing as t

import django
import pydantic
import pytest
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import Form, modelform_factory
from django_pydantic_field import fields, forms

from .conftest import InnerSchema


class SampleForwardRefFieldModel(models.Model):
    annotated_field: t.Optional["SampleSchema"] = fields.SchemaField(null=True)

    class Meta:
        app_label = "test_app"


class SampleForm(Form):
    field = forms.SchemaField(t.ForwardRef("SampleSchema"))


class SampleSchema(pydantic.BaseModel):
    field: int = 1


def test_form_schema_field():
    field = forms.SchemaField(InnerSchema)

    cleaned_data = field.clean('{"stub_str": "abc", "stub_list": ["1970-01-01"]}')
    assert cleaned_data == InnerSchema.parse_obj({"stub_str": "abc", "stub_list": ["1970-01-01"]})

def test_empty_form_values():
    field = forms.SchemaField(InnerSchema, required=False)
    assert field.clean("") is None
    assert field.clean(None) is None


def test_invalid_raises():
    field = forms.SchemaField(InnerSchema)
    with pytest.raises(ValidationError) as e:
        field.clean("")

    assert e.match("This field is required")

    with pytest.raises(ValidationError) as e:
        field.clean('{"stub_list": "abc"}')

    assert e.match("stub_str")
    assert e.match("stub_list")


@pytest.mark.xfail(
    django.VERSION[:2] < (4, 0),
    reason="Django < 4 has it's own feeling on bound fields resolution",
)
def test_forwardref_field():
    form = SampleForm(data={"field": '{"field": "2"}'})
    assert form.is_valid()


def test_model_formfield():
    field = fields.PydanticSchemaField(schema=InnerSchema)
    assert isinstance(field.formfield(), forms.SchemaField)


def test_forwardref_model_formfield():
    form_cls = modelform_factory(SampleForwardRefFieldModel, exclude=())
    form = form_cls(data={"annotated_field": '{"field": "2"}'})

    assert form.is_valid()
    cleaned_data = form.cleaned_data

    assert cleaned_data is not None
    assert cleaned_data["annotated_field"] == SampleSchema(field=2)


@pytest.mark.parametrize("export_kwargs", [
    {"include": {"stub_str", "stub_int"}},
    {"exclude": {"stub_list"}},
    {"exclude_unset": True},
    {"exclude_defaults": True},
    {"exclude_none": True},
    {"by_alias": True},
])
def test_form_field_export_kwargs(export_kwargs):
    field = forms.SchemaField(InnerSchema, required=False, **export_kwargs)
    value = InnerSchema.parse_obj({"stub_str": "abc", "stub_list": ["1970-01-01"]})
    assert field.prepare_value(value)
