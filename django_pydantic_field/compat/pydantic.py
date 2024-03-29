from pydantic.version import VERSION as PYDANTIC_VERSION

__all__ = ("PYDANTIC_V2", "PYDANTIC_V1", "PYDANTIC_VERSION")

PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")
PYDANTIC_V1 = PYDANTIC_VERSION.startswith("1.")
