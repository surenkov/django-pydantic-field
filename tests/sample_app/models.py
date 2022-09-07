import enum
import typing as t
import pydantic

from django.db import models
from django_pydantic_field import SchemaField


class BuildingTypes(str, enum.Enum):
    FRAME = "frame"
    BRICK = "brick"
    STUCCO = "stucco"


class BuildingMeta(pydantic.BaseModel):
    type: t.Optional[BuildingTypes]


default_meta = BuildingMeta(type=BuildingTypes.FRAME)

class Building(models.Model):
    meta: BuildingMeta = SchemaField(schema=BuildingMeta, default=default_meta)
    meta_builtin_list: list[BuildingMeta] = SchemaField(schema=list[BuildingMeta], default=list)
    meta_typing_list: t.List[BuildingMeta] = SchemaField(schema=t.List[BuildingMeta], default=list)
    meta_untyped_list: list = SchemaField(schema=t.List, default=list)
    meta_untyped_builtin_list: t.List = SchemaField(schema=list, default=list)
