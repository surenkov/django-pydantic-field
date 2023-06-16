import typing as t
from datetime import date

import pydantic
import pytest

from django.conf import settings
from django.db import connections
from pydantic.dataclasses import dataclass
from rest_framework.test import APIRequestFactory


class InnerSchema(pydantic.BaseModel):
    stub_str: str
    stub_int: int = 1
    stub_list: t.List[date]

    class Config:
        allow_mutation = True
        frozen = False


@dataclass
class SampleDataclass:
    stub_str: str
    stub_list: t.List[date]
    stub_int: int = 1


@pytest.fixture
def request_factory():
    return APIRequestFactory()


# ==============================
# PARAMETRIZED DATABASE BACKENDS
# ==============================


def sqlite_backend(_monkeypatch, _settings):
    pass  # sqlite is our default database backend


def postgres_backend(monkeypatch, settings):
    settings.DATABASES["default"] = settings.DATABASES["postgres"]

    with monkeypatch.context() as patch:
        patch.setitem(connections, "default", connections["postgres"])
        yield


def mysql_backend(monkeypatch, settings):
    settings.DATABASES["default"] = settings.DATABASES["mysql"]
    with monkeypatch.context() as patch:
        patch.setitem(connections, "default", connections["mysql"])
        yield


@pytest.fixture(
    params=[
        sqlite_backend,
        pytest.param(
            postgres_backend,
            marks=pytest.mark.skipif(
                "postgres" not in settings.DATABASES,
                reason="POSTGRES_DSN is not specified",
            ),
        ),
        pytest.param(
            mysql_backend,
            marks=pytest.mark.skipif(
                "mysql" not in settings.DATABASES,
                reason="MYSQL_DSN is not specified",
            ),
        ),
    ]
)
def available_database_backends(request, django_db_blocker, monkeypatch, settings):
    with django_db_blocker.unblock():
        yield request.param(monkeypatch, settings)
