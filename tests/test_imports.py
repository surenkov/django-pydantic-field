import warnings

import pytest

import django_pydantic_field
from django_pydantic_field import fields, forms, rest_framework
from django_pydantic_field.compat import PYDANTIC_V1, PYDANTIC_V2


@pytest.mark.parametrize(
    "module, exported_primitive_name",
    [
        (django_pydantic_field, "SchemaField"),
        (fields, "SchemaField"),
        (forms, "SchemaField"),
        (rest_framework, "SchemaParser"),
        (rest_framework, "SchemaRenderer"),
        (rest_framework, "SchemaField"),
        (rest_framework, "AutoSchema"),
        pytest.param(
            rest_framework,
            "openapi",
            marks=pytest.mark.skipif(
                not PYDANTIC_V2,
                reason="`.rest_framework.openapi` module is only appearing in v2 layer",
            ),
        ),
        pytest.param(
            rest_framework,
            "coreapi",
            marks=pytest.mark.skipif(
                not PYDANTIC_V2,
                reason="`.rest_framework.coreapi` module is only appearing in v2 layer",
            ),
        ),
    ],
)
def test_module_imports(module, exported_primitive_name):
    assert exported_primitive_name in dir(module)
    assert getattr(module, exported_primitive_name, None) is not None


@pytest.mark.skipif(not PYDANTIC_V2, reason="AutoSchema import warning is only appearing in v2 layer")
def test_rest_framework_autoschema_warning_v2():
    with pytest.deprecated_call(match="`django_pydantic_field.rest_framework.AutoSchema` is deprecated.*"):
        rest_framework.AutoSchema


@pytest.mark.skipif(not PYDANTIC_V1, reason="Deprecation warning should not be raised in v1 layer")
def test_rest_framework_autoschema_no_warning_v1():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rest_framework.AutoSchema
