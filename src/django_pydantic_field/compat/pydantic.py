import typing as ty

import pydantic
from pydantic.version import VERSION as PYDANTIC_VERSION

__all__ = ("PYDANTIC_V2", "PYDANTIC_V1", "PYDANTIC_VERSION", "ConfigType")

PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")
PYDANTIC_V1 = PYDANTIC_VERSION.startswith("1.")

if PYDANTIC_V2:
    from pydantic import v1 as pydantic_v1  # type: ignore[unresolved-import]

    ConfigType = ty.Union[
        pydantic.ConfigDict,
        pydantic_v1.ConfigDict,
        ty.Type[pydantic_v1.BaseConfig],
        ty.Type,
        ty.Any,
    ]
else:
    ConfigType = ty.Union[
        pydantic.ConfigDict,
        ty.Type[pydantic.BaseConfig],
    ]
