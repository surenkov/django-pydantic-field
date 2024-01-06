from django_pydantic_field.compat.pydantic import PYDANTIC_V1

if not PYDANTIC_V1:
    raise ImportError("django_pydantic_field.v1 package is only compatible with Pydantic v1")

from .fields import *
