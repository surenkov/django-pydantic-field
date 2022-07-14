import typing as t
import pydantic
import pytest

from datetime import date
from rest_framework.test import APIRequestFactory


class InnerSchema(pydantic.BaseModel):
    stub_str: str
    stub_int: int = 1
    stub_list: t.List[date]


@pytest.fixture
def request_factory():
    return APIRequestFactory()
