from unittest.mock import MagicMock

import pydantic
from django.db import models
from django.test.utils import isolate_apps

from django_pydantic_field import fields


@isolate_apps("tests.test_app")
def test_django_jsonfield_default_factory_flow():
    default_mock = MagicMock(return_value={"foo": "bar"})

    class SampleModel(models.Model):
        field = models.JSONField(default=default_mock)

        class Meta:
            app_label = "test_app"

    default_mock.assert_not_called()

    obj = SampleModel()
    default_mock.assert_called_once()

    assert obj.field == {"foo": "bar"}
    default_mock.assert_called_once()


@isolate_apps("tests.test_app")
def test_pydantic_schemafield_default_factory_flow():
    default_mock = MagicMock(return_value={"foo": "bar"})

    class SampleSchema(pydantic.BaseModel):
        foo: str = "bar"

    class SampleModel(models.Model):
        field = fields.SchemaField(SampleSchema, default=default_mock)

        class Meta:
            app_label = "test_app"

    default_mock.assert_not_called()

    obj = SampleModel()
    default_mock.assert_called_once()

    assert obj.field == SampleSchema(foo="bar")
    default_mock.assert_called_once()


@isolate_apps("tests.test_app")
def test_pydantic_schemafield_inner_default_factory_flow():
    default_mock = MagicMock(return_value="bar")

    class SampleSchema(pydantic.BaseModel):
        foo: str = pydantic.Field(default_factory=default_mock)

    class SampleModel(models.Model):
        field = fields.SchemaField(SampleSchema, default=SampleSchema)

        class Meta:
            app_label = "test_app"

    default_mock.assert_not_called()

    obj = SampleModel()
    default_mock.assert_called_once()

    assert obj.field == SampleSchema(foo="bar")
    default_mock.assert_called_once()
