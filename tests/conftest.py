import typing as ty
from datetime import date

import pydantic
import pytest
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
