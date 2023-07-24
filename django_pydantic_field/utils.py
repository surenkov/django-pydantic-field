from __future__ import annotations

import sys
import typing as t

from pydantic.config import BaseConfig, inherit_config

if t.TYPE_CHECKING:
    from pydantic import BaseModel


def get_annotated_type(obj, field, default=None) -> t.Any:
    try:
        if isinstance(obj, type):
            annotations = obj.__dict__["__annotations__"]
        else:
            annotations = obj.__annotations__

        return annotations[field]
    except (AttributeError, KeyError):
        return default


def get_local_namespace(cls) -> t.Dict[str, t.Any]:
    try:
        module = cls.__module__
        return vars(sys.modules[module])
    except (KeyError, AttributeError):
        return {}


def inherit_configs(parent: t.Type[BaseModel], config: t.Type | dict | None = None) -> t.Type[BaseConfig]:
    parent_config = t.cast(t.Type[BaseConfig], getattr(parent, "Config", BaseConfig))
    if config is None:
        return parent_config
    if isinstance(config, dict):
        config = type("Config", (BaseConfig,), config)
    return inherit_config(config, parent_config)
