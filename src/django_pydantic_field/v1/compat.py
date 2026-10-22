import typing as ty

from django_pydantic_field.compat.pydantic import PYDANTIC_V1

if ty.TYPE_CHECKING:
    import pydantic.v1 as pydantic_v1
    from pydantic.v1.config import inherit_config
    from pydantic.v1.typing import display_as_type
elif PYDANTIC_V1:
    import pydantic as pydantic_v1
    from pydantic.config import inherit_config
    from pydantic.typing import display_as_type
else:
    try:
        from pydantic import v1 as pydantic_v1
        from pydantic.v1.config import inherit_config
        from pydantic.v1.typing import display_as_type
    except (ImportError, AttributeError):
        pydantic_v1 = None
        inherit_config = None
        display_as_type = None

__all__ = ("display_as_type", "inherit_config", "pydantic_v1")
