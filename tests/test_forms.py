from __future__ import annotations

import collections
import enum
import json
import sys
import typing as ty
import uuid
from datetime import date, datetime

import django
import pydantic
import pytest
import typing_extensions as te
from django.core.exceptions import ValidationError
from django.forms import Form, modelform_factory
from django_jsonform.validators import JSONSchemaValidator
from django_jsonform.widgets import JSONFormWidget

from django_pydantic_field import fields, forms
from django_pydantic_field._internal._jsonform import coerce_jsonform_data, normalize_jsonform_schema
from django_pydantic_field.compat.pydantic import PYDANTIC_V2
from django_pydantic_field.v1 import fields as fields_v1
from django_pydantic_field.v1 import forms as forms_v1
from django_pydantic_field.v1.compat import pydantic_v1
from tests.conftest import InnerSchema, InnerSchemaV1
from tests.test_app.models import ExampleSchema, SampleForwardRefModel, SampleSchema

V1_SKIP = pytest.mark.skipif(
    sys.version_info >= (3, 14) or pydantic_v1 is None,
    reason="Pydantic V1 is incompatible with Python 3.14+",
)
V2_SKIP = pytest.mark.skipif(
    not PYDANTIC_V2,
    reason="Pydantic V2 is required",
)


class ColorEnum(str, enum.Enum):
    RED = "red"
    BLUE = "blue"


class PointNamedTuple(ty.NamedTuple):
    x: int
    y: str


class HomogeneousNamedTuple(ty.NamedTuple):
    a: int
    b: int


class EmptyNamedTuple(ty.NamedTuple):
    pass


UntypedNamedTuple = collections.namedtuple("UntypedNamedTuple", ["first", "second"])


# ============================================================================
# Pydantic v2 Schemas
# ============================================================================


class EmptyModel(pydantic.BaseModel):
    pass


class ModelWithTypeField(pydantic.BaseModel):
    type: str = "custom"
    properties: dict[str, str] = pydantic.Field(default_factory=dict)


class MappingContainerModel(pydantic.BaseModel):
    my_mapping: dict[str, str] = pydantic.Field(default_factory=dict)
    untyped_mapping: dict = pydantic.Field(default_factory=dict)
    optional_mapping: dict[str, int] | None = None
    list_of_mappings: list[dict[str, str]] = pydantic.Field(default_factory=list)
    nested_model_mapping: dict[str, InnerSchema] = pydantic.Field(default_factory=dict)


class OptionalInnerModel(pydantic.BaseModel):
    opt_nested_str: str | None = None
    opt_nested_date: date | None = None


class OptionalFieldsModel(pydantic.BaseModel):
    req_str: str
    opt_str: str | None = None
    opt_str_no_default: str | None
    opt_str_with_default: str | None = "preset"
    opt_str_empty_default: str | None = ""
    opt_int: int | None = None
    opt_bool: bool | None = None
    opt_date: date | None = None
    opt_datetime: datetime | None = None
    opt_uuid: uuid.UUID | None = None
    opt_enum: ColorEnum | None = None
    opt_enum_with_default: ColorEnum | None = ColorEnum.BLUE
    opt_literal: ty.Literal["a", "b"] | None = None
    opt_inner: InnerSchema | None = None
    inner_with_default: OptionalInnerModel = OptionalInnerModel(opt_nested_str="init")
    multi_union: str | int | None = None


class TupleContainerModel(pydantic.BaseModel):
    hetero_tuple: tuple[int, str]
    homo_tuple: tuple[int, int]
    single_tuple: tuple[int]
    variadic_tuple: tuple[int, ...]
    empty_tuple: tuple[()] = ()
    untyped_tuple: tuple = ()
    named_tuple: PointNamedTuple
    empty_named_tuple: EmptyNamedTuple = EmptyNamedTuple()
    untyped_named_tuple: UntypedNamedTuple


class ComposedIssuesModel(pydantic.BaseModel):
    opt_mapping_of_opt_dates: dict[str, date | None] | None = None
    opt_tuple_with_opt_date: tuple[date | None, str] | None = None
    mapping_of_tuples: dict[str, tuple[int, str | None]] = pydantic.Field(default_factory=dict)


class RecursiveNodeModel(pydantic.BaseModel):
    name: str
    opt_tag: str | None = None
    parent: RecursiveNodeModel | None = None
    children: list[RecursiveNodeModel] = pydantic.Field(default_factory=list)


if PYDANTIC_V2:
    RecursiveNodeModel.model_rebuild()

    class MutualRootA(pydantic.RootModel["MutualRootB | dict[str, str | None] | None"]):
        pass

    class MutualRootB(pydantic.RootModel["MutualRootA | int | None"]):
        pass

    MutualRootA.model_rebuild()
    MutualRootB.model_rebuild()
else:
    RecursiveNodeModel.update_forward_refs()
    MutualRootA = None
    MutualRootB = None


class UnionBranchA(pydantic.BaseModel):
    kind: ty.Literal["a"]
    opt_shared: str | None = None
    opt_a: date | None = None


class UnionBranchB(pydantic.BaseModel):
    kind: ty.Literal["b"]
    opt_shared: str | None = None
    opt_b: date | None = None


class DiscriminatedAndMultiUnionModel(pydantic.BaseModel):
    disc_union: UnionBranchA | UnionBranchB | None = pydantic.Field(
        default=None,
        discriminator="kind",
    )
    multi_union: UnionBranchA | UnionBranchB | None = None


class SampleForm(Form):
    field = forms.SchemaField(ty.ForwardRef("SampleSchema"))


class NoDefaultForm(Form):
    field = forms.SchemaField(schema=ExampleSchema)


# ============================================================================
# Pydantic v1 Schemas (Fallback to v2 stubs on Python 3.14+ for collection)
# ============================================================================

if pydantic_v1 is not None:

    class SampleSchemaV1(pydantic_v1.BaseModel):
        field: int = 1

    class ExampleSchemaV1(pydantic_v1.BaseModel):
        count: int

    class SampleFormV1(Form):
        field = forms_v1.SchemaField(ty.ForwardRef("SampleSchemaV1"))

    class NoDefaultFormV1(Form):
        field = forms_v1.SchemaField(schema=ExampleSchemaV1)

    class EmptyModelV1(pydantic_v1.BaseModel):
        pass

    class ModelWithTypeFieldV1(pydantic_v1.BaseModel):
        type: str = "custom"
        properties: dict[str, str] = pydantic_v1.Field(default_factory=dict)

    class MappingContainerModelV1(pydantic_v1.BaseModel):
        my_mapping: dict[str, str] = pydantic_v1.Field(default_factory=dict)
        untyped_mapping: dict = pydantic_v1.Field(default_factory=dict)
        optional_mapping: dict[str, int] | None = None
        list_of_mappings: list[dict[str, str]] = pydantic_v1.Field(default_factory=list)
        nested_model_mapping: dict[str, InnerSchemaV1] = pydantic_v1.Field(default_factory=dict)

    class OptionalInnerModelV1(pydantic_v1.BaseModel):
        opt_nested_str: str | None = None
        opt_nested_date: date | None = None

    class OptionalFieldsModelV1(pydantic_v1.BaseModel):
        req_str: str
        opt_str: str | None = None
        opt_str_no_default: str | None
        opt_str_with_default: str | None = "preset"
        opt_str_empty_default: str | None = ""
        opt_int: int | None = None
        opt_bool: bool | None = None
        opt_date: date | None = None
        opt_datetime: datetime | None = None
        opt_uuid: uuid.UUID | None = None
        opt_enum: ColorEnum | None = None
        opt_enum_with_default: ColorEnum | None = ColorEnum.BLUE
        opt_literal: ty.Literal["a", "b"] | None = None
        opt_inner: InnerSchemaV1 | None = None
        inner_with_default: OptionalInnerModelV1 = OptionalInnerModelV1(opt_nested_str="init")
        multi_union: str | int | None = None

    class TupleContainerModelV1(pydantic_v1.BaseModel):
        hetero_tuple: tuple[int, str]
        homo_tuple: tuple[int, int]
        single_tuple: tuple[int]
        variadic_tuple: tuple[int, ...]
        empty_tuple: tuple[()] = ()
        untyped_tuple: tuple = ()
        named_tuple: PointNamedTuple
        empty_named_tuple: EmptyNamedTuple = EmptyNamedTuple()
        untyped_named_tuple: UntypedNamedTuple

    class ComposedIssuesModelV1(pydantic_v1.BaseModel):
        opt_mapping_of_opt_dates: dict[str, date | None] | None = None
        opt_tuple_with_opt_date: tuple[date | None, str] | None = None
        mapping_of_tuples: dict[str, tuple[int, str | None]] = pydantic_v1.Field(default_factory=dict)

else:
    SampleSchemaV1 = SampleSchema
    ExampleSchemaV1 = ExampleSchema
    SampleFormV1 = SampleForm
    NoDefaultFormV1 = NoDefaultForm
    EmptyModelV1 = EmptyModel
    ModelWithTypeFieldV1 = ModelWithTypeField
    MappingContainerModelV1 = MappingContainerModel
    OptionalInnerModelV1 = OptionalInnerModel
    OptionalFieldsModelV1 = OptionalFieldsModel
    TupleContainerModelV1 = TupleContainerModel
    ComposedIssuesModelV1 = ComposedIssuesModel


# ============================================================================
# Core Form SchemaField Tests (Unified v1 & v2)
# ============================================================================


@pytest.mark.parametrize(
    "forms_mod, schema_cls, raw_data",
    [
        (forms, InnerSchema, '{"stub_str": "abc", "stub_list": ["1970-01-01"]}'),
        (forms, InnerSchema, b'{"stub_str": "abc", "stub_list": ["1970-01-01"]}'),
        (forms, InnerSchema, {"stub_str": "abc", "stub_list": ["1970-01-01"]}),
        (forms, InnerSchema, InnerSchema(stub_str="abc", stub_list=[date(1970, 1, 1)])),
        pytest.param(forms_v1, InnerSchemaV1, '{"stub_str": "abc", "stub_list": ["1970-01-01"]}', marks=V1_SKIP),
        pytest.param(forms_v1, InnerSchemaV1, b'{"stub_str": "abc", "stub_list": ["1970-01-01"]}', marks=V1_SKIP),
        pytest.param(forms_v1, InnerSchemaV1, {"stub_str": "abc", "stub_list": ["1970-01-01"]}, marks=V1_SKIP),
        pytest.param(
            forms_v1,
            InnerSchemaV1,
            InnerSchemaV1(stub_str="abc", stub_list=[date(1970, 1, 1)]),
            marks=V1_SKIP,
        ),
    ],
)
def test_form_schema_field(forms_mod, schema_cls, raw_data):
    field = forms_mod.SchemaField(schema_cls)
    cleaned_data = field.clean(raw_data)
    assert cleaned_data == schema_cls(stub_str="abc", stub_list=[date(1970, 1, 1)])


@pytest.mark.parametrize(
    "forms_mod, schema_cls",
    [
        (forms, InnerSchema),
        pytest.param(forms_v1, InnerSchemaV1, marks=V1_SKIP),
    ],
)
def test_empty_form_values(forms_mod, schema_cls):
    field = forms_mod.SchemaField(schema_cls, required=False)
    assert field.clean("") is None
    assert field.clean(None) is None


@pytest.mark.parametrize(
    "forms_mod, schema_cls, expected",
    [
        pytest.param(
            forms,
            InnerSchema,
            '{"stub_str":"abc","stub_int":1,"stub_list":["1970-01-01"]}',
            marks=V2_SKIP,
        ),
        pytest.param(
            forms_v1,
            InnerSchemaV1,
            '{"stub_str": "abc", "stub_int": 1, "stub_list": ["1970-01-01"]}',
            marks=V1_SKIP,
        ),
    ],
)
def test_prepare_value(forms_mod, schema_cls, expected):
    field = forms_mod.SchemaField(schema_cls, required=False)
    assert expected == field.prepare_value({"stub_str": "abc", "stub_list": ["1970-01-01"]})


@V1_SKIP
def test_prepare_value_export_params_v1():
    field = forms_v1.SchemaField(InnerSchemaV1, required=False, indent=2, sort_keys=True, separators=("", " > "))
    expected = """{
  "stub_int" > 1
  "stub_list" > [
    "1970-01-01"
  ]
  "stub_str" > "abc"
}"""
    assert expected == field.prepare_value({"stub_str": "abc", "stub_list": ["1970-01-01"]})


@V2_SKIP
@pytest.mark.parametrize(
    "value, expected",
    [
        ([], "[]"),
        ([42], "[42]"),
        ("[42]", "[42]"),
    ],
)
def test_root_value_passes(value, expected):
    RootModel = pydantic.RootModel[list[int]]
    field = forms.SchemaField(RootModel)
    assert field.prepare_value(value) == expected


@V2_SKIP
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
    RootModel = pydantic.RootModel[list[int]]
    field = forms.SchemaField(RootModel)
    assert field.has_changed(initial, value) is expected


@pytest.mark.parametrize(
    "forms_mod, schema_cls",
    [
        (forms, InnerSchema),
        pytest.param(forms_v1, InnerSchemaV1, marks=V1_SKIP),
    ],
)
def test_empty_required_raises(forms_mod, schema_cls):
    field = forms_mod.SchemaField(schema_cls)
    with pytest.raises(ValidationError) as e:
        field.clean("")

    assert e.match("This field is required")


@pytest.mark.parametrize(
    "forms_mod, schema_cls, is_v2",
    [
        pytest.param(forms, InnerSchema, True, marks=V2_SKIP),
        pytest.param(forms_v1, InnerSchemaV1, False, marks=V1_SKIP),
    ],
)
def test_invalid_schema_raises(forms_mod, schema_cls, is_v2):
    field = forms_mod.SchemaField(schema_cls)
    with pytest.raises(ValidationError) as e:
        field.clean('{"stub_list": "abc"}')

    assert e.match("Schema didn't match for")
    if is_v2:
        assert "stub_list" in e.value.params["detail"]  # type: ignore
        assert "stub_str" in e.value.params["detail"]  # type: ignore
    else:
        assert e.match("stub_str")
        assert e.match("stub_list")


@pytest.mark.parametrize(
    "forms_mod, schema_cls, is_v2",
    [
        pytest.param(forms, InnerSchema, True, marks=V2_SKIP),
        pytest.param(forms_v1, InnerSchemaV1, False, marks=V1_SKIP),
    ],
)
def test_invalid_json_raises(forms_mod, schema_cls, is_v2):
    field = forms_mod.SchemaField(schema_cls)
    with pytest.raises(ValidationError) as e:
        field.clean('{"stub_list": "abc}')

    assert e.match(r"['Schema didn't match for.*]")
    if is_v2:
        assert '"type":"json_invalid"' in e.value.params["json"]  # type: ignore
    else:
        assert e.match("type=value_error.jsondecode")


@pytest.mark.xfail(
    django.VERSION[:2] < (4, 0),
    reason="Django < 4 has it's own feeling on bound fields resolution",
)
@pytest.mark.parametrize(
    "form_cls",
    [
        SampleForm,
        pytest.param(SampleFormV1, marks=V1_SKIP),
    ],
)
def test_forwardref_field(form_cls):
    form = form_cls(data={"field": '{"field": "2"}'})
    assert form.is_valid()


@pytest.mark.parametrize(
    "fields_mod, forms_mod, schema_cls",
    [
        (fields, forms, InnerSchema),
        pytest.param(fields_v1, forms_v1, InnerSchemaV1, marks=V1_SKIP),
    ],
)
def test_model_formfield(fields_mod, forms_mod, schema_cls):
    field = fields_mod.PydanticSchemaField(schema=schema_cls)
    assert isinstance(field.formfield(), forms_mod.SchemaField)


def test_forwardref_model_formfield():
    form_cls = modelform_factory(SampleForwardRefModel, exclude=("field",))
    form = form_cls(data={"annotated_field": '{"field": "2"}'})

    assert form.is_valid(), form.errors
    cleaned_data = form.cleaned_data

    assert cleaned_data is not None
    assert cleaned_data["annotated_field"] == SampleSchema(field=2)


@pytest.mark.parametrize(
    "forms_mod, schema_cls",
    [
        (forms, InnerSchema),
        pytest.param(forms_v1, InnerSchemaV1, marks=V1_SKIP),
    ],
)
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
def test_form_field_export_kwargs(forms_mod, schema_cls, export_kwargs):
    field = forms_mod.SchemaField(schema_cls, required=False, **export_kwargs)
    value = schema_cls(stub_str="abc", stub_list=[date(1970, 1, 1)])
    assert field.prepare_value(value)


@V1_SKIP
@pytest.mark.parametrize(
    "export_kwargs",
    [
        {"indent": 4},
        {"separators": (",", ": ")},
        {"sort_keys": True},
    ],
)
def test_form_field_export_kwargs_v1_json_dumps(export_kwargs):
    field = forms_v1.SchemaField(InnerSchemaV1, required=False, **export_kwargs)
    value = InnerSchemaV1(stub_str="abc", stub_list=[date(1970, 1, 1)])
    assert field.prepare_value(value)


@V2_SKIP
def test_annotated_acceptance():
    field = forms.SchemaField(te.Annotated[InnerSchema, pydantic.Field(title="Inner Schema")])
    value = InnerSchema.model_validate({"stub_str": "abc", "stub_list": ["1970-01-01"]})
    assert field.prepare_value(value)


@pytest.mark.parametrize(
    "form_cls",
    [
        NoDefaultForm,
        pytest.param(NoDefaultFormV1, marks=V1_SKIP),
    ],
)
def test_form_render_without_default(form_cls):
    form = form_cls()
    form.as_p()


# ============================================================================
# Shared Schema Invariant Helper
# ============================================================================


def _assert_valid_jsonform_schema_node(node: ty.Any) -> None:
    if isinstance(node, list):
        for el in node:
            _assert_valid_jsonform_schema_node(el)
        return
    if not isinstance(node, dict):
        return

    if node.get("type") in ("object", "dict"):
        assert any(k in node for k in ("properties", "keys", "oneOf", "anyOf", "allOf")), (
            f"Object schema node missing properties/keys/combinator: {node}"
        )

    if node.get("type") == "array":
        assert "prefixItems" not in node
        assert "items" in node and isinstance(node["items"], dict), f"Array schema node must have dict 'items': {node}"
        items = node["items"]
        assert any(k in items for k in ("type", "$ref", "oneOf", "anyOf", "allOf", "const")), (
            f"Array 'items' missing type/combinator: {items}"
        )

    for key in ("properties", "keys", "$defs", "definitions"):
        if isinstance(node.get(key), dict):
            for v in node[key].values():
                _assert_valid_jsonform_schema_node(v)

    for key in ("anyOf", "oneOf", "allOf"):
        if isinstance(node.get(key), list):
            for sub in node[key]:
                assert sub != {"type": "null"}, f"Unwrapped null branch found in {key}: {node}"
                _assert_valid_jsonform_schema_node(sub)

    if isinstance(node.get("items"), dict):
        _assert_valid_jsonform_schema_node(node["items"])
    if isinstance(node.get("additionalProperties"), dict):
        _assert_valid_jsonform_schema_node(node["additionalProperties"])


# ============================================================================
# Issue #64: Objects with only additionalProperties in django-jsonform
# ============================================================================


@pytest.mark.parametrize(
    "forms_mod, schema_tp, sample_data",
    [
        (forms, dict[str, str], {"k1": "v1"}),
        (forms, dict[str, ty.Any], {"k1": "v1"}),
        (forms, dict, {"k1": "v1"}),
        (forms, dict[str, dict[str, int]], {"outer": {"inner": 1}}),
        (forms, dict[str, InnerSchema], {"m": {"stub_str": "a", "stub_int": 1, "stub_list": ["2020-01-01"]}}),
        (
            forms,
            MappingContainerModel,
            {
                "my_mapping": {"a": "b"},
                "untyped_mapping": {"x": "y"},
                "optional_mapping": {"k": 1},
                "list_of_mappings": [{"c": "d"}],
                "nested_model_mapping": {},
            },
        ),
        (forms, ModelWithTypeField, {"type": "hello", "properties": {"k": "v"}}),
        pytest.param(forms_v1, dict[str, str], {"k1": "v1"}, marks=V1_SKIP),
        pytest.param(forms_v1, dict[str, ty.Any], {"k1": "v1"}, marks=V1_SKIP),
        pytest.param(forms_v1, dict, {"k1": "v1"}, marks=V1_SKIP),
        pytest.param(forms_v1, dict[str, dict[str, int]], {"outer": {"inner": 1}}, marks=V1_SKIP),
        pytest.param(
            forms_v1,
            dict[str, InnerSchemaV1],
            {"m": {"stub_str": "a", "stub_int": 1, "stub_list": ["2020-01-01"]}},
            marks=V1_SKIP,
        ),
        pytest.param(
            forms_v1,
            MappingContainerModelV1,
            {
                "my_mapping": {"a": "b"},
                "untyped_mapping": {"x": "y"},
                "optional_mapping": {"k": 1},
                "list_of_mappings": [{"c": "d"}],
                "nested_model_mapping": {},
            },
            marks=V1_SKIP,
        ),
        pytest.param(forms_v1, ModelWithTypeFieldV1, {"type": "hello", "properties": {"k": "v"}}, marks=V1_SKIP),
    ],
)
def test_issue_64_jsonform_additional_properties(forms_mod, schema_tp, sample_data):
    widget = forms_mod.JSONFormSchemaWidget(schema_tp)
    assert "$ref" not in widget.schema
    _assert_valid_jsonform_schema_node(widget.schema)

    rendered = widget.render("field", json.dumps(sample_data))
    assert "data-django-jsonform" in rendered

    validator = JSONSchemaValidator(widget.schema)
    validator(sample_data)

    field_with_base_widget = forms_mod.SchemaField(schema_tp, widget=JSONFormWidget)
    _assert_valid_jsonform_schema_node(field_with_base_widget.widget.schema)


@pytest.mark.parametrize(
    "forms_mod, empty_cls, type_field_cls",
    [
        (forms, EmptyModel, ModelWithTypeField),
        pytest.param(forms_v1, EmptyModelV1, ModelWithTypeFieldV1, marks=V1_SKIP),
    ],
)
def test_issue_64_empty_model_and_type_field_safety(forms_mod, empty_cls, type_field_cls):
    empty_widget = forms_mod.JSONFormSchemaWidget(empty_cls)
    assert empty_widget.schema.get("properties") == {}
    assert "additionalProperties" not in empty_widget.schema

    dict_widget = forms_mod.JSONFormSchemaWidget(dict)
    assert dict_widget.schema.get("properties") == {}
    assert dict_widget.schema.get("additionalProperties") is True

    type_field_widget = forms_mod.JSONFormSchemaWidget(type_field_cls)
    assert type_field_widget.schema["properties"]["type"]["type"] == "string"
    assert "properties" not in type_field_widget.schema["properties"]["type"]
    assert type_field_widget.schema["properties"]["properties"]["properties"] == {}


# ============================================================================
# Issue #65: Optional[] UX & Empty String ("") -> None Coercion
# ============================================================================


@pytest.mark.parametrize(
    "forms_mod, model_cls, is_v2",
    [
        pytest.param(forms, OptionalFieldsModel, True, marks=V2_SKIP),
        pytest.param(forms_v1, OptionalFieldsModelV1, False, marks=V1_SKIP),
    ],
)
def test_issue_65_jsonform_optional_schema_normalization(forms_mod, model_cls, is_v2):
    widget = forms_mod.JSONFormSchemaWidget(model_cls)
    schema = widget.schema
    _assert_valid_jsonform_schema_node(schema)

    props = schema["properties"]
    assert props["opt_str"]["type"] == "string"
    assert "anyOf" not in props["opt_str"]
    assert "default" not in props["opt_str"]

    assert props["opt_str_no_default"]["type"] == "string"
    assert "anyOf" not in props["opt_str_no_default"]
    assert schema.get("required") == ["req_str"]

    assert props["opt_str_with_default"]["default"] == "preset"
    assert props["opt_str_empty_default"]["default"] == ""

    assert "allOf" not in props["opt_enum_with_default"]
    assert "allOf" not in props["inner_with_default"]
    assert "anyOf" not in props["opt_inner"]

    if is_v2:
        multi_branches = props["multi_union"]["anyOf"]
        assert len(multi_branches) == 2
        assert {"type": "null"} not in multi_branches
        assert all("title" in b for b in multi_branches)


@pytest.mark.parametrize("use_base_widget", [False, True])
@pytest.mark.parametrize(
    "forms_mod, model_cls, is_v2",
    [
        pytest.param(forms, OptionalFieldsModel, True, marks=V2_SKIP),
        pytest.param(forms_v1, OptionalFieldsModelV1, False, marks=V1_SKIP),
    ],
)
def test_issue_65_jsonform_optional_empty_string_roundtrip(forms_mod, model_cls, is_v2, use_base_widget):
    widget_cls = JSONFormWidget if use_base_widget else forms_mod.JSONFormSchemaWidget

    class OptionalForm(Form):
        data = forms_mod.SchemaField(model_cls, widget=widget_cls)

    field_widget = OptionalForm.base_fields["data"].widget
    _assert_valid_jsonform_schema_node(field_widget.schema)

    raw_payload = json.dumps(
        {
            "req_str": "",
            "opt_str": "",
            "opt_str_no_default": "",
            "opt_str_with_default": "",
            "opt_str_empty_default": "",
            "opt_int": None,
            "opt_bool": None,
            "opt_date": "",
            "opt_datetime": "",
            "opt_uuid": "",
            "opt_enum": "",
            "opt_enum_with_default": "blue",
            "opt_literal": "",
            "opt_inner": None,
            "inner_with_default": {"opt_nested_str": "", "opt_nested_date": ""},
            "multi_union": "",
        }
    )
    form = OptionalForm(data={"data": raw_payload})
    assert form.is_valid(), form.errors
    cleaned = form.cleaned_data["data"]
    assert cleaned.req_str == ""
    assert cleaned.opt_str is None
    assert cleaned.opt_str_no_default is None
    assert cleaned.opt_str_with_default is (None if is_v2 else "")
    assert cleaned.opt_str_empty_default == ""
    assert cleaned.opt_date is None
    assert cleaned.opt_datetime is None
    assert cleaned.opt_uuid is None
    assert cleaned.opt_enum is None
    assert cleaned.opt_enum_with_default == ColorEnum.BLUE
    assert cleaned.opt_literal is None
    assert cleaned.opt_inner is None
    assert cleaned.inner_with_default.opt_nested_str is None
    assert cleaned.inner_with_default.opt_nested_date is None
    assert cleaned.multi_union is None

    bound_val = form["data"].value()
    assert bound_val is not None


# ============================================================================
# Issue #66: Tuple[] and NamedTuple Schemas in django-jsonform
# ============================================================================


@pytest.mark.parametrize(
    "forms_mod, container_cls",
    [
        (forms, TupleContainerModel),
        pytest.param(forms_v1, TupleContainerModelV1, marks=V1_SKIP),
    ],
)
@pytest.mark.parametrize(
    "schema_tp, sample_json, expected_python",
    [
        (tuple[int, str], '[1, "hello"]', (1, "hello")),
        (tuple[int, int], "[10, 20]", (10, 20)),
        (tuple[int], "[42]", (42,)),
        (tuple[int, ...], "[1, 2, 3]", (1, 2, 3)),
        (tuple[()], "[]", ()),
        (tuple, '["a", "b"]', ("a", "b")),
        (PointNamedTuple, '[5, "p"]', PointNamedTuple(5, "p")),
        (HomogeneousNamedTuple, "[3, 4]", HomogeneousNamedTuple(3, 4)),
        (EmptyNamedTuple, "[]", EmptyNamedTuple()),
        (UntypedNamedTuple, '["x", "y"]', UntypedNamedTuple("x", "y")),
        ("container", None, None),
    ],
)
def test_issue_66_jsonform_tuples_and_namedtuples(
    forms_mod,
    container_cls,
    schema_tp,
    sample_json,
    expected_python,
):
    if schema_tp == "container":
        schema_tp = container_cls
        sample_json = json.dumps(
            {
                "hetero_tuple": [1, "a"],
                "homo_tuple": [2, 3],
                "single_tuple": [4],
                "variadic_tuple": [5, 6],
                "empty_tuple": [],
                "untyped_tuple": ["z"],
                "named_tuple": [7, "b"],
                "empty_named_tuple": [],
                "untyped_named_tuple": ["u", "v"],
            }
        )
        expected_python = container_cls(
            hetero_tuple=(1, "a"),
            homo_tuple=(2, 3),
            single_tuple=(4,),
            variadic_tuple=(5, 6),
            empty_tuple=(),
            untyped_tuple=("z",),
            named_tuple=PointNamedTuple(7, "b"),
            empty_named_tuple=EmptyNamedTuple(),
            untyped_named_tuple=UntypedNamedTuple("u", "v"),
        )

    widget = forms_mod.JSONFormSchemaWidget(schema_tp)
    _assert_valid_jsonform_schema_node(widget.schema)

    validator = JSONSchemaValidator(widget.schema)
    validator(json.loads(sample_json))

    class TupleForm(Form):
        field = forms_mod.SchemaField(schema_tp, widget=forms_mod.JSONFormSchemaWidget, required=False)

    form = TupleForm(data={"field": sample_json})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["field"] == expected_python


# ============================================================================
# Cross-Issue Composed, Recursive/Cyclic, and Union Coercion Tests
# ============================================================================


@pytest.mark.parametrize(
    "forms_mod, composed_cls, is_v2",
    [
        pytest.param(forms, ComposedIssuesModel, True, marks=V2_SKIP),
        pytest.param(forms_v1, ComposedIssuesModelV1, False, marks=V1_SKIP),
    ],
)
def test_composed_issues_64_65_66_roundtrip(forms_mod, composed_cls, is_v2):
    widget = forms_mod.JSONFormSchemaWidget(composed_cls)
    _assert_valid_jsonform_schema_node(widget.schema)

    class ComposedForm(Form):
        field = forms_mod.SchemaField(composed_cls, widget=forms_mod.JSONFormSchemaWidget)

    payload = json.dumps(
        {
            "opt_mapping_of_opt_dates": {"d1": "", "d2": "2025-05-01"},
            "opt_tuple_with_opt_date": ["", "label"],
            "mapping_of_tuples": {"k1": [10, ""], "k2": [20, "text"]},
        }
    )
    form = ComposedForm(data={"field": payload})
    assert form.is_valid(), form.errors
    cleaned = form.cleaned_data["field"]
    assert cleaned.opt_mapping_of_opt_dates == {"d1": None, "d2": date(2025, 5, 1)}
    assert cleaned.opt_tuple_with_opt_date == (None, "label")
    assert cleaned.mapping_of_tuples == {"k1": (10, None if is_v2 else ""), "k2": (20, "text")}


def test_recursive_and_cyclic_ref_schemas():
    widget = forms.JSONFormSchemaWidget(RecursiveNodeModel)
    _assert_valid_jsonform_schema_node(widget.schema)

    class RecursiveForm(Form):
        node = forms.SchemaField(RecursiveNodeModel, widget=forms.JSONFormSchemaWidget)

    payload = json.dumps(
        {
            "name": "root",
            "opt_tag": "",
            "parent": {"name": "grandparent", "opt_tag": "", "parent": None, "children": []},
            "children": [{"name": "child", "opt_tag": "", "parent": None, "children": []}],
        }
    )
    form = RecursiveForm(data={"node": payload})
    assert form.is_valid(), form.errors
    cleaned: RecursiveNodeModel = form.cleaned_data["node"]
    assert cleaned.opt_tag is None
    assert cleaned.parent is not None and cleaned.parent.opt_tag is None
    assert cleaned.children[0].opt_tag is None

    if PYDANTIC_V2:
        # Mutual cyclic RootModels should not hit RecursionError during normalization or coercion
        mutual_widget = forms.JSONFormSchemaWidget(MutualRootA)
        _assert_valid_jsonform_schema_node(mutual_widget.schema)
        mutual_schema = forms.SchemaField(MutualRootA).adapter.json_schema()
        assert json.loads(coerce_jsonform_data('{"k": ""}', mutual_schema)) == {"k": None}

    # Direct cyclic $ref guard in synthetic schema
    cyclic_schema = {
        "$defs": {"A": {"$ref": "#/$defs/B"}, "B": {"$ref": "#/$defs/A"}},
        "properties": {"a": {"$ref": "#/$defs/A"}},
        "required": ["a"],
        "type": "object",
    }
    norm_cyclic = normalize_jsonform_schema(cyclic_schema)
    assert norm_cyclic["required"] == ["a"]
    assert coerce_jsonform_data('{"a": ""}', cyclic_schema) == '{"a": ""}'


def test_discriminated_and_multi_branch_union_coercion():
    widget = forms.JSONFormSchemaWidget(DiscriminatedAndMultiUnionModel)
    _assert_valid_jsonform_schema_node(widget.schema)

    class UnionForm(Form):
        field = forms.SchemaField(DiscriminatedAndMultiUnionModel, widget=forms.JSONFormSchemaWidget)

    payload = json.dumps(
        {
            "disc_union": {"kind": "b", "opt_shared": "", "opt_b": ""},
            "multi_union": {"kind": "b", "opt_shared": "", "opt_b": ""},
        }
    )
    form = UnionForm(data={"field": payload})
    assert form.is_valid(), form.errors
    cleaned: DiscriminatedAndMultiUnionModel = form.cleaned_data["field"]
    assert isinstance(cleaned.disc_union, UnionBranchB)
    assert cleaned.disc_union.opt_shared is None
    assert cleaned.disc_union.opt_b is None
    assert isinstance(cleaned.multi_union, UnionBranchB)
    assert cleaned.multi_union.opt_shared is None
    assert cleaned.multi_union.opt_b is None
