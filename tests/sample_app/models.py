from __future__ import annotations

import enum
import typing as ty

import pydantic
from django.db import models

from django_pydantic_field import SchemaField


class Building(models.Model):
    opt_meta: ty.Optional["BuildingMeta"] = SchemaField(default={"type": "frame"}, null=True)
    meta: "BuildingMeta" = SchemaField(default={"type": "frame"})

    meta_schema_list = SchemaField(schema=ty.ForwardRef("ty.List[BuildingMeta]"), default=list)
    meta_typing_list: ty.List["BuildingMeta"] = SchemaField(default=list)
    meta_untyped_list: list = SchemaField(schema=ty.List, default=list)
    meta_untyped_builtin_list: ty.List = SchemaField(schema=list, default=list)


class BuildingTypes(str, enum.Enum):
    FRAME = "frame"
    BRICK = "brick"
    STUCCO = "stucco"


class BuildingMeta(pydantic.BaseModel):
    type: ty.Optional[BuildingTypes]


class PostponedBuilding(models.Model):
    meta: "BuildingMeta" = SchemaField(default=BuildingMeta(type=BuildingTypes.FRAME))
    meta_builtin_list: ty.List[BuildingMeta] = SchemaField(schema=ty.List[BuildingMeta], default=list)
    meta_typing_list: ty.List["BuildingMeta"] = SchemaField(default=list)
    meta_untyped_list: list = SchemaField(schema=ty.List, default=list)
    meta_untyped_builtin_list: ty.List = SchemaField(schema=list, default=list)
