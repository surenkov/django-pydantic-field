import typing as t

import pydantic
from django.db import models
from django_pydantic_field import SchemaField

from ..conftest import InnerSchema


class FrozenInnerSchema(InnerSchema):
    model_config = pydantic.ConfigDict({"frozen": True})


class SampleModel(models.Model):
    sample_field: InnerSchema = SchemaField()
    sample_list: t.List[InnerSchema] = SchemaField()
    sample_seq: t.Sequence[InnerSchema] = SchemaField(schema=t.List[InnerSchema], default=list)

    class Meta:
        app_label = "test_app"


class SampleForwardRefModel(models.Model):
    annotated_field: "SampleSchema" = SchemaField(default=dict)
    field = SchemaField(schema=t.ForwardRef("SampleSchema"), default=dict)

    class Meta:
        app_label = "test_app"


class SampleSchema(pydantic.BaseModel):
    field: int = 1
