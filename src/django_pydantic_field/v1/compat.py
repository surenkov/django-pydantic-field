import sys
import typing as ty

from django_pydantic_field.compat.pydantic import PYDANTIC_V1

if sys.version_info >= (3, 14):
    pydantic_v1: ty.Any = None
    inherit_config: ty.Any = None
    display_as_type: ty.Any = None
elif PYDANTIC_V1:
    import pydantic as pydantic_v1
    from pydantic.config import inherit_config
    from pydantic.typing import display_as_type
else:
    from pydantic import v1 as pydantic_v1
    from pydantic.v1.config import inherit_config
    from pydantic.v1.typing import display_as_type

__all__ = ("display_as_type", "inherit_config", "pydantic_v1")
