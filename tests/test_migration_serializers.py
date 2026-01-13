import typing as ty

import pytest
import typing_extensions as te
from django.db.migrations.writer import MigrationWriter

import django_pydantic_field

try:
    from django_pydantic_field.compat.django import GenericContainer
except ImportError:
    from django_pydantic_field._migration_serializers import GenericContainer  # noqa

try:
    import annotationlib  # type: ignore[unresolved-import]
except ImportError:
    annotationlib = None

test_types = [
    str,
    list,
    list[str],
    ty.Literal["foo"],
    ty.Union[ty.Literal["foo"], list[str]],
    list[ty.Union[int, bool]],
    tuple[list[ty.Literal[1]], ty.Union[str, ty.Literal["foo"]]],
    ty.ForwardRef("str"),
]


@pytest.mark.parametrize("raw_type", test_types)
def test_wrap_unwrap_idempotent(raw_type):
    wrapped_type = GenericContainer.wrap(raw_type)
    assert raw_type == GenericContainer.unwrap(wrapped_type)


@pytest.mark.parametrize("raw_type", test_types)
def test_serialize_eval_idempotent(raw_type):
    raw_type = GenericContainer.wrap(raw_type)
    expression, _ = MigrationWriter.serialize(raw_type)
    imports = dict(
        typing=ty, typing_extensions=te, django_pydantic_field=django_pydantic_field, annotationlib=annotationlib
    )
    assert eval(expression, imports) == raw_type
