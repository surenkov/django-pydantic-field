from __future__ import annotations

import typing as ty
import typing_extensions as te
from collections import ChainMap

import pydantic

from . import utils
from ..compat.django import GenericContainer

ST = ty.TypeVar("ST", bound="SchemaT")

if ty.TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic.type_adapter import IncEx
    from pydantic.dataclasses import DataclassClassOrWrapper
    from django.db.models import Model

    ModelType = ty.Type[pydantic.BaseModel]
    DjangoModelType = ty.Type[Model]
    SchemaT = ty.Union[
        pydantic.BaseModel,
        DataclassClassOrWrapper,
        ty.Sequence[ty.Any],
        ty.Mapping[str, ty.Any],
        ty.Set[ty.Any],
        ty.FrozenSet[ty.Any],
    ]


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


class SchemaAdapter(ty.Generic[ST]):
    def __init__(
        self,
        schema: ty.Any,
        config: pydantic.ConfigDict | None,
        parent_type: type | None,
        attname: str | None,
        allow_null: bool | None = None,
        **export_kwargs: ty.Unpack[ExportKwargs],
    ):
        self.schema = schema
        self.config = config
        self.parent_type = parent_type
        self.attname = attname
        self.allow_null = allow_null
        self.export_kwargs = export_kwargs

    @staticmethod
    def extract_export_kwargs(kwargs: dict[str, ty.Any]) -> ExportKwargs:
        common_keys = kwargs.keys() & ExportKwargs.__annotations__.keys()
        export_kwargs = {key: kwargs.pop(key) for key in common_keys}
        return ty.cast(ExportKwargs, export_kwargs)

    @utils.cached_property
    def type_adapter(self) -> pydantic.TypeAdapter:
        return pydantic.TypeAdapter(self.prepared_schema, config=self.config)  # type: ignore

    @property
    def is_bound(self) -> bool:
        return self.parent_type is not None and self.attname is not None

    def bind(self, parent_type: type, attname: str) -> None:
        self.parent_type = parent_type
        self.attname = attname
        self.__dict__.pop("prepared_schema", None)
        self.__dict__.pop("type_adapter", None)

    def validate_schema(self) -> None:
        """Validate the schema and raise an exception if it is invalid."""
        self.prepared_schema()

    def validate_python(self, value: ty.Any, *, strict: bool | None = None, from_attributes: bool | None = None) -> ST:
        """Validate the value and raise an exception if it is invalid."""
        if strict is None:
            strict = self.export_kwargs.get("strict", None)
        if from_attributes is None:
            from_attributes = self.export_kwargs.get("from_attributes", None)
        return self.type_adapter.validate_python(value, strict=strict, from_attributes=from_attributes)

    def validate_json(self, value: str | bytes, *, strict: bool | None = None) -> ST:
        if strict is None:
            strict = self.export_kwargs.get("strict", None)
        return self.type_adapter.validate_json(value, strict=strict)

    def dump_python(self, value: ty.Any) -> ty.Any:
        """Dump the value to a Python object."""
        return self.type_adapter.dump_python(value, **self._dump_python_kwargs)

    def dump_json(self, value: ty.Any) -> bytes:
        return self.type_adapter.dump_json(value, **self._dump_python_kwargs)

    def json_schema(self) -> ty.Any:
        """Return the JSON schema for the field."""
        by_alias = self.export_kwargs.get("by_alias", True)
        return self.type_adapter.json_schema(by_alias=by_alias)

    @utils.cached_property
    def prepared_schema(self) -> type[ST]:
        schema = self.schema

        if schema is None and self.attname is not None:
            schema = self._guess_schema_from_annotations()
        if isinstance(schema, GenericContainer):
            schema = ty.cast(ty.Type[ST], GenericContainer.unwrap(schema))
        if isinstance(schema, (str, ty.ForwardRef)):
            schema = self._resolve_schema_forward_ref(schema)

        if schema is None:
            if self.parent_type is not None and self.attname is not None:
                error_msg = f"Schema not provided for {self.parent_type.__name__}.{self.attname}"
            else:
                error_msg = "The adapter is accessed before it was bound"
            raise ValueError(error_msg)

        if self.allow_null:
            schema = ty.Optional[schema]

        return ty.cast(ty.Type[ST], schema)

    def _guess_schema_from_annotations(self) -> type[ST] | str | ty.ForwardRef | None:
        return utils.get_annotated_type(self.parent_type, self.attname)

    def _resolve_schema_forward_ref(self, schema: str | ty.ForwardRef) -> ty.Any:
        if isinstance(schema, str):
            schema = ty.ForwardRef(schema)

        globalns = utils.get_namespace(self.parent_type)
        return utils.evaluate_forward_ref(schema, globalns)

    @utils.cached_property
    def _dump_python_kwargs(self) -> dict[str, ty.Any]:
        export_kwargs = self.export_kwargs.copy()
        export_kwargs.pop("strict", None)
        return ty.cast(dict, export_kwargs)
