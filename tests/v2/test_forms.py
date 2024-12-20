import typing as ty
from datetime import date

import django
import pydantic
import pytest
import typing_extensions as te
from django.core.exceptions import ValidationError
from django.forms import Form, modelform_factory

from tests.conftest import InnerSchema
from tests.test_app.models import SampleForwardRefModel, SampleSchema, ExampleSchema

fields = pytest.importorskip("django_pydantic_field.v2.fields")
forms = pytest.importorskip("django_pydantic_field.v2.forms")


class SampleForm(Form):
    field = forms.SchemaField(ty.ForwardRef("SampleSchema"))


class NoDefaultForm(Form):
    field = forms.SchemaField(schema=ExampleSchema)


@pytest.mark.parametrize(
    "raw_data, clean_data",
    [
        ('{"stub_str": "abc", "stub_list": ["1970-01-01"]}', {"stub_str": "abc", "stub_list": ["1970-01-01"]}),
        (b'{"stub_str": "abc", "stub_list": ["1970-01-01"]}', {"stub_str": "abc", "stub_list": ["1970-01-01"]}),
        ({"stub_str": "abc", "stub_list": ["1970-01-01"]}, {"stub_str": "abc", "stub_list": ["1970-01-01"]}),
        (InnerSchema(stub_str="abc", stub_list=[date(1970, 1, 1)]), {"stub_str": "abc", "stub_list": ["1970-01-01"]}),
    ],
)
def test_form_schema_field(raw_data, clean_data):
    field = forms.SchemaField(InnerSchema)

    cleaned_data = field.clean(raw_data)
    assert cleaned_data == InnerSchema.model_validate(clean_data)


def test_empty_form_values():
    field = forms.SchemaField(InnerSchema, required=False)
    assert field.clean("") is None
    assert field.clean(None) is None


def test_prepare_value():
    field = forms.SchemaField(InnerSchema, required=False)
    expected = '{"stub_str":"abc","stub_int":1,"stub_list":["1970-01-01"]}'
    assert expected == field.prepare_value({"stub_str": "abc", "stub_list": ["1970-01-01"]})


@pytest.mark.parametrize(
    "value, expected",
    [
        ([], "[]"),
        ([42], "[42]"),
        ("[42]", "[42]"),
    ],
)
def test_root_value_passes(value, expected):
    RootModel = pydantic.RootModel[ty.List[int]]
    field = forms.SchemaField(RootModel)
    assert field.prepare_value(value) == expected


@pytest.mark.parametrize(
    "value, initial, expected",
    [
        ("[]", "[]", False),
        ([], [], False),
        ([], [42], True),
        ("[]", [], False),
        ("[42]", [], True),
        ([42], "[42]", False),
        ("[42]", "[42]", False),
        ("[42]", "[41]", True),
    ],
)
def test_root_value_has_changed(value, initial, expected):
    RootModel = pydantic.RootModel[ty.List[int]]
    field = forms.SchemaField(RootModel)
    assert field.has_changed(initial, value) is expected


def test_empty_required_raises():
    field = forms.SchemaField(InnerSchema)
    with pytest.raises(ValidationError) as e:
        field.clean("")

    assert e.match("This field is required")


def test_invalid_schema_raises():
    field = forms.SchemaField(InnerSchema)
    with pytest.raises(ValidationError) as e:
        field.clean('{"stub_list": "abc"}')

    assert e.match("Schema didn't match for")
    assert "stub_list" in e.value.params["detail"]  # type: ignore
    assert "stub_str" in e.value.params["detail"]  # type: ignore


def test_invalid_json_raises():
    field = forms.SchemaField(InnerSchema)
    with pytest.raises(ValidationError) as e:
        field.clean('{"stub_list": "abc}')

    assert e.match("Schema didn't match for")
    assert '"type":"json_invalid"' in e.value.params["detail"]  # type: ignore


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
    form_cls = modelform_factory(SampleForwardRefModel, exclude=("field",))
    form = form_cls(data={"annotated_field": '{"field": "2"}'})

    assert form.is_valid(), form.errors
    cleaned_data = form.cleaned_data

    assert cleaned_data is not None
    assert cleaned_data["annotated_field"] == SampleSchema(field=2)


@pytest.mark.parametrize(
    "export_kwargs",
    [
        {"include": {"stub_str", "stub_int"}},
        {"exclude": {"stub_list"}},
        {"exclude_unset": True},
        {"exclude_defaults": True},
        {"exclude_none": True},
        {"by_alias": True},
    ],
)
def test_form_field_export_kwargs(export_kwargs):
    field = forms.SchemaField(InnerSchema, required=False, **export_kwargs)
    value = InnerSchema.model_validate({"stub_str": "abc", "stub_list": ["1970-01-01"]})
    assert field.prepare_value(value)


def test_annotated_acceptance():
    field = forms.SchemaField(te.Annotated[InnerSchema, pydantic.Field(title="Inner Schema")])
    value = InnerSchema.model_validate({"stub_str": "abc", "stub_list": ["1970-01-01"]})
    assert field.prepare_value(value)


def test_form_render_without_default():
    form = NoDefaultForm()
    form.as_p()
