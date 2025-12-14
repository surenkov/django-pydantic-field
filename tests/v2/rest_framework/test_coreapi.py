import sys

import pytest
from rest_framework import schemas
from rest_framework.request import Request

from .view_fixtures import create_views_urlconf

coreapi = pytest.importorskip("django_pydantic_field.v2.rest_framework.coreapi")


@pytest.mark.skipif(sys.version_info >= (3, 12), reason="CoreAPI is not compatible with 3.12")
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
    urlconf = create_views_urlconf(coreapi.AutoSchema)
    generator = schemas.SchemaGenerator(urlconf=urlconf)
    request = Request(request_factory.generic(method, path))
    coreapi_schema = generator.get_schema(request)
    assert coreapi_schema
