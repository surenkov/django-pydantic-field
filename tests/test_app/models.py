import typing as t
import typing_extensions as te

import pydantic
from django.db import models
from django_pydantic_field import SchemaField
from django_pydantic_field.v1.fields import SchemaField as SchemaFieldV1
from django_pydantic_field.compat import PYDANTIC_V2

from ..conftest import InnerSchema, InnerSchemaV1


class FrozenInnerSchema(InnerSchema):
    model_config = pydantic.ConfigDict({"frozen": True})


class SampleModel(models.Model):
    sample_field: InnerSchema = SchemaField()
    sample_list: t.List[InnerSchema] = SchemaField()
    sample_seq: t.Sequence[InnerSchema] = SchemaField(schema=t.List[InnerSchema], default=list)

    class Meta:
        app_label = "test_app"


class SampleModelV1(models.Model):
    sample_field: InnerSchemaV1 = SchemaFieldV1()
    sample_list: t.List[InnerSchemaV1] = SchemaFieldV1()
    sample_seq: t.Sequence[InnerSchemaV1] = SchemaFieldV1(schema=t.List[InnerSchemaV1], default=list)

    class Meta:
        app_label = "test_app"


class SampleForwardRefModel(models.Model):
    annotated_field: "SampleSchema" = SchemaField(default=dict)
    field = SchemaField(schema=t.ForwardRef("SampleSchema"), default=dict)

    class Meta:
        app_label = "test_app"


class SampleSchema(pydantic.BaseModel):
    field: int = 1


class ExampleSchema(pydantic.BaseModel):
    count: int


class ExampleModel(models.Model):
    example_field: ExampleSchema = SchemaField(default=ExampleSchema(count=1))


if PYDANTIC_V2:

    class RootSchema(pydantic.RootModel):
        root: t.List[int]

else:

    class RootSchema(pydantic.BaseModel):
        __root__: t.List[int]


class SampleModelWithRoot(models.Model):
    root_field = SchemaField(schema=RootSchema, default=list)


class SampleModelAnnotated(models.Model):
    annotated_field: te.Annotated[t.Union[int, float], pydantic.Field(gt=0, title="Annotated Field")] = SchemaField()
    annotated_schema = SchemaField(schema=te.Annotated[t.Union[int, float], pydantic.Field(gt=0)])
