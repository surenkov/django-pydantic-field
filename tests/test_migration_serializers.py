import sys
import typing as t
import typing_extensions as te

from django.db.migrations.writer import MigrationWriter
import pytest

import django_pydantic_field
from django_pydantic_field._migration_serializers import GenericContainer

if sys.version_info < (3, 8):
    test_types = [
        str,
        list,
        t.List[str],
        t.Union[te.Literal["foo"], t.List[str]],
        t.List[t.Union[int, bool]],
        t.Tuple[t.List[te.Literal[1]], t.Union[str, te.Literal["foo"]]],
        t.ForwardRef("str"),
    ]
else:
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
    if sys.version_info < (3, 8):
        imports.update(typing_extensions=te)
    assert eval(expression, imports) == typ
