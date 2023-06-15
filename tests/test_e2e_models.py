from datetime import date

import pytest

from django.db.models import Q
from .conftest import InnerSchema
from .test_app.models import SampleModel


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
                "sample_field": {"stub_str": "abc", "stub_list": ['2023-06-01']},
                "sample_list": [{"stub_str": "abc", "stub_list": []}],
            },
            {
                "sample_field": InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 1)]),
                "sample_list": [InnerSchema(stub_str="abc", stub_list=[])],
            },
        ),
    ],
)
@pytest.mark.django_db
def test_model_db_serde(initial_payload, expected_values):
    instance = SampleModel(**initial_payload)
    instance.save()

    instance = SampleModel.objects.get(pk=instance.pk)
    instance_values = {k: getattr(instance, k) for k in expected_values.keys()}
    assert instance_values == expected_values


@pytest.mark.parametrize(
    "lookup",
    [
        Q(),
        Q(sample_field=InnerSchema(stub_str="abc", stub_list=[date(2023, 6, 1)])),
        Q(sample_field={"stub_str": "abc", "stub_list": ["2023-06-01"]}),
        Q(sample_field__stub_int=1),
        Q(sample_field__stub_str="abc"),
        Q(sample_field__stub_list=[date(2023, 6, 1)]),
    ],
)
@pytest.mark.django_db
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
    ],
)
@pytest.mark.django_db
def test_model_field_lookup_failed(lookup):
    instance = SampleModel(
        sample_field=dict(stub_str="abc", stub_list=["2023-06-01"]),
        sample_list=[],
    )
    instance.save()

    with pytest.raises(SampleModel.DoesNotExist):
        SampleModel.objects.get(lookup)