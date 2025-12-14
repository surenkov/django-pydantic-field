import typing as t
from datetime import date

import pydantic
import pytest
from django.conf import settings
from pydantic.dataclasses import dataclass
from rest_framework.test import APIRequestFactory
from syrupy.extensions.json import JSONSnapshotExtension

from django_pydantic_field.compat import PYDANTIC_V2


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


class SchemaWithCustomTypes(pydantic.BaseModel):
    url: pydantic.HttpUrl = "http://localhost/"
    uid: pydantic.UUID4 = "367388a6-9b3b-4ef0-af84-a27d61a05bc7"
    crd: pydantic.PaymentCardNumber = "4111111111111111"

    if PYDANTIC_V2:
        b64: pydantic.Base64Str = "YmFzZTY0"
        model_config = dict(validate_default=True)  # type: ignore


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


@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)
