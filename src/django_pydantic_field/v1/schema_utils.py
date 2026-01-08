from __future__ import annotations

import typing as ty

import pydantic
from pydantic.config import BaseConfig, inherit_config
from pydantic.typing import display_as_type

from django_pydantic_field._internal._annotation_utils import get_namespace
from django_pydantic_field.compat.pydantic import ConfigType

if ty.TYPE_CHECKING:
    from pydantic import BaseModel


def inherit_configs(parent: ty.Type[BaseModel], config: ConfigType | None = None):
    parent_config = ty.cast(ty.Type[BaseConfig], getattr(parent, "Config", BaseConfig))
    if config is None:
        return parent_config
    if isinstance(config, dict):
        config = type("Config", (BaseConfig,), config)  # type: ignore[invalid-argument-type]
    return inherit_config(ty.cast(ty.Type[BaseConfig], config), parent_config)


def get_field_schema_name(schema) -> str:
    return f"FieldSchema[{display_as_type(schema)}]"


def prepare_schema(
    schema: ty.Type[pydantic.BaseModel],
    config: ty.Any | None = None,
    allow_null: bool | None = None,
    owner: ty.Any = None,
) -> ty.Type[pydantic.BaseModel]:
    type_name = get_field_schema_name(schema)
    wrapped_schema = pydantic.create_model(
        type_name,
        __root__=(ty.Optional[schema] if allow_null else schema, ...),
        __config__=inherit_configs(schema, config),
    )

    namespace = get_namespace(owner)
    wrapped_schema.update_forward_refs(**namespace)  # type: ignore[deprecated]
    return wrapped_schema
