import sys
import pydantic
import pytest
import typing as ty

from ..conftest import InnerSchema, SampleDataclass

types = pytest.importorskip("django_pydantic_field.v2.types")
skip_unsupported_builtin_subscription = pytest.mark.skipif(sys.version_info < (3, 9), reason="Built-in type subscription supports only in 3.9+")


@pytest.mark.parametrize(
    "ctor, args, kwargs",
    [
        pytest.param(types.SchemaAdapter, ["list[int]", None, None, None], {}, marks=skip_unsupported_builtin_subscription),
        pytest.param(types.SchemaAdapter, ["list[int]", {"strict": True}, None, None], {}, marks=skip_unsupported_builtin_subscription),
        (types.SchemaAdapter, [ty.List[int], None, None, None], {}),
        (types.SchemaAdapter, [ty.List[int], {"strict": True}, None, None], {}),
        (types.SchemaAdapter, [None, None, InnerSchema, "stub_int"], {}),
        (types.SchemaAdapter, [None, None, SampleDataclass, "stub_int"], {}),
        pytest.param(types.SchemaAdapter.from_type, ["list[int]"], {}, marks=skip_unsupported_builtin_subscription),
        pytest.param(types.SchemaAdapter.from_type, ["list[int]", {"strict": True}], {}, marks=skip_unsupported_builtin_subscription),
        (types.SchemaAdapter.from_type, [ty.List[int]], {}),
        (types.SchemaAdapter.from_type, [ty.List[int], {"strict": True}], {}),
        (types.SchemaAdapter.from_annotation, [InnerSchema, "stub_int"], {}),
        (types.SchemaAdapter.from_annotation, [InnerSchema, "stub_int", {"strict": True}], {}),
        (types.SchemaAdapter.from_annotation, [SampleDataclass, "stub_int"], {}),
        (types.SchemaAdapter.from_annotation, [SampleDataclass, "stub_int", {"strict": True}], {}),
    ]
)
def test_schema_adapter_constructors(ctor, args, kwargs):
    adapter = ctor(*args, **kwargs)
    adapter.validate_schema()
    assert isinstance(adapter.type_adapter, pydantic.TypeAdapter)


def test_schema_adapter_is_bound():
    adapter = types.SchemaAdapter(None, None, None, None)
    with pytest.raises(types.ImproperlyConfiguredSchema):
        adapter.validate_schema()  # Schema cannot be resolved for fully unbound adapter

    adapter = types.SchemaAdapter(ty.List[int], None, None, None)
    assert not adapter.is_bound, "SchemaAdapter should not be bound"
    adapter.validate_schema()  # Schema should be resolved from direct argument

    adapter.bind(InnerSchema, "stub_int")
    assert adapter.is_bound, "SchemaAdapter should be bound"
    adapter.validate_schema()  # Schema should be resolved from direct argument

    adapter = types.SchemaAdapter(None, None, InnerSchema, "stub_int")
    assert adapter.is_bound, "SchemaAdapter should be bound"
    adapter.validate_schema()  # Schema should be resolved from bound attribute


@pytest.mark.parametrize(
    "kwargs, expected_export_kwargs",
    [
        ({}, {}),
        ({"strict": True}, {"strict": True}),
        ({"strict": True, "by_alias": False}, {"strict": True, "by_alias": False}),
        ({"strict": True, "from_attributes": False, "on_delete": "CASCADE"}, {"strict": True, "from_attributes": False}),
    ],
)
def test_schema_adapter_extract_export_kwargs(kwargs, expected_export_kwargs):
    orig_kwargs = dict(kwargs)
    assert types.SchemaAdapter.extract_export_kwargs(kwargs) == expected_export_kwargs
    assert kwargs == {key: orig_kwargs[key] for key in orig_kwargs.keys() - expected_export_kwargs.keys()}


def test_schema_adapter_validate_python():
    adapter = types.SchemaAdapter.from_type(ty.List[int])
    assert adapter.validate_python([1, 2, 3]) == [1, 2, 3]
    assert adapter.validate_python([1, 2, 3], strict=True) == [1, 2, 3]
    assert adapter.validate_python([1, 2, 3], strict=False) == [1, 2, 3]

    adapter = types.SchemaAdapter.from_type(ty.List[int], {"strict": True})
    assert adapter.validate_python([1, 2, 3]) == [1, 2, 3]
    assert adapter.validate_python(["1", "2", "3"], strict=False) == [1, 2, 3]
    assert sorted(adapter.validate_python({1, 2, 3}, strict=False)) == [1, 2, 3]
    with pytest.raises(pydantic.ValidationError):
        assert adapter.validate_python(["1", "2", "3"]) == [1, 2, 3]

    adapter = types.SchemaAdapter.from_type(ty.List[int], {"strict": False})
    assert adapter.validate_python([1, 2, 3]) == [1, 2, 3]
    assert adapter.validate_python([1, 2, 3], strict=False) == [1, 2, 3]
    assert sorted(adapter.validate_python({1, 2, 3})) == [1, 2, 3]
    with pytest.raises(pydantic.ValidationError):
        assert adapter.validate_python({1, 2, 3}, strict=True) == [1, 2, 3]


def test_schema_adapter_validate_json():
    adapter = types.SchemaAdapter.from_type(ty.List[int])
    assert adapter.validate_json("[1, 2, 3]") == [1, 2, 3]
    assert adapter.validate_json("[1, 2, 3]", strict=True) == [1, 2, 3]
    assert adapter.validate_json("[1, 2, 3]", strict=False) == [1, 2, 3]

    adapter = types.SchemaAdapter.from_type(ty.List[int], {"strict": True})
    assert adapter.validate_json("[1, 2, 3]") == [1, 2, 3]
    assert adapter.validate_json('["1", "2", "3"]', strict=False) == [1, 2, 3]
    with pytest.raises(pydantic.ValidationError):
        assert adapter.validate_json('["1", "2", "3"]') == [1, 2, 3]

    adapter = types.SchemaAdapter.from_type(ty.List[int], {"strict": False})
    assert adapter.validate_json("[1, 2, 3]") == [1, 2, 3]
    assert adapter.validate_json("[1, 2, 3]", strict=False) == [1, 2, 3]
    with pytest.raises(pydantic.ValidationError):
        assert adapter.validate_json('["1", "2", "3"]', strict=True) == [1, 2, 3]


def test_schema_adapter_dump_python():
    adapter = types.SchemaAdapter.from_type(ty.List[int])
    assert adapter.dump_python([1, 2, 3]) == [1, 2, 3]

    adapter = types.SchemaAdapter.from_type(ty.List[int], {})
    assert adapter.dump_python([1, 2, 3]) == [1, 2, 3]
    assert sorted(adapter.dump_python({1, 2, 3})) == [1, 2, 3]
    with pytest.warns(UserWarning):
        assert adapter.dump_python(["1", "2", "3"]) == ["1", "2", "3"]

    adapter = types.SchemaAdapter.from_type(ty.List[int], {})
    assert adapter.dump_python([1, 2, 3]) == [1, 2, 3]
    assert sorted(adapter.dump_python({1, 2, 3})) == [1, 2, 3]
    with pytest.warns(UserWarning):
        assert adapter.dump_python(["1", "2", "3"]) == ["1", "2", "3"]


def test_schema_adapter_dump_json():
    adapter = types.SchemaAdapter.from_type(ty.List[int])
    assert adapter.dump_json([1, 2, 3]) == b"[1,2,3]"

    adapter = types.SchemaAdapter.from_type(ty.List[int], {})
    assert adapter.dump_json([1, 2, 3]) == b"[1,2,3]"
    assert adapter.dump_json({1, 2, 3}) == b"[1,2,3]"
    with pytest.warns(UserWarning):
        assert adapter.dump_json(["1", "2", "3"]) == b'["1","2","3"]'

    adapter = types.SchemaAdapter.from_type(ty.List[int], {})
    assert adapter.dump_json([1, 2, 3]) == b"[1,2,3]"
    assert adapter.dump_json({1, 2, 3}) == b"[1,2,3]"
    with pytest.warns(UserWarning):
        assert adapter.dump_json(["1", "2", "3"]) == b'["1","2","3"]'
