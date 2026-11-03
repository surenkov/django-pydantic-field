import json
import sys
import typing as ty
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import ExpressionWrapper, F, OuterRef, Subquery, Value
from django.db.models.expressions import RawSQL
from django.db.models.fields.json import KeyTransform
from django.db.models.functions import Cast, JSONObject
from django.db.models.signals import pre_delete
from django.test.utils import isolate_apps

from django_pydantic_field import SchemaField, fields
from django_pydantic_field.v1 import fields as fields_v1
from tests.conftest import InnerSchema, InnerSchemaV1
from tests.test_app.models import SampleModel, SampleModelV1

pytestmark = [
    pytest.mark.usefixtures("available_database_backends"),
    pytest.mark.django_db(databases="__all__"),
]

V1_SKIP = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="Pydantic V1 is incompatible with Python 3.14+",
)


FIELD_SCHEMA_PARAMS = pytest.mark.parametrize(
    "field_cls, schema_cls",
    [
        (fields.SchemaField, InnerSchema),
        pytest.param(fields_v1.SchemaField, InnerSchemaV1, marks=V1_SKIP),
    ],
)

QUERY_ANNOTATION_PARAMS = pytest.mark.parametrize(
    "model_cls, field_cls, schema_cls",
    [
        (SampleModel, fields.SchemaField, InnerSchema),
        pytest.param(SampleModelV1, fields_v1.SchemaField, InnerSchemaV1, marks=V1_SKIP),
    ],
)


def _insert_raw_sample_row(
    model_cls: type[models.Model],
    sample_field_data: ty.Any,
    sample_list_data: ty.Any = None,
) -> int:
    field = model_cls._meta.get_field("sample_field")
    list_field = model_cls._meta.get_field("sample_list")
    original_errors = field.errors
    original_list_errors = list_field.errors
    field.errors = "ignore"
    list_field.errors = "ignore"
    try:
        instance = model_cls.objects.create(
            sample_field=sample_field_data,
            sample_list=sample_list_data if sample_list_data is not None else [],
            sample_seq=[],
        )
        return instance.pk
    finally:
        field.errors = original_errors
        list_field.errors = original_list_errors


def _assert_annotated_queryset(qs: models.QuerySet, expected: dict[str, ty.Any]) -> None:
    obj = qs.get()
    for name, expected_val in expected.items():
        assert getattr(obj, name) == expected_val

    assert qs.values(*expected.keys()).get() == expected
    for name, expected_val in expected.items():
        assert qs.values_list(name, flat=True).get() == expected_val


# ============================================================================
# 1. Configuration, Deconstruction & System Checks
# ============================================================================


def test_invalid_error_mode_raises_value_error():
    with pytest.raises(ValueError, match="Invalid error handling mode"):
        SchemaField(InnerSchema, errors="invalid_mode")  # type: ignore[arg-type]


def test_deconstruct_error_modes():
    default_field = SchemaField(InnerSchema)
    _, _, _, kwargs_default = default_field.deconstruct()
    assert "errors" not in kwargs_default

    raise_field = SchemaField(InnerSchema, errors="raise")
    _, _, _, kwargs_raise = raise_field.deconstruct()
    assert "errors" not in kwargs_raise

    ignore_field = SchemaField(InnerSchema, errors="ignore")
    _, _, _, kwargs_ignore = ignore_field.deconstruct()
    assert kwargs_ignore.get("errors") == "ignore"

    coerce_field = SchemaField(InnerSchema, errors="coerce", null=True)
    _, _, _, kwargs_coerce = coerce_field.deconstruct()
    assert kwargs_coerce.get("errors") == "coerce"


@isolate_apps("tests.test_app")
def test_system_check_w004_on_coerce_without_fallback():
    class InvalidCoerceModel(models.Model):
        field: InnerSchema = SchemaField(errors="coerce")

        class Meta:
            app_label = "test_app"

    warnings = InvalidCoerceModel._meta.get_field("field").check()
    assert any(w.id == "pydantic.W004" for w in warnings)


@isolate_apps("tests.test_app")
def test_system_check_no_w004_when_nullable_or_default():
    class ValidCoerceModel(models.Model):
        nullable_field: InnerSchema | None = SchemaField(null=True, errors="coerce")
        default_field: InnerSchema = SchemaField(
            default=lambda: InnerSchema(stub_str="default", stub_list=[]),
            errors="coerce",
        )

        class Meta:
            app_label = "test_app"

    assert not any(w.id == "pydantic.W004" for w in ValidCoerceModel._meta.get_field("nullable_field").check())
    assert not any(w.id == "pydantic.W004" for w in ValidCoerceModel._meta.get_field("default_field").check())


# ============================================================================
# 2. errors="raise" (Default Behavior & Issue #80)
# ============================================================================


@FIELD_SCHEMA_PARAMS
def test_errors_raise_to_python_and_validate(field_cls, schema_cls):
    field = field_cls(schema=schema_cls, errors="raise")

    # Invalid python dict
    with pytest.raises(ValidationError) as exc_info:
        field.to_python({"stub_str": "missing_list"})
    assert exc_info.value.code == "invalid"
    assert exc_info.value.params is not None
    assert "errors" in exc_info.value.params
    assert exc_info.value.params["field"] is field

    # Invalid JSON string
    with pytest.raises(ValidationError) as exc_info_json:
        field.to_python('{"stub_str": "missing_list"}')
    assert exc_info_json.value.code == "invalid"

    # Malformed non-JSON string for model schema reports validate_python error
    with pytest.raises(ValidationError) as exc_info_non_json:
        field.to_python("not-a-json-object")
    assert exc_info_non_json.value.params is not None
    assert len(exc_info_non_json.value.params["errors"]) > 0
    assert exc_info_non_json.value.params["errors"][0]["type"] != "json_invalid"

    # validate() also raises Django ValidationError
    with pytest.raises(ValidationError):
        field.validate({"stub_str": "missing_list"}, None)


def test_errors_raise_on_corrupted_db_row_and_annotations():
    pk = _insert_raw_sample_row(
        SampleModel,
        {"stub_str": "corrupted_no_list"},
    )

    # Fetching model instance raises ValidationError
    with pytest.raises(ValidationError):
        SampleModel.objects.get(pk=pk)

    # Fetching via .values() also validates through from_db_value -> to_python
    with pytest.raises(ValidationError):
        list(SampleModel.objects.filter(pk=pk).values("sample_field"))

    # Issue #80: Malformed queryset annotations with output_field=SchemaField raise ValidationError
    valid_instance = SampleModel.objects.create(
        sample_field=InnerSchema(stub_str="ok", stub_list=[date(2023, 1, 1)]),
        sample_list=[],
    )
    with pytest.raises(ValidationError):
        list(
            SampleModel.objects.filter(pk=valid_instance.pk).annotate(
                bad_annotation=Value(
                    {"stub_str": "missing_stub_list"},
                    output_field=SchemaField(InnerSchema),
                )
            )
        )


def test_string_schema_handles_plain_and_json_strings():
    str_field = SchemaField(str)
    # Valid JSON string decodes to str
    assert str_field.to_python('"hello"') == "hello"
    # Plain non-JSON string falls back to validate_python and succeeds for str schema
    assert str_field.to_python("plain_string") == "plain_string"


# ============================================================================
# 3. errors="ignore" (Graceful Degradation, Cleanup & Signals)
# ============================================================================


@FIELD_SCHEMA_PARAMS
def test_errors_ignore_to_python_and_prep_value(field_cls, schema_cls):
    field = field_cls(schema=schema_cls, errors="ignore")

    # Invalid JSON string is decoded to raw dict
    raw_from_json = field.to_python('{"stub_str": "legacy_format", "stub_list": "not_a_list"}')
    assert raw_from_json == {"stub_str": "legacy_format", "stub_list": "not_a_list"}

    # Invalid Python dict is returned as-is
    raw_dict = {"stub_str": "legacy_format", "extra": [1, 2, 3]}
    assert field.to_python(raw_dict) == raw_dict

    # Unparseable raw string is returned as-is
    assert field.to_python("{malformed json") == "{malformed json"

    # Saving / preparing raw unvalidated dict back to DB works in both v1 and v2
    prepped = field.get_prep_value(raw_dict)
    assert prepped == raw_dict


@pytest.mark.parametrize(
    "model_cls",
    [
        SampleModel,
        pytest.param(SampleModelV1, marks=V1_SKIP),
    ],
)
def test_errors_ignore_orm_lifecycle_and_signal_deletion(model_cls, monkeypatch):
    field = model_cls._meta.get_field("sample_field")
    monkeypatch.setattr(field, "errors", "ignore")

    pk = _insert_raw_sample_row(
        model_cls,
        {"stub_str": "legacy_enum_value", "stub_list": "not-a-list"},
    )

    # 1. Load corrupted instance without crashing
    instance = model_cls.objects.get(pk=pk)
    assert instance.sample_field == {"stub_str": "legacy_enum_value", "stub_list": "not-a-list"}

    # 2. Re-save instance with unvalidated data still in field
    instance.save()
    instance.refresh_from_db()
    assert instance.sample_field == {"stub_str": "legacy_enum_value", "stub_list": "not-a-list"}

    # 3. Clean up / migrate data in place and save valid model
    schema_cls = InnerSchemaV1 if model_cls is SampleModelV1 else InnerSchema
    instance.sample_field = {"stub_str": instance.sample_field["stub_str"], "stub_list": ["2024-01-01"]}
    assert isinstance(instance.sample_field, schema_cls)
    instance.save()

    # 4. Insert another corrupted row and verify queryset.delete() works even with pre_delete signal
    corrupted_pk = _insert_raw_sample_row(
        model_cls,
        {"broken": True},
    )
    deleted_snapshots = []

    def on_pre_delete(sender, instance, **kwargs):
        deleted_snapshots.append(instance.sample_field)

    pre_delete.connect(on_pre_delete, sender=model_cls)
    try:
        model_cls.objects.filter(pk=corrupted_pk).delete()
    finally:
        pre_delete.disconnect(on_pre_delete, sender=model_cls)

    assert deleted_snapshots == [{"broken": True}]
    assert not model_cls.objects.filter(pk=corrupted_pk).exists()


def test_errors_ignore_annotation():
    instance = SampleModel.objects.create(
        sample_field=InnerSchema(stub_str="ok", stub_list=[]),
        sample_list=[],
    )
    qs = SampleModel.objects.filter(pk=instance.pk).annotate(
        forgiving_ann=Value(
            {"invalid": "payload"},
            output_field=SchemaField(InnerSchema, errors="ignore"),
        )
    )
    result = qs.first()
    assert result is not None
    assert result.forgiving_ann == {"invalid": "payload"}


# ============================================================================
# 4. errors="coerce" (Fallback to Default or None)
# ============================================================================


@FIELD_SCHEMA_PARAMS
def test_errors_coerce_with_callable_and_static_default(field_cls, schema_cls):
    default_instance = schema_cls(stub_str="fallback", stub_list=[date(2020, 1, 1)])

    field_callable = field_cls(
        schema=schema_cls,
        default=lambda: default_instance,
        errors="coerce",
    )
    assert field_callable.to_python('{"invalid": "data"}') == default_instance
    assert field_callable.to_python({"invalid": "data"}) == default_instance

    field_static = field_cls(
        schema=schema_cls,
        default={"stub_str": "static_fallback", "stub_list": [date(2020, 1, 1)]},
        errors="coerce",
    )
    expected_static = schema_cls(stub_str="static_fallback", stub_list=[date(2020, 1, 1)])
    assert field_static.to_python('{"invalid": "data"}') == expected_static


@FIELD_SCHEMA_PARAMS
def test_errors_coerce_with_nullable_no_default(field_cls, schema_cls):
    field_nullable = field_cls(
        schema=schema_cls,
        null=True,
        errors="coerce",
    )
    assert field_nullable.to_python('{"invalid": "data"}') is None
    assert field_nullable.to_python({"invalid": "data"}) is None


def test_errors_coerce_prefers_default_over_null():
    default_instance = InnerSchema(stub_str="default_wins", stub_list=[])
    field = SchemaField(
        InnerSchema,
        null=True,
        default=lambda: default_instance,
        errors="coerce",
    )
    assert field.to_python('{"invalid": "data"}') == default_instance


def test_errors_coerce_raises_when_no_default_and_not_null():
    field = SchemaField(InnerSchema, null=False, errors="coerce")
    with pytest.raises(ValidationError):
        field.to_python('{"invalid": "data"}')


def test_errors_coerce_orm_db_hydration(monkeypatch):
    fallback = InnerSchema(stub_str="coerced_from_db", stub_list=[])
    field = SampleModel._meta.get_field("sample_field")
    monkeypatch.setattr(field, "errors", "coerce")
    monkeypatch.setattr(field, "default", lambda: fallback)

    pk = _insert_raw_sample_row(
        SampleModel,
        {"corrupted": 123},
    )

    instance = SampleModel.objects.get(pk=pk)
    assert instance.sample_field == fallback


@FIELD_SCHEMA_PARAMS
def test_from_db_value_with_predecoded_python_objects(field_cls, schema_cls):
    """Simulate database drivers (e.g. psycopg on PostgreSQL) that pass decoded dicts/lists to from_db_value."""
    raw_invalid_dict = {"stub_str": "from_driver", "stub_list": "not_a_list"}
    raw_valid_dict = {"stub_str": "from_driver", "stub_list": ["2023-01-01"]}

    # errors="raise"
    field_raise = field_cls(schema=schema_cls, errors="raise")
    assert field_raise.from_db_value(raw_valid_dict, None, connection) == schema_cls(
        stub_str="from_driver",
        stub_list=[date(2023, 1, 1)],
    )
    with pytest.raises(ValidationError):
        field_raise.from_db_value(raw_invalid_dict, None, connection)

    # errors="ignore"
    field_ignore = field_cls(schema=schema_cls, errors="ignore")
    assert field_ignore.from_db_value(raw_invalid_dict, None, connection) == raw_invalid_dict

    # errors="coerce"
    fallback = schema_cls(stub_str="driver_fallback", stub_list=[])
    field_coerce = field_cls(schema=schema_cls, default=lambda: fallback, errors="coerce")
    assert field_coerce.from_db_value(raw_invalid_dict, None, connection) == fallback


@FIELD_SCHEMA_PARAMS
def test_errors_coerce_with_broken_callable_default(field_cls, schema_cls):
    """Verify fallback when a callable default itself fails validation under errors='coerce'."""
    broken_nullable = field_cls(
        schema=schema_cls,
        null=True,
        default=lambda: {"invalid_default": 123},
        errors="coerce",
    )
    assert broken_nullable.to_python('{"invalid": "input"}') is None

    broken_nonnull = field_cls(
        schema=schema_cls,
        null=False,
        default=lambda: {"invalid_default": 123},
        errors="coerce",
    )
    with pytest.raises(ValidationError) as exc_info:
        broken_nonnull.to_python('{"invalid": "input"}')
    assert exc_info.value.code == "invalid"


# ============================================================================
# 5. Query Annotations, Expressions & KeyTransforms (Issue #80)
# ============================================================================


@QUERY_ANNOTATION_PARAMS
def test_valid_query_annotations_hydrate_to_schema(model_cls, field_cls, schema_cls):
    item = schema_cls(stub_str="item0", stub_int=7, stub_list=[date(2023, 2, 2)])
    instance = model_cls.objects.create(
        sample_field=schema_cls(stub_str="root", stub_int=1, stub_list=[date(2023, 1, 1)]),
        sample_list=[item],
    )
    valid_json = json.dumps({"stub_str": "from_sql", "stub_int": 3, "stub_list": ["2023-03-03"]})
    expected_from_sql = schema_cls(stub_str="from_sql", stub_int=3, stub_list=[date(2023, 3, 3)])
    expected_from_val = schema_cls(stub_str="from_val", stub_int=2, stub_list=[date(2023, 4, 4)])
    expected_from_json_obj = schema_cls(stub_str="from_json_obj", stub_int=5, stub_list=[date(2023, 1, 1)])

    qs = model_cls.objects.filter(pk=instance.pk).annotate(
        ann_value=Value(
            {"stub_str": "from_val", "stub_int": 2, "stub_list": ["2023-04-04"]},
            output_field=field_cls(schema_cls),
        ),
        ann_raw_sql=RawSQL(
            "%s",
            (valid_json,),
            output_field=field_cls(schema_cls),
        ),
        ann_json_obj=ExpressionWrapper(
            JSONObject(
                stub_str=Value("from_json_obj"),
                stub_int=Value(5),
                stub_list=F("sample_field__stub_list"),
            ),
            output_field=field_cls(schema_cls),
        ),
        ann_cast=Cast("sample_list__0", output_field=field_cls(schema_cls)),
        ann_wrapper=ExpressionWrapper(F("sample_list__0"), output_field=field_cls(schema_cls)),
        ann_key_transform=KeyTransform("0", "sample_list", output_field=field_cls(schema_cls)),
        ann_subquery=Subquery(
            model_cls.objects.filter(pk=OuterRef("pk")).values("sample_list__0")[:1],
            output_field=field_cls(schema_cls),
        ),
    )

    _assert_annotated_queryset(
        qs,
        {
            "ann_value": expected_from_val,
            "ann_raw_sql": expected_from_sql,
            "ann_json_obj": expected_from_json_obj,
            "ann_cast": item,
            "ann_wrapper": item,
            "ann_key_transform": item,
            "ann_subquery": item,
        },
    )


@QUERY_ANNOTATION_PARAMS
def test_malformed_query_annotations_raise_by_default(model_cls, field_cls, schema_cls):
    pk = _insert_raw_sample_row(
        model_cls,
        sample_field_data={"stub_str": "ok", "stub_int": 1, "stub_list": ["2023-01-01"]},
        sample_list_data=[{"stub_str": "bad_elem_missing_list"}],
    )
    invalid_json = json.dumps({"stub_str": "missing_stub_list"})

    expressions = [
        Value({"stub_str": "missing_stub_list"}, output_field=field_cls(schema_cls)),
        RawSQL("%s", (invalid_json,), output_field=field_cls(schema_cls)),
        ExpressionWrapper(
            JSONObject(stub_str=Value("missing_stub_list")),
            output_field=field_cls(schema_cls),
        ),
        Cast("sample_list__0", output_field=field_cls(schema_cls)),
        ExpressionWrapper(F("sample_list__0"), output_field=field_cls(schema_cls)),
        KeyTransform("0", "sample_list", output_field=field_cls(schema_cls)),
        Subquery(
            model_cls.objects.filter(pk=OuterRef("pk")).values("sample_list__0")[:1],
            output_field=field_cls(schema_cls),
        ),
    ]

    base_qs = model_cls.objects.filter(pk=pk).only("id")
    for expr in expressions:
        qs = base_qs.annotate(bad_ann=expr)
        with pytest.raises(ValidationError):
            list(qs)
        with pytest.raises(ValidationError):
            list(qs.values("bad_ann"))
        with pytest.raises(ValidationError):
            list(qs.values_list("bad_ann", flat=True))


@QUERY_ANNOTATION_PARAMS
def test_malformed_query_annotations_ignore_and_coerce(model_cls, field_cls, schema_cls):
    pk = _insert_raw_sample_row(
        model_cls,
        sample_field_data={"stub_str": "ok", "stub_int": 1, "stub_list": ["2023-01-01"]},
        sample_list_data=[{"stub_str": "bad_elem_missing_list"}],
    )
    invalid_payload = {"stub_str": "bad_elem_missing_list"}
    invalid_json = json.dumps(invalid_payload)
    fallback = schema_cls(stub_str="coerced_ann", stub_list=[date(2020, 1, 1)])

    qs = (
        model_cls.objects.filter(pk=pk)
        .only("id")
        .annotate(
            ignore_json_obj=ExpressionWrapper(
                JSONObject(stub_str=Value("bad_elem_missing_list")),
                output_field=field_cls(schema_cls, errors="ignore"),
            ),
            ignore_raw_sql=RawSQL(
                "%s",
                (invalid_json,),
                output_field=field_cls(schema_cls, errors="ignore"),
            ),
            ignore_key_transform=KeyTransform(
                "0",
                "sample_list",
                output_field=field_cls(schema_cls, errors="ignore"),
            ),
            coerce_val=Value(
                invalid_payload,
                output_field=field_cls(schema_cls, errors="coerce", default=lambda: fallback),
            ),
            coerce_json_obj=ExpressionWrapper(
                JSONObject(stub_str=Value("bad_elem_missing_list")),
                output_field=field_cls(schema_cls, errors="coerce", default=lambda: fallback),
            ),
            coerce_raw_sql=RawSQL(
                "%s",
                (invalid_json,),
                output_field=field_cls(schema_cls, errors="coerce", default=lambda: fallback),
            ),
            coerce_key_transform=KeyTransform(
                "0",
                "sample_list",
                output_field=field_cls(schema_cls, errors="coerce", default=lambda: fallback),
            ),
            coerce_null=KeyTransform(
                "0",
                "sample_list",
                output_field=field_cls(schema_cls, errors="coerce", null=True),
            ),
        )
    )

    _assert_annotated_queryset(
        qs,
        {
            "ignore_json_obj": invalid_payload,
            "ignore_raw_sql": invalid_payload,
            "ignore_key_transform": invalid_payload,
            "coerce_val": fallback,
            "coerce_json_obj": fallback,
            "coerce_raw_sql": fallback,
            "coerce_key_transform": fallback,
            "coerce_null": None,
        },
    )


@QUERY_ANNOTATION_PARAMS
def test_implicit_key_transforms_bypass_parent_schema_validation(model_cls, field_cls, schema_cls):
    instance = model_cls.objects.create(
        sample_field=schema_cls(stub_str="hello", stub_int=42, stub_list=[date(2023, 5, 5)]),
        sample_list=[schema_cls(stub_str="elem0", stub_int=9, stub_list=[date(2023, 6, 6)])],
    )
    expected_elem_dict = {"stub_str": "elem0", "stub_int": 9, "stub_list": ["2023-06-06"]}

    values_row = (
        model_cls.objects.filter(pk=instance.pk)
        .values("sample_field__stub_str", "sample_field__stub_int", "sample_list__0")
        .get()
    )
    assert values_row == {
        "sample_field__stub_str": "hello",
        "sample_field__stub_int": 42,
        "sample_list__0": expected_elem_dict,
    }

    qs = model_cls.objects.filter(pk=instance.pk).annotate(
        extracted_str=F("sample_field__stub_str"),
        extracted_elem=KeyTransform("0", "sample_list"),
        annotated_schema=Value(
            {"stub_str": "from_ann", "stub_int": 11, "stub_list": ["2023-07-07"]},
            output_field=field_cls(schema_cls),
        ),
        chained_from_ann=KeyTransform("stub_str", "annotated_schema"),
    )
    obj = qs.get()
    assert obj.extracted_str == "hello"
    assert obj.extracted_elem == expected_elem_dict
    assert obj.annotated_schema == schema_cls(stub_str="from_ann", stub_int=11, stub_list=[date(2023, 7, 7)])
    assert obj.chained_from_ann == "from_ann"
