import pytest


def test_model_admin_not_failing():
    try:
        from .test_app import admin
    except:
        pytest.fail("Django admin handlers should not fail")
