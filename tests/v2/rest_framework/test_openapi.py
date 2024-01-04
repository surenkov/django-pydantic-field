import pytest
from rest_framework.schemas.openapi import SchemaGenerator
from rest_framework.request import Request

from .view_fixtures import create_views_urlconf

openapi = pytest.importorskip("django_pydantic_field.v2.rest_framework.openapi")

@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/func"),
        ("POST", "/func"),
        ("GET", "/class"),
        ("PUT", "/class"),
    ],
)
def test_openapi_schema_generators(request_factory, method, path, snapshot_json):
    urlconf = create_views_urlconf(openapi.AutoSchema)
    generator = SchemaGenerator(urlconf=urlconf)
    request = Request(request_factory.generic(method, path))
    assert snapshot_json() == generator.get_schema(request)
