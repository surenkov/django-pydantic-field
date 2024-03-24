from django.middleware.csrf import CsrfViewMiddleware
import pytest

from django.contrib.auth.models import AnonymousUser
from django.contrib.admin import site

from .test_app import admin, models

pytestmark = [
    pytest.mark.django_db(),
]

all_admins = {
    # This model cannot be instantiated without reasonable defaults
    # models.SampleModel: admin.SampleModelAdmin,
    #
    models.SampleForwardRefModel: admin.SampleForwardRefModelAdmin,
    models.SampleModelWithRoot: admin.SampleModelWithRootAdmin,
    models.ExampleModel: admin.ExampleModelAdmin
}


@pytest.fixture
def user():
    return AnonymousUser()


def patch_model_admin(admin_view, monkeypatch):
    monkeypatch.setattr(CsrfViewMiddleware, "process_view", lambda self, req, *a, **kw: self._accept(req))
    monkeypatch.setattr(admin_view, "has_view_permission", lambda self, *args: True)
    monkeypatch.setattr(admin_view, "has_view_or_change_permission", lambda self, *args: True)
    monkeypatch.setattr(admin_view, "has_add_permission", lambda self, *args: True)
    monkeypatch.setattr(admin_view, "has_change_permission", lambda self, *args: True)
    monkeypatch.setattr(admin_view, "has_delete_permission", lambda self, *args: True)


@pytest.mark.parametrize("model, admin_view", all_admins.items())
def test_model_admin_view_not_failing(model, admin_view, rf, user, monkeypatch):
    patch_model_admin(admin_view, monkeypatch)

    request = rf.get("/")
    request.user = user

    response = admin_view(model, site).changeform_view(request)
    assert response.status_code == 200
