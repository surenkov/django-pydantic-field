import sys
import dataclasses
import typing as ty
from unittest.mock import MagicMock

import annotated_types
import pytest
from django.db.migrations.writer import MigrationWriter
from pydantic import SecretStr, conint, constr
from typing_extensions import Annotated

from django_pydantic_field.compat import PYDANTIC_V1
from django_pydantic_field.compat.django import GenericContainer

try:
    from pydantic.types import StringConstraints
except ImportError:
    StringConstraints = MagicMock()


@dataclasses.dataclass
class SampleDataclass:
    tp: ty.Any

if sys.version_info < (3, 9):
    test_types = [
        str,
        list,
        ty.List[str],
        ty.Literal["foo"],
        ty.Union[ty.Literal["foo"], ty.List[str]],
        ty.List[ty.Union[int, bool]],
        ty.Tuple[ty.List[ty.Literal[1]], ty.Union[str, ty.Literal["foo"]]],
        ty.ForwardRef("str"),
        SecretStr,
        Annotated[int, annotated_types.Gt(gt=0)],
        SampleDataclass,
        pytest.param(
            conint(gt=0),
            marks=pytest.mark.xfail(
                PYDANTIC_V1,
                reason="Pydantic v1 does not provide a type hierarchy for constrained types",
                strict=False,
            ),
        ),
        pytest.param(
            constr(min_length=10),
            marks=pytest.mark.xfail(
                PYDANTIC_V1,
                reason="Pydantic v1 does not provide a type hierarchy for constrained types",
                strict=False,
            ),
        ),
        pytest.param(
            Annotated[str, StringConstraints(pattern=r"[a-zA-Z0-9_]+")],
            marks=pytest.mark.skipif(
                PYDANTIC_V1,
                reason="StringConstraints is available since Pydantic v2",
            ),
        ),
    ]
else:
    test_types = [
        str,
        list,
        list[str],
        ty.Literal["foo"],
        ty.Union[ty.Literal["foo"], list[str]],
        list[ty.Union[int, bool]],
        tuple[list[ty.Literal[1]], ty.Union[str, ty.Literal["foo"]]],
        ty.ForwardRef("str"),
        SecretStr,
        Annotated[int, annotated_types.Gt(gt=0)],
        SampleDataclass,
        pytest.param(
            conint(gt=0),
            marks=pytest.mark.xfail(
                PYDANTIC_V1,
                reason="Pydantic v1 does not provide a type hierarchy for constrained types",
                strict=False,
            ),
        ),
        pytest.param(
            constr(min_length=10),
            marks=pytest.mark.xfail(
                PYDANTIC_V1,
                reason="Pydantic v1 does not provide a type hierarchy for constrained types",
                strict=False,
            ),
        ),
        pytest.param(
            Annotated[str, StringConstraints(pattern=r"[a-zA-Z0-9_]+")],
            marks=pytest.mark.skipif(
                PYDANTIC_V1,
                reason="StringConstraints is available since Pydantic v2",
            ),
        ),
    ]

@pytest.mark.parametrize("raw_type", test_types)
def test_wrap_unwrap_idempotent(raw_type):
    wrapped_type = GenericContainer.wrap(raw_type)
    assert raw_type == GenericContainer.unwrap(wrapped_type)


@pytest.mark.parametrize("raw_type", test_types)
def test_serialize_eval_idempotent(raw_type):
    raw_type = GenericContainer.wrap(raw_type)
    expression, raw_imports = MigrationWriter.serialize(raw_type)

    resolved_imports = {}
    exec("\n".join(raw_imports) + "\n", {}, resolved_imports)

    assert eval(expression, resolved_imports) == raw_type
