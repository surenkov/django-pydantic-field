from django_pydantic_field.compat.pydantic import PYDANTIC_V2

if not PYDANTIC_V2:
    raise ImportError("django_pydantic_field.v2 package is only compatible with Pydantic v2")
