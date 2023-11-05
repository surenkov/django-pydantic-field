from __future__ import annotations

import functools
import typing as ty

from pydantic.type_adapter import TypeAdapter

from . import utils
from ..compat.django import GenericContainer

ST = ty.TypeVar("ST", bound="SchemaT")

if ty.TYPE_CHECKING:
    from pydantic import BaseModel
    from pydantic.type_adapter import IncEx
    from pydantic.dataclasses import DataclassClassOrWrapper
    from django.db.models import Model

    ModelType = ty.Type[BaseModel]
    DjangoModelType = ty.Type[Model]
    SchemaT = ty.Union[
        BaseModel,
        DataclassClassOrWrapper,
        ty.Sequence[ty.Any],
        ty.Mapping[str, ty.Any],
        ty.Set[ty.Any],
        ty.FrozenSet[ty.Any],
    ]

class ExportKwargs(ty.TypedDict, total=False):
    strict: bool
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
        schema,
        config,
        parent_type,
        attname,
        allow_null,
        *,
        parent_depth=4,
        **export_kwargs: ty.Unpack[ExportKwargs],
    ):
        self.schema = schema
        self.config = config
        self.parent_type = parent_type
        self.attname = attname
        self.allow_null = allow_null
        self.parent_depth = parent_depth
        self.export_kwargs = export_kwargs

    @staticmethod
    def extract_export_kwargs(kwargs: dict[str, ty.Any]) -> ExportKwargs:
        common_keys = kwargs.keys() & ExportKwargs.__annotations__.keys()
        export_kwargs = {key: kwargs.pop(key) for key in common_keys}
        return ty.cast(ExportKwargs, export_kwargs)

    @functools.cached_property
    def type_adapter(self) -> TypeAdapter:
        schema = self._get_prepared_schema()
        return TypeAdapter(schema, config=self.config, _parent_depth=4)  # type: ignore

    def bind(self, parent_type, attname):
        self.parent_type = parent_type
        self.attname = attname
        self.__dict__.pop("type_adapter", None)

    def validate_schema(self) -> None:
        """Validate the schema and raise an exception if it is invalid."""
        self._get_prepared_schema()

    def validate_python(self, value: ty.Any, *, strict: bool | None = None) -> ST:
        """Validate the value and raise an exception if it is invalid."""
        if strict is None:
            strict = self.export_kwargs.get("strict", None)
        return self.type_adapter.validate_python(value, strict=strict)

    def dump_python(self, value: ty.Any) -> ty.Any:
        """Dump the value to a Python object."""
        return self.type_adapter.dump_python(value, **self._dump_python_kwargs)

    def json_schema(self) -> ty.Any:
        """Return the JSON schema for the field."""
        by_alias = self.export_kwargs.get("by_alias", True)
        return self.type_adapter.json_schema(by_alias=by_alias)

    def _get_prepared_schema(self) -> type[ST]:
        schema = self.schema

        if schema is None:
            schema = self._guess_schema_from_annotations()
        if isinstance(schema, GenericContainer):
            schema = ty.cast(type[ST], GenericContainer.unwrap(schema))
        if isinstance(schema, (str, ty.ForwardRef)):
            schema = self._resolve_schema_forward_ref(schema)

        if schema is None:
            error_msg = f"Schema not provided for {self.parent_type.__name__}.{self.attname}"
            raise ValueError(error_msg)

        if self.allow_null:
            schema = ty.Optional[schema]
        return ty.cast(type[ST], schema)

    def _guess_schema_from_annotations(self) -> type[ST] | str | ty.ForwardRef | None:
        return utils.get_annotated_type(self.parent_type, self.attname)

    def _resolve_schema_forward_ref(self, schema: str | ty.ForwardRef) -> ty.Any:
        if isinstance(schema, str):
            schema = ty.ForwardRef(schema)
        namespace = utils.get_local_namespace(self.parent_type)
        return schema._evaluate(namespace, vars(self.parent_type), frozenset())  # type: ignore

    @functools.cached_property
    def _dump_python_kwargs(self) -> dict[str, ty.Any]:
        export_kwargs = self.export_kwargs.copy()
        export_kwargs.pop("strict", None)
        return ty.cast(dict, export_kwargs)
