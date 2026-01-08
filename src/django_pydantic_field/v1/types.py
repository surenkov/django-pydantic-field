from __future__ import annotations

import typing as ty
import json
from collections import ChainMap

import pydantic
import typing_extensions as te

from django_pydantic_field.compat.django import GenericContainer
from django_pydantic_field.compat.functools import cached_property
from django_pydantic_field.v1 import utils, base

from django_pydantic_field.types import BaseSchemaAdapter, ST


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
        return ty.cast(ExportKwargs, export_kwargs)

    def bind(self, parent_type: type | None, attname: str | None) -> te.Self:
        """Bind the adapter to specific attribute of a `parent_type`."""
        super().bind(parent_type, attname)
        self.__dict__.pop("wrapper_model", None)
        return self

    def validate_python(self, value: ty.Any, **kwargs: ty.Any) -> ST:
        model = self.wrapper_model
        return model.parse_obj(value).__root__

    def validate_json(self, value: str | bytes, **kwargs: ty.Any) -> ST:
        model = self.wrapper_model
        return model.parse_raw(value).__root__

    def dump_python(self, value: ty.Any, mode: str = "python", **override_kwargs) -> ty.Any:
        union_kwargs = ChainMap(override_kwargs, self.export_kwargs)
        if union_kwargs.get("round_trip"):
            union_kwargs = union_kwargs.new_child({"exclude_unset": True})

        dict_kwargs = {
            k: v
            for k, v in union_kwargs.items()
            if k
            in ("include", "exclude", "by_alias", "skip_defaults", "exclude_unset", "exclude_defaults", "exclude_none")
        }

        if "include" in dict_kwargs and dict_kwargs["include"] is not None:
            dict_kwargs["include"] = {"__root__": dict_kwargs["include"]}
        if "exclude" in dict_kwargs and dict_kwargs["exclude"] is not None:
            dict_kwargs["exclude"] = {"__root__": dict_kwargs["exclude"]}

        model_instance: pydantic.BaseModel = self.wrapper_model.parse_obj(value)
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

        model_instance = self.wrapper_model.parse_obj(value)
        return model_instance.json(**json_kwargs).encode()

    def json_schema(self) -> dict[str, ty.Any]:
        by_alias = self.export_kwargs.get("by_alias", True)
        schema = self.wrapper_model.schema(by_alias=by_alias)
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
        field = self.wrapper_model.__fields__["__root__"]
        if not field.required:
            return field.default
        return None

    @cached_property
    def wrapper_model(self) -> ty.Type[pydantic.BaseModel]:
        schema = self.prepared_schema
        config = self.config

        type_name = base._get_field_schema_name(schema)
        params = base._get_field_schema_params(schema, config, allow_null=self.allow_null)
        model = pydantic.create_model(type_name, **params)
        base.prepare_schema(model, self.parent_type)
        return model

    def guess_schema_from_annotations(self):
        return utils.get_annotated_type(self.parent_type, self.attname)

    def resolve_schema_forward_ref(self, schema):
        if schema is None:
            return None

        if isinstance(schema, ty.ForwardRef):
            globalns = utils.get_local_namespace(self.parent_type)
            from pydantic.typing import evaluate_forwardref

            try:
                return evaluate_forwardref(schema, globalns, globalns)
            except NameError:
                # Fallback to the forward ref itself if it cannot be resolved yet
                return schema

        from django_pydantic_field.compat.typing import get_args, get_origin

        origin = get_origin(schema)
        if origin is None:
            return schema

        args = get_args(schema)
        new_args = tuple(self.resolve_schema_forward_ref(arg) for arg in args)
        if all(a is b for a, b in zip(args, new_args)):
            return schema

        return GenericContainer.unwrap(GenericContainer(origin, new_args))
