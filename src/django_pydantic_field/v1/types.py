from __future__ import annotations

import json
import typing as ty
from collections import ChainMap
from functools import cached_property

import typing_extensions as te

from django_pydantic_field.compat.pydantic import pydantic_v1
from django_pydantic_field.types import ST, BaseSchemaAdapter, SchemaAdapterResolver
from django_pydantic_field.v1 import schema_utils


class ExportKwargs(te.TypedDict, total=False):
    include: ty.Optional[ty.Union[ty.Set[int], ty.Set[str], ty.Dict[int, ty.Any], ty.Dict[str, ty.Any]]]
    exclude: ty.Optional[ty.Union[ty.Set[int], ty.Set[str], ty.Dict[int, ty.Any], ty.Dict[str, ty.Any]]]
    by_alias: bool
    exclude_unset: bool
    exclude_defaults: bool
    exclude_none: bool
    skipkeys: bool
    indent: ty.Optional[int]
    separators: ty.Optional[ty.Tuple[str, str]]
    allow_nan: bool
    sort_keys: bool


class SchemaAdapter(BaseSchemaAdapter[ST]):
    @staticmethod
    def extract_export_kwargs(kwargs: dict) -> ExportKwargs:
        common_keys = kwargs.keys() & ExportKwargs.__annotations__.keys()
        export_kwargs = {key: kwargs.pop(key) for key in common_keys}
        return ty.cast("ExportKwargs", export_kwargs)

    def bind(self, parent_type: type | None, attname: str | None) -> te.Self:
        """Bind the adapter to specific attribute of a `parent_type`."""
        super().bind(parent_type, attname)
        self.__dict__.pop("wrapped_schema", None)
        return self

    def validate_python(self, value: ty.Any, **kwargs: ty.Any) -> ST:
        model = self.wrapped_schema
        return model.parse_obj(value).__root__

    def validate_json(self, value: str | bytes, **kwargs: ty.Any) -> ST:
        model = self.wrapped_schema
        return model.parse_raw(value).__root__

    def dump_python(self, value: ty.Any, mode: str = "python", **override_kwargs) -> ty.Any:
        dict_kwargs = ChainMap(override_kwargs, self.export_kwargs)

        if dict_kwargs.get("round_trip"):
            dict_kwargs.pop("round_trip", None)
            dict_kwargs = dict_kwargs.new_child({"exclude_unset": True})

        include_fields = dict_kwargs.get("include", None)
        exclude_fields = dict_kwargs.get("exclude", None)

        if include_fields is not None:
            dict_kwargs["include"] = {"__root__": dict_kwargs["include"]}
        if exclude_fields is not None:
            dict_kwargs["exclude"] = {"__root__": dict_kwargs["exclude"]}

        model_instance = self.wrapped_schema.parse_obj(value)
        if mode == "json":
            return json.loads(model_instance.json(**dict_kwargs))

        return model_instance.dict(**dict_kwargs)["__root__"]

    def dump_json(self, value: ty.Any, **override_kwargs) -> bytes:
        union_kwargs = ChainMap(override_kwargs, self.export_kwargs)
        json_kwargs = {k: v for k, v in union_kwargs.items() if k in ExportKwargs.__annotations__}

        if "include" in json_kwargs and json_kwargs["include"] is not None:
            json_kwargs["include"] = {"__root__": json_kwargs["include"]}
        if "exclude" in json_kwargs and json_kwargs["exclude"] is not None:
            json_kwargs["exclude"] = {"__root__": json_kwargs["exclude"]}

        model_instance = self.wrapped_schema.parse_obj(value)
        return model_instance.json(**json_kwargs).encode()

    def json_schema(self) -> dict[str, ty.Any]:
        by_alias = self.export_kwargs.get("by_alias", True)
        schema = self.wrapped_schema.schema(by_alias=by_alias)
        definitions = schema.get("definitions", {})

        if "properties" in schema and "__root__" in schema["properties"]:
            root_schema = schema["properties"]["__root__"]
        else:
            root_schema = schema

        root_schema = root_schema.copy()
        if definitions:
            root_schema["definitions"] = definitions

        return root_schema

    def get_default_value(self) -> ST | None:
        field = self.wrapped_schema.__fields__["__root__"]
        if not field.required:
            return field.default
        return None

    @cached_property
    def wrapped_schema(self) -> ty.Type[pydantic_v1.BaseModel]:
        return schema_utils.prepare_schema(self.prepared_schema, self.config, self.allow_null, owner=self.parent_type)


class V1SchemaAdapterResolver(SchemaAdapterResolver):
    @classmethod
    def get_schema_adapter_class(cls):
        return SchemaAdapter
