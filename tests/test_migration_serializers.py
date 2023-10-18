import typing as t

from django.db.migrations.writer import MigrationWriter
import pytest

import django_pydantic_field
from django_pydantic_field._migration_serializers import GenericContainer

test_types = [
    str,
    list,
    list[str],
    t.Union[t.Literal["foo"], list[str]],
    list[t.Union[int, bool]],
    tuple[list[t.Literal[1]], t.Union[str, t.Literal["foo"]]],
    t.ForwardRef("str"),
]


@pytest.mark.parametrize("typ", test_types)
def test_wrap_unwrap_idempotent(typ):
    assert typ == GenericContainer.unwrap(GenericContainer.wrap(typ))


@pytest.mark.parametrize("typ", test_types)
def test_serialize_eval_idempotent(typ):
    typ = GenericContainer.wrap(typ)
    expression, _ = MigrationWriter.serialize(GenericContainer.wrap(typ))
    imports = dict(typing=t, django_pydantic_field=django_pydantic_field)
    assert eval(expression, imports) == typ
