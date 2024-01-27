from datetime import date

import pytest
from django.core import serializers
from django.db.models import F, Q, JSONField, Value

from tests.conftest import InnerSchema
from tests.test_app.models import ExampleModel, SampleModel

pytestmark = [
    pytest.mark.usefixtures("available_database_backends"),
    pytest.mark.django_db(databases="__all__"),
]


@pytest.mark.parametrize(
    "initial_payload,expected_values",
    [
        (
            {
                "sample_field": InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 1)]),
                "sample_list": [InnerSchema(stub_str="abc", stub_list=[])],
            },
            {
                "sample_field": InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 1)]),
                "sample_list": [InnerSchema(stub_str="abc", stub_list=[])],
            },
        ),
        (
            {
                "sample_field": {"stub_str": "abc", "stub_list": ["2023-06-01"]},
                "sample_list": [{"stub_str": "abc", "stub_list": []}],
            },
            {
                "sample_field": InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 1)]),
                "sample_list": [InnerSchema(stub_str="abc", stub_list=[])],
            },
        ),
    ],
)
def test_model_db_serde(initial_payload, expected_values):
    instance = SampleModel(**initial_payload)
    instance.save()

    instance = SampleModel.objects.get(pk=instance.pk)
    instance_values = {k: getattr(instance, k) for k in expected_values.keys()}
    assert instance_values == expected_values


@pytest.mark.parametrize(
    "Model,payload,update_fields",
    [
        (
            SampleModel,
            {
                "sample_field": InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 1)]),
                "sample_list": [InnerSchema(stub_str="abc", stub_list=[])],
            },
            ["sample_field", "sample_list", "sample_seq"],
        ),
        (
            SampleModel,
            {
                "sample_field": {"stub_str": "abc", "stub_list": ["2023-06-01"]},
                "sample_list": [{"stub_str": "abc", "stub_list": []}],
            },
            ["sample_field", "sample_list", "sample_seq"],
        ),
        (ExampleModel, {}, ["example_field"]),
        (ExampleModel, {"example_field": {"count": 1}}, ["example_field"]),
    ],
)
def test_model_bulk_operations(Model, payload, update_fields):
    models = [
        Model(**payload),
        Model(**payload),
        Model(**payload),
    ]
    saved_models = Model.objects.bulk_create(models)
    fetched_models = Model.objects.order_by("pk")
    assert len(fetched_models) == len(saved_models) == 3

    Model.objects.bulk_update(fetched_models, update_fields)
    assert len(fetched_models.all()) == 3


@pytest.mark.parametrize("format", ["python", "json", "yaml", "jsonl"])
@pytest.mark.parametrize(
    "payload",
    [
        {
            "sample_field": InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 1)]),
            "sample_list": [InnerSchema(stub_str="abc", stub_list=[])],
        },
        {
            "sample_field": {"stub_str": "abc", "stub_list": ["2023-06-01"]},
            "sample_list": [{"stub_str": "abc", "stub_list": []}],
        },
    ],
)
def test_model_serialization(payload, format):
    instance = SampleModel(**payload)
    instance_values = {k: getattr(instance, k) for k in payload.keys()}

    serialized_instances = serializers.serialize(format, [instance])
    deserialized_instance = next(serializers.deserialize(format, serialized_instances)).object
    deserialized_values = {k: getattr(deserialized_instance, k) for k in payload.keys()}

    assert instance_values == deserialized_values
    assert serialized_instances == serializers.serialize(format, [deserialized_instance])


@pytest.mark.parametrize(
    "lookup",
    [
        Q(),
        Q(sample_field=InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 1)])),
        Q(sample_field={"stub_str": "abc", "stub_list": ["2023-06-01"]}),
        Q(sample_field__stub_int=1),
        Q(sample_field__stub_str="abc"),
        Q(sample_field__stub_list=[date(2023, 6, 1)]),
        Q(sample_field__stub_str=F("sample_field__stub_str")),
        Q(sample_field__stub_int=F("sample_field__stub_int")),
        Q(sample_field__stub_int=Value(1, output_field=JSONField())),
        Q(sample_field__stub_str=Value("abc", output_field=JSONField())),
        ~Q(sample_field__stub_int=Value("abcd", output_field=JSONField())),
    ],
)
def test_model_field_lookup_succeeded(lookup):
    instance = SampleModel(
        sample_field=dict(stub_str="abc", stub_list=["2023-06-01"]),
        sample_list=[],
    )
    instance.save()

    filtered_instance = SampleModel.objects.get(lookup)
    assert filtered_instance.pk == instance.pk


@pytest.mark.parametrize(
    "lookup",
    [
        Q(sample_field=InnerSchema(stub_str="abcd", stub_list=[date(2023, 6, 1)])),
        Q(sample_field=InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 2)])),
        Q(sample_field={"stub_str": "abcd", "stub_list": ["2023-06-01"]}),
        Q(sample_field={"stub_str": "abc", "stub_list": ["2023-06-02"]}),
        Q(sample_field__stub_int=2),
        Q(sample_field__stub_str="abcd"),
        Q(sample_field__stub_list=[date(2023, 6, 2)]),
        Q(sample_field__stub_int=F("sample_field__stub_str")),
        Q(sample_field__stub_int=Value(2, output_field=JSONField())),
        Q(sample_field__stub_int=Value("abcd", output_field=JSONField())),
        Q(sample_field__stub_str=Value("abcd", output_field=JSONField())),
    ],
)
def test_model_field_lookup_failed(lookup):
    instance = SampleModel(
        sample_field=dict(stub_str="abc", stub_list=["2023-06-01"]),
        sample_list=[],
    )
    instance.save()

    with pytest.raises(SampleModel.DoesNotExist):
        SampleModel.objects.get(lookup)
