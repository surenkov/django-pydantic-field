from typing import Annotated
from unittest.mock import MagicMock

import pydantic
import pytest
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
    assert SampleModel.check() == []
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
    assert SampleModel.check() == []
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
    assert SampleModel.check() == []
    default_mock.assert_not_called()

    obj = SampleModel()
    default_mock.assert_called_once()

    assert obj.field == SampleSchema(foo="bar")
    default_mock.assert_called_once()


@isolate_apps("tests.test_app")
def test_pydantic_schemafield_default_factory_with_export_kwargs():
    default_mock = MagicMock(return_value={"foo": "bar"})
    annotated_mock = MagicMock(return_value={"foo": "bar"})

    class SampleSchema(pydantic.BaseModel):
        foo: str = "bar"

    class SampleModel(models.Model):
        field = fields.SchemaField(SampleSchema, default=default_mock, include={"foo"})
        annotated_field: Annotated[SampleSchema, pydantic.Field(default_factory=annotated_mock)] = fields.SchemaField(
            include={"foo"}
        )

        class Meta:
            app_label = "test_app"

    default_mock.assert_not_called()
    annotated_mock.assert_not_called()
    assert SampleModel.check() == []
    default_mock.assert_not_called()
    annotated_mock.assert_not_called()


@isolate_apps("tests.test_app")
def test_pydantic_schemafield_runtime_error_callable_default():
    dynamic_default = MagicMock(side_effect=RuntimeError("Runtime context unavailable during startup"))

    class SampleSchema(pydantic.BaseModel):
        foo: str = "bar"

    class SampleModel(models.Model):
        field = fields.SchemaField(SampleSchema, default=dynamic_default)

        class Meta:
            app_label = "test_app"

    assert SampleModel.check() == []
    dynamic_default.assert_not_called()

    with pytest.raises(RuntimeError, match="Runtime context unavailable during startup"):
        SampleModel()


@isolate_apps("tests.test_app")
def test_pydantic_schemafield_static_invalid_default_reports_e002():
    class SampleSchema(pydantic.BaseModel):
        foo: int

    class SampleModel(models.Model):
        field = fields.SchemaField(SampleSchema, default="invalid_static_value")

        class Meta:
            app_label = "test_app"

    errors = SampleModel.check()
    assert len(errors) == 1
    assert errors[0].id == "pydantic.E002"
