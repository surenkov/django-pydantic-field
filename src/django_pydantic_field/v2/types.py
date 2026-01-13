from __future__ import annotations

import typing as ty
from collections import ChainMap
from functools import cached_property

import pydantic
import typing_extensions as te

from django_pydantic_field.compat import deprecation
from django_pydantic_field.types import ST, BaseSchemaAdapter

if ty.TYPE_CHECKING:
    from pydantic.type_adapter import IncEx

    ModelType = ty.Type[pydantic.BaseModel]


class ExportKwargs(te.TypedDict, total=False):
    strict: bool
    from_attributes: bool
    mode: ty.Literal["json", "python"]
    include: IncEx | None
    exclude: IncEx | None
    by_alias: bool
    exclude_unset: bool
    exclude_defaults: bool
    exclude_none: bool
    round_trip: bool
    warnings: bool


class SchemaAdapter(BaseSchemaAdapter[ST]):
    @staticmethod
    def extract_export_kwargs(kwargs: dict[str, ty.Any]) -> ExportKwargs:
        """Extract the export kwargs from the kwargs passed to the field.
        This method mutates passed kwargs by removing those that are used by the adapter."""
        deprecation.truncate_deprecated_v1_export_kwargs(kwargs)
        common_keys = kwargs.keys() & ExportKwargs.__annotations__.keys()
        export_kwargs = {key: kwargs.pop(key) for key in common_keys}
        return ty.cast("ExportKwargs", export_kwargs)

    @cached_property
    def type_adapter(self) -> pydantic.TypeAdapter:
        schema = self.prepared_schema
        if self.allow_null:
            schema = ty.Optional[schema]
        return pydantic.TypeAdapter(schema, config=self.config)

    def bind(self, parent_type: type | None, attname: str | None) -> te.Self:
        """Bind the adapter to specific attribute of a `parent_type`."""
        super().bind(parent_type, attname)
        self.__dict__.pop("type_adapter", None)
        return self

    def validate_python(
        self,
        value: ty.Any,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        **kwargs: ty.Any,
    ) -> ST:
        """Validate the value and raise an exception if it is invalid."""
        if strict is None:
            strict = self.export_kwargs.get("strict", None)
        if from_attributes is None:
            from_attributes = self.export_kwargs.get("from_attributes", None)
        return self.type_adapter.validate_python(value, strict=strict, from_attributes=from_attributes)

    def validate_json(self, value: str | bytes, strict: bool | None = None, **kwargs: ty.Any) -> ST:
        if strict is None:
            strict = self.export_kwargs.get("strict", None)
        return self.type_adapter.validate_json(value, strict=strict)

    def dump_python(self, value: ty.Any, **override_kwargs: te.Unpack[ExportKwargs]) -> ty.Any:
        """Dump the value to a Python object."""
        union_kwargs = ChainMap(override_kwargs, self._dump_python_kwargs, {"mode": "json"})
        return self.type_adapter.dump_python(value, **union_kwargs)

    def dump_json(self, value: ty.Any, **override_kwargs: te.Unpack[ExportKwargs]) -> bytes:
        union_kwargs = ChainMap(override_kwargs, self._dump_python_kwargs)
        return self.type_adapter.dump_json(value, **union_kwargs)

    def json_schema(self) -> dict[str, ty.Any]:
        """Return the JSON schema for the field."""
        by_alias = self.export_kwargs.get("by_alias", True)
        return self.type_adapter.json_schema(by_alias=by_alias)

    def get_default_value(self) -> ST | None:
        wrapped = self.type_adapter.get_default_value()
        if wrapped is not None:
            return wrapped.value
        return None

    @cached_property
    def _dump_python_kwargs(self) -> dict[str, ty.Any]:
        export_kwargs = self.export_kwargs.copy()
        export_kwargs.pop("strict", None)
        export_kwargs.pop("from_attributes", None)
        return ty.cast(dict, export_kwargs)
