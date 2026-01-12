import typing as t
import typing_extensions as te
import pydantic
from django.db import models

from django_pydantic_field import SchemaField

from django_pydantic_field.v1.fields import SchemaField as SchemaFieldV1
from django_pydantic_field.v2.fields import SchemaField as SchemaFieldV2

T = t.TypeVar("T")


class SimpleSchema(pydantic.BaseModel):
    count: int


class GenericSchema(pydantic.BaseModel, t.Generic[T]):
    data: T


class LinterTestModel(models.Model):
    # Standard usage with type inference
    simple: SimpleSchema = SchemaField()
    simple_list: t.List[SimpleSchema] = SchemaField()
    optional: t.Optional[SimpleSchema] = SchemaField(null=True)

    # Forward References (String)
    forward_ref: "SimpleSchema" = SchemaField()

    # Without explicit annotation
    no_annotation = SchemaField(SimpleSchema)
    no_annotation_list = SchemaField(t.List[SimpleSchema])

    # Generics and Builtins
    generic_int: GenericSchema[int] = SchemaField()
    builtin_dict: dict[str, int] = SchemaField()
    generic_int_no_annotation = SchemaField(GenericSchema[int])
    builtin_dict_no_annotation = SchemaField(dict[str, int])

    # Explicit Version Fields
    v1_field: SimpleSchema = SchemaFieldV1()
    v2_field: SimpleSchema = SchemaFieldV2()
    v1_field_no_annotation = SchemaFieldV1(SimpleSchema)
    v2_field_no_annotation = SchemaFieldV2(SimpleSchema)

    # More complex cases from samples
    nested_generics: t.Union[t.List[te.Literal["foo"]], te.Literal["bar"]] = SchemaField()
    untyped_list = SchemaField(schema=t.List, default=list)
    untyped_builtin_list = SchemaField(schema=list, default=list)

    # Annotated support
    annotated_field: te.Annotated[t.Union[int, float], pydantic.Field(gt=0)] = SchemaField()
    annotated_schema = SchemaField(schema=te.Annotated[t.Union[int, float], pydantic.Field(gt=0)])


def linter_test_model_assertions(model: LinterTestModel):
    te.assert_type(model.simple, SimpleSchema)
    te.assert_type(model.simple_list, t.List[SimpleSchema])
    te.assert_type(model.optional, t.Optional[SimpleSchema])
    te.assert_type(model.generic_int, GenericSchema[int])
    te.assert_type(model.builtin_dict, dict[str, int])
    te.assert_type(model.v1_field, SimpleSchema)
    te.assert_type(model.v2_field, SimpleSchema)
    te.assert_type(model.forward_ref, SimpleSchema)
    te.assert_type(model.no_annotation, SimpleSchema)
    te.assert_type(model.no_annotation_list, t.List[SimpleSchema])
    te.assert_type(model.nested_generics, t.Union[t.List[te.Literal["foo"]], te.Literal["bar"]])
    te.assert_type(model.untyped_list, list)
    te.assert_type(model.untyped_builtin_list, t.List)
    te.assert_type(model.annotated_field, t.Union[int, float])
    te.assert_type(model.annotated_schema, t.Union[int, float])
