from datetime import date

import pytest

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
def test_model_e2e_serde(initial_payload, expected_values):
    instance = SampleModel(**initial_payload)
    instance.save()

    instance = SampleModel.objects.get(pk=instance.pk)
    instance_values = {k: getattr(instance, k) for k in expected_values.keys()}
    assert instance_values == expected_values
