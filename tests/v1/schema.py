import typing as t
from datetime import date

try:
    import pydantic.v1 as pydantic
except ImportError:
    import pydantic

from pydantic.dataclasses import dataclass


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
