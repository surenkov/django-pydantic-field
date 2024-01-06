from __future__ import annotations

import typing as ty
from collections import ChainMap

import pydantic
import typing_extensions as te

from django_pydantic_field.compat.django import GenericContainer
from django_pydantic_field.compat.functools import cached_property
from . import utils

if ty.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from django.db.models import Model
    from pydantic.dataclasses import DataclassClassOrWrapper
    from pydantic.type_adapter import IncEx

    ModelType = ty.Type[pydantic.BaseModel]
    DjangoModelType = ty.Type[Model]
    SchemaT = ty.Union[
        pydantic.BaseModel,
        DataclassClassOrWrapper,
        Sequence[ty.Any],
        Mapping[str, ty.Any],
        set[ty.Any],
        frozenset[ty.Any],
    ]

ST = ty.TypeVar("ST", bound="SchemaT")


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


class ImproperlyConfiguredSchema(ValueError):
    """Raised when the schema is improperly configured."""


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
        self.schema = GenericContainer.unwrap(schema)
        self.config = config
        self.parent_type = parent_type
        self.attname = attname
        self.allow_null = allow_null
        self.export_kwargs = export_kwargs

    @classmethod
    def from_type(
        cls,
        schema: ty.Any,
        config: pydantic.ConfigDict | None = None,
        **kwargs: ty.Unpack[ExportKwargs],
    ) -> SchemaAdapter[ST]:
        """Create an adapter from a type."""
        return cls(schema, config, None, None, **kwargs)

    @classmethod
    def from_annotation(
        cls,
        parent_type: type,
        attname: str,
        config: pydantic.ConfigDict | None = None,
        **kwargs: ty.Unpack[ExportKwargs],
    ) -> SchemaAdapter[ST]:
        """Create an adapter from a type annotation."""
        return cls(None, config, parent_type, attname, **kwargs)

    @staticmethod
    def extract_export_kwargs(kwargs: dict[str, ty.Any]) -> ExportKwargs:
        """Extract the export kwargs from the kwargs passed to the field.
        This method mutates passed kwargs by removing those that are used by the adapter."""
        common_keys = kwargs.keys() & ExportKwargs.__annotations__.keys()
        export_kwargs = {key: kwargs.pop(key) for key in common_keys}
        return ty.cast(ExportKwargs, export_kwargs)

    @cached_property
    def type_adapter(self) -> pydantic.TypeAdapter:
        return pydantic.TypeAdapter(self.prepared_schema, config=self.config)  # type: ignore

    @property
    def is_bound(self) -> bool:
        """Return True if the adapter is bound to a specific attribute of a `parent_type`."""
        return self.parent_type is not None and self.attname is not None

    def bind(self, parent_type: type | None, attname: str | None) -> te.Self:
        """Bind the adapter to specific attribute of a `parent_type`."""
        self.parent_type = parent_type
        self.attname = attname
        self.__dict__.pop("prepared_schema", None)
        self.__dict__.pop("type_adapter", None)
        return self

    def validate_schema(self) -> None:
        """Validate the schema and raise an exception if it is invalid."""
        try:
            self._prepare_schema()
        except Exception as exc:
            if not isinstance(exc, ImproperlyConfiguredSchema):
                raise ImproperlyConfiguredSchema(*exc.args) from exc
            raise

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

    def dump_python(self, value: ty.Any, **override_kwargs: ty.Unpack[ExportKwargs]) -> ty.Any:
        """Dump the value to a Python object."""
        union_kwargs = ChainMap(override_kwargs, self._dump_python_kwargs)  # type: ignore
        return self.type_adapter.dump_python(value, **union_kwargs)

    def dump_json(self, value: ty.Any, **override_kwargs: ty.Unpack[ExportKwargs]) -> bytes:
        union_kwargs = ChainMap(override_kwargs, self._dump_python_kwargs)  # type: ignore
        return self.type_adapter.dump_json(value, **union_kwargs)

    def json_schema(self) -> dict[str, ty.Any]:
        """Return the JSON schema for the field."""
        by_alias = self.export_kwargs.get("by_alias", True)
        return self.type_adapter.json_schema(by_alias=by_alias)

    def _prepare_schema(self) -> type[ST]:
        """Prepare the schema for the adapter.

        This method is called by `prepared_schema` property and should not be called directly.
        The intent is to resolve the real schema from an annotations or a forward references.
        """
        schema = self.schema

        if schema is None and self.is_bound:
            schema = self._guess_schema_from_annotations()
        if isinstance(schema, str):
            schema = ty.ForwardRef(schema)

        schema = self._resolve_schema_forward_ref(schema)
        if schema is None:
            if self.is_bound:
                error_msg = f"Annotation is not provided for {self.parent_type.__name__}.{self.attname}"  # type: ignore[union-attr]
            else:
                error_msg = "Cannot resolve the schema. The adapter is accessed before it was bound."
            raise ImproperlyConfiguredSchema(error_msg)

        if self.allow_null:
            schema = ty.Optional[schema]  # type: ignore

        return ty.cast(ty.Type[ST], schema)

    prepared_schema = cached_property(_prepare_schema)

    def __copy__(self):
        instance = self.__class__(
            self.schema,
            self.config,
            self.parent_type,
            self.attname,
            self.allow_null,
            **self.export_kwargs,
        )
        instance.__dict__.update(self.__dict__)
        return instance

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(bound={self.is_bound}, schema={self.schema!r}, config={self.config!r})"

    def __eq__(self, other: ty.Any) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented

        self_fields: list[ty.Any] = [self.attname, self.export_kwargs]
        other_fields: list[ty.Any] = [other.attname, other.export_kwargs]
        try:
            self_fields.append(self.prepared_schema)
            other_fields.append(other.prepared_schema)
        except ImproperlyConfiguredSchema:
            if self.is_bound and other.is_bound:
                return False
            else:
                self_fields.extend((self.schema, self.config, self.allow_null))
                other_fields.extend((other.schema, other.config, other.allow_null))

        return self_fields == other_fields

    def _guess_schema_from_annotations(self) -> type[ST] | str | ty.ForwardRef | None:
        return utils.get_annotated_type(self.parent_type, self.attname)

    def _resolve_schema_forward_ref(self, schema: ty.Any) -> ty.Any:
        if schema is None:
            return None

        if isinstance(schema, ty.ForwardRef):
            globalns = utils.get_namespace(self.parent_type)
            return utils.evaluate_forward_ref(schema, globalns)

        wrapped_schema = GenericContainer.wrap(schema)
        if not isinstance(wrapped_schema, GenericContainer):
            return schema

        origin = self._resolve_schema_forward_ref(wrapped_schema.origin)
        args = map(self._resolve_schema_forward_ref, wrapped_schema.args)
        return GenericContainer.unwrap(GenericContainer(origin, tuple(args)))

    @cached_property
    def _dump_python_kwargs(self) -> dict[str, ty.Any]:
        export_kwargs = self.export_kwargs.copy()
        export_kwargs.pop("strict", None)
        export_kwargs.pop("from_attributes", None)
        return ty.cast(dict, export_kwargs)
