from __future__ import annotations

import abc
import operator as op
import typing as ty
from functools import cached_property

import typing_extensions as te

from django_pydantic_field._internal._annotation_utils import evaluate_forward_ref, get_annotated_type, get_namespace
from django_pydantic_field.compat.django import BaseContainer, GenericContainer
from django_pydantic_field.compat.pydantic import PYDANTIC_V1, ConfigType

if ty.TYPE_CHECKING:
    from django.db.models import Model

    from django_pydantic_field.v1.types import ExportKwargs as ExportKwargsV1
    from django_pydantic_field.v2.types import ExportKwargs as ExportKwargsV2

    DjangoModelType = type[Model]
    ExportKwargsT: te.TypeAlias = ty.Mapping[str, ty.Any]

    class ExportKwargs(ExportKwargsV2):
        pass

    class DeprecatedExportKwargs(ExportKwargsV1):
        pass


ST = ty.TypeVar("ST")


class ImproperlyConfiguredSchema(ValueError):
    """Raised when the schema is improperly configured."""


class BaseSchemaAdapter(abc.ABC, ty.Generic[ST]):
    """The base class for schema adapters that bridge Django fields and Pydantic models.

    Handles schema resolution, validation, and serialization.
    """

    def __init__(
        self,
        schema: ty.Any,
        config: ty.Any,
        parent_type: type | None,
        attname: str | None,
        allow_null: bool | None = None,
        **export_kwargs: ty.Any,
    ):
        self.schema = BaseContainer.unwrap(schema)
        self.config = config
        self.parent_type = parent_type
        self.attname = attname
        self.allow_null = allow_null
        self.export_kwargs = export_kwargs

    @classmethod
    def from_type(cls, schema: ty.Any, config: ty.Any = None, **kwargs: ty.Any) -> te.Self:
        """Create an adapter instance from a specific type/schema."""
        return cls(schema, config, None, None, **kwargs)

    @classmethod
    def from_annotation(cls, parent_type: type, attname: str, config: ty.Any = None, **kwargs: ty.Any) -> te.Self:
        """Create an adapter instance by looking up annotations on the parent type."""
        return cls(None, config, parent_type, attname, **kwargs)

    @staticmethod
    @abc.abstractmethod
    def extract_export_kwargs(kwargs: dict[str, ty.Any]) -> ExportKwargs | DeprecatedExportKwargs:
        """Extract the export-related arguments from the field's kwargs.
        This method should mutate the passed dictionary by removing the extracted keys."""
        raise NotImplementedError

    @abc.abstractmethod
    def validate_python(self, value: ty.Any, **kwargs: ty.Any) -> ST:
        """Validate the given Python object against the schema.
        Should raise a validation error (e.g., pydantic.ValidationError) if invalid.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def validate_json(self, value: str | bytes, **kwargs: ty.Any) -> ST:
        """Validate the given JSON string or bytes against the schema."""
        raise NotImplementedError

    @abc.abstractmethod
    def dump_python(self, value: ty.Any, **kwargs: ty.Any) -> ty.Any:
        """Serialize the given value to a Python-native object compatible with the schema."""
        raise NotImplementedError

    @abc.abstractmethod
    def dump_json(self, value: ty.Any, **kwargs: ty.Any) -> bytes:
        """Serialize the given value to a JSON-encoded byte string."""
        raise NotImplementedError

    @abc.abstractmethod
    def json_schema(self) -> dict[str, ty.Any]:
        """Generate a JSON schema representation of the underlying schema."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_default_value(self) -> ST | None:
        """Retrieve the default value from the schema if one is defined."""
        raise NotImplementedError

    @property
    def is_bound(self) -> bool:
        """Check if the adapter is bound to a specific model attribute."""
        return self.parent_type is not None and self.attname is not None

    def bind(self, parent_type: type | None, attname: str | None) -> te.Self:
        """Bind the adapter to a specific attribute of a parent type."""
        self.parent_type = parent_type
        self.attname = attname
        self.__dict__.pop("prepared_schema", None)
        return self

    def validate_schema(self) -> None:
        """Validate that the schema is properly configured and can be prepared."""
        try:
            self._prepare_schema()
        except Exception as exc:
            if not isinstance(exc, ImproperlyConfiguredSchema):
                raise ImproperlyConfiguredSchema(*exc.args) from exc
            raise

    prepared_schema = cached_property(op.methodcaller("_prepare_schema"))
    """The prepared and resolved schema."""

    def _prepare_schema(self) -> ty.Any:
        """Internal method to prepare the schema by guessing it from annotations if needed,
        resolving forward references, and wrapping it if necessary.
        """
        schema = self.schema
        if schema is None and self.is_bound:
            schema = get_annotated_type(self.parent_type, self.attname)
        if isinstance(schema, str):
            schema = ty.ForwardRef(schema)

        schema = self._resolve_schema_forward_ref(schema)
        if schema is None:
            if self.is_bound:
                error_msg = f"Annotation is not provided for {self.parent_type.__name__}.{self.attname}"
            else:
                error_msg = "Cannot resolve the schema. The adapter is accessed before it was bound."
            raise ImproperlyConfiguredSchema(error_msg)

        return schema

    def _resolve_schema_forward_ref(self, schema: ty.Any) -> ty.Any:
        if schema is None:
            return None

        if isinstance(schema, ty.ForwardRef):
            globalns = get_namespace(self.parent_type)
            return evaluate_forward_ref(schema, globalns)

        wrapped_schema = GenericContainer.wrap(schema)
        if not isinstance(wrapped_schema, GenericContainer):
            return schema

        origin = self._resolve_schema_forward_ref(wrapped_schema.origin)
        args = map(self._resolve_schema_forward_ref, wrapped_schema.args)
        return GenericContainer.unwrap(GenericContainer(origin, tuple(args)))

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
        if other is None or not isinstance(other, self.__class__):
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


class SchemaAdapterResolver(ty.Generic[ST]):
    @classmethod
    def get_schema_adapter_class(cls) -> type[BaseSchemaAdapter[ST]]:
        if PYDANTIC_V1:
            from django_pydantic_field.v1.types import SchemaAdapter
        else:
            from django_pydantic_field.v2.types import SchemaAdapter

        return SchemaAdapter


__all__ = (
    "ST",
    "BaseSchemaAdapter",
    "ConfigType",
    "DjangoModelType",
    "ImproperlyConfiguredSchema",
)
