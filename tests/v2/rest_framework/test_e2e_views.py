from datetime import date

import pytest

from tests.conftest import InnerSchema

from .view_fixtures import (
    ClassBasedView,
    ClassBasedViewWithModel,
    ClassBasedViewWithSchemaContext,
    sample_view,
)

rest_framework = pytest.importorskip("django_pydantic_field.v2.rest_framework")


@pytest.mark.parametrize(
    "view",
    [
        sample_view,
        ClassBasedView.as_view(),
        ClassBasedViewWithSchemaContext.as_view(),
    ],
)
def test_end_to_end_api_view(view, request_factory):
    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    existing_encoded = b'{"stub_str":"abc","stub_int":1,"stub_list":["2022-07-01"]}'

    request = request_factory.post("/", existing_encoded, content_type="application/json")
    response = view(request)

    assert response.data == [expected_instance]
    assert response.data[0] is not expected_instance

    assert response.rendered_content == b"[%s]" % existing_encoded


@pytest.mark.django_db
def test_end_to_end_list_create_api_view(request_factory):
    field_data = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]).json()
    expected_result = {
        "sample_field": {"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1},
        "sample_list": [{"stub_str": "abc", "stub_list": ["2022-07-01"], "stub_int": 1}],
        "sample_seq": [],
    }

    payload = '{"sample_field": %s, "sample_list": [%s], "sample_seq": []}' % ((field_data,) * 2)
    request = request_factory.post("/", payload.encode(), content_type="application/json")
    response = ClassBasedViewWithModel.as_view()(request)

    assert response.data == expected_result

    request = request_factory.get("/", content_type="application/json")
    response = ClassBasedViewWithModel.as_view()(request)
    assert response.data == [expected_result]
