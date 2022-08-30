import enum
import typing as t
import pydantic

from django.db import models
from django_pydantic_field import PydanticSchemaField


class BuildingTypes(str, enum.Enum):
    FRAME = "frame"
    BRICK = "brick"
    STUCCO = "stucco"


class BuildingMeta(pydantic.BaseModel):
    type: t.Optional[BuildingTypes]


default_meta = BuildingMeta(type=BuildingTypes.FRAME)

class Building(models.Model):
    meta = PydanticSchemaField(schema=BuildingMeta, default=default_meta)
