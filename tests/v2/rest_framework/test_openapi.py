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
def test_coreapi_schema_generators(request_factory, method, path):
    urlconf = create_views_urlconf(openapi.AutoSchema)
    generator = SchemaGenerator(urlconf=urlconf)
    request = Request(request_factory.generic(method, path))
    openapi_schema = generator.get_schema(request)
    assert openapi_schema
