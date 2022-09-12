import typing as t
import pydantic
import pytest

from datetime import date
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
