import sys
import typing as ty

import pydantic
from pydantic.version import VERSION as PYDANTIC_VERSION

PYDANTIC_V1 = PYDANTIC_VERSION.startswith("1.")
PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

if PYDANTIC_V1:
    import pydantic as pydantic_v1

    ValidationErrorsTuple = (pydantic_v1.ValidationError,)
    ConfigType = ty.Union[
        pydantic.ConfigDict,
        ty.Type[pydantic_v1.BaseConfig],
    ]
elif sys.version_info >= (3, 14):
    ValidationErrorsTuple = (pydantic.ValidationError,)
    ConfigType = ty.Union[
        pydantic.ConfigDict,
        ty.Type,
        ty.Any,
    ]
else:
    from pydantic import v1 as pydantic_v1

    ValidationErrorsTuple = (pydantic.ValidationError, pydantic_v1.ValidationError)
    ConfigType = ty.Union[
        pydantic.ConfigDict,
        pydantic_v1.ConfigDict,
        ty.Type[pydantic_v1.BaseConfig],
        ty.Type,
        ty.Any,
    ]
