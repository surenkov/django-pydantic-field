import pytest

from ..test_app.models import SampleModel

_ = pytest.importorskip("django_pydantic_field.v2.fields", exc_type=ImportError)


@pytest.mark.django_db
def test_key_lookup_on_schema_field():
    instance = SampleModel.objects.create(
        sample_field={"stub_str": "foo", "stub_int": 1, "stub_list": ["1970-01-01"]},
        sample_list=[],
    )

    value = SampleModel.objects.values("sample_field__stub_str").get(pk=instance.pk)
    assert value["sample_field__stub_str"] == "foo"

    value = SampleModel.objects.values("sample_field__stub_int").get(pk=instance.pk)
    assert value["sample_field__stub_int"] == 1

    value = SampleModel.objects.values("sample_field__stub_list").get(pk=instance.pk)
    assert value["sample_field__stub_list"] == ["1970-01-01"]
