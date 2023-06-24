import typing as ty
from datetime import date

import pydantic
import pytest

from django.conf import settings
from pydantic.dataclasses import dataclass

from rest_framework.test import APIRequestFactory


class InnerSchema(pydantic.BaseModel):
    model_config = dict(frozen=False)

    stub_str: str
    stub_int: int = 1
    stub_list: ty.List[date]


@dataclass
class SampleDataclass:
    stub_str: str
    stub_list: ty.List[date]
    stub_int: int = 1


@pytest.fixture
def request_factory():
    return APIRequestFactory()


# ==============================
# PARAMETRIZED DATABASE BACKENDS
# ==============================


def sqlite_backend(settings):
    settings.CURRENT_TEST_DB = "default"


def postgres_backend(settings):
    settings.CURRENT_TEST_DB = "postgres"


def mysql_backend(settings):
    settings.CURRENT_TEST_DB = "mysql"


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
def available_database_backends(request, settings):
    yield request.param(settings)
