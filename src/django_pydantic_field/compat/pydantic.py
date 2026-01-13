import typing as ty

import pydantic
from pydantic import ValidationError
from pydantic.version import VERSION as PYDANTIC_VERSION

PYDANTIC_V1 = PYDANTIC_VERSION.startswith("1.")
PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

if PYDANTIC_V1:
    import pydantic as pydantic_v1
    from pydantic.config import inherit_config
    from pydantic.typing import display_as_type

    ValidationErrorsTuple = (ValidationError,)

    ConfigType = ty.Union[
        pydantic.ConfigDict,
        ty.Type[pydantic_v1.BaseConfig],
    ]
else:
    from pydantic import v1 as pydantic_v1
    from pydantic.v1.config import inherit_config  # noqa: F401
    from pydantic.v1.typing import display_as_type  # noqa: F401

    ValidationErrorsTuple = (ValidationError, pydantic_v1.ValidationError)

    ConfigType = ty.Union[
        pydantic.ConfigDict,
        pydantic_v1.ConfigDict,
        ty.Type[pydantic_v1.BaseConfig],
        ty.Type,
        ty.Any,
    ]
