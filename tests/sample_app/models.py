import enum
import typing as t
import typing_extensions as te

import pydantic
from django.db import models
from django_pydantic_field import SchemaField


class BuildingTypes(str, enum.Enum):
    FRAME = "frame"
    BRICK = "brick"
    STUCCO = "stucco"


class Building(models.Model):
    opt_meta: t.Optional["BuildingMeta"] = SchemaField(default={"type": "frame"}, exclude={"type"}, null=True)
    meta: "BuildingMeta" = SchemaField(default={"type": "frame"}, include={"type"})

    meta_schema_list = SchemaField(schema=t.ForwardRef("t.List[BuildingMeta]"), default=list)
    meta_typing_list: t.List["BuildingMeta"] = SchemaField(default=list)
    meta_untyped_list: list = SchemaField(schema=t.List, default=list)
    meta_untyped_builtin_list: t.List = SchemaField(schema=list, default=list)


class BuildingMeta(pydantic.BaseModel):
    type: t.Optional[BuildingTypes] = pydantic.Field(alias="buildingType")


class PostponedBuilding(models.Model):
    meta: "BuildingMeta" = SchemaField(default=BuildingMeta(buildingType=BuildingTypes.FRAME), by_alias=True)
    meta_builtin_list: t.List[BuildingMeta] = SchemaField(schema=t.List[BuildingMeta], default=list)
    meta_typing_list: t.List["BuildingMeta"] = SchemaField(default=list)
    meta_untyped_list: list = SchemaField(schema=t.List, default=list)
    meta_untyped_builtin_list: t.List = SchemaField(schema=list, default=list)
    nested_generics: t.Union[t.List[te.Literal["foo"]], te.Literal["bar"]] = SchemaField()
