import json
import uuid
from datetime import date
from decimal import Decimal

import pydantic
from django.core.serializers.json import DjangoJSONEncoder
from django.db.migrations.writer import MigrationWriter

from django_pydantic_field import fields
from django_pydantic_field.compat.pydantic import PYDANTIC_V2

from .conftest import InnerSchema, SampleDataclass
from .test_app.models import SampleModel

if PYDANTIC_V2:

    class SampleRootModel(pydantic.RootModel):
        root: list[str]

else:

    class SampleRootModel(pydantic.BaseModel):
        __root__: list[str]


def test_encoder_default_is_pydantic_django_json_encoder():
    field = fields.PydanticSchemaField(schema=InnerSchema)
    assert field.encoder is fields.PydanticDjangoJSONEncoder

    factory_field = fields.SchemaField(InnerSchema)
    assert factory_field.encoder is fields.PydanticDjangoJSONEncoder


def test_pydantic_django_json_encoder_direct():
    """Verify PydanticDjangoJSONEncoder directly encodes Pydantic models, root models, and dataclasses."""
    encoder = fields.PydanticDjangoJSONEncoder

    # Pydantic model
    inner = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    assert json.loads(json.dumps(inner, cls=encoder)) == {
        "stub_str": "abc",
        "stub_int": 1,
        "stub_list": ["2022-07-01"],
    }

    # Root model
    root = SampleRootModel(root=["alpha", "beta"]) if PYDANTIC_V2 else SampleRootModel(__root__=["alpha", "beta"])
    assert json.loads(json.dumps(root, cls=encoder)) == ["alpha", "beta"]

    # Dataclass
    dc = SampleDataclass(stub_str="xyz", stub_list=[date(2022, 7, 1)], stub_int=42)
    assert json.loads(json.dumps(dc, cls=encoder)) == {
        "stub_str": "xyz",
        "stub_list": ["2022-07-01"],
        "stub_int": 42,
    }

    # Standard Django types inside containers alongside models
    sample_uuid = uuid.uuid4()
    payload = {
        "date": date(2023, 5, 1),
        "decimal": Decimal("12.34"),
        "uuid": sample_uuid,
        "model": inner,
    }
    res = json.loads(json.dumps(payload, cls=encoder))
    assert res["date"] == "2023-05-01"
    assert res["decimal"] == "12.34"
    assert res["uuid"] == str(sample_uuid)
    assert res["model"]["stub_str"] == "abc"


def test_schema_field_encoder_with_model_instance():
    """Verify json.dumps(val, cls=field.encoder) works for model instances (Issue #86)."""
    instance = SampleModel(
        sample_field=InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)]),
        sample_list=[InnerSchema(stub_str="item", stub_list=[date(2022, 7, 1)])],
    )
    field = instance._meta.get_field("sample_field")
    list_field = instance._meta.get_field("sample_list")

    # Serialize single schema field
    encoded_str = json.dumps(instance.sample_field, cls=field.encoder)
    assert json.loads(encoded_str) == {
        "stub_str": "abc",
        "stub_int": 1,
        "stub_list": ["2022-07-01"],
    }

    # Serialize list schema field
    encoded_list_str = json.dumps(instance.sample_list, cls=list_field.encoder)
    assert json.loads(encoded_list_str) == [{"stub_str": "item", "stub_int": 1, "stub_list": ["2022-07-01"]}]


def test_schema_field_custom_encoder_override():
    """Verify explicitly provided encoder is preserved and not overridden."""

    class CustomEncoder(DjangoJSONEncoder):
        def default(self, o):
            return "custom"

    field = fields.PydanticSchemaField(schema=InnerSchema, encoder=CustomEncoder)
    assert field.encoder is CustomEncoder


def test_migration_writer_serialization():
    """Verify field serialization in migrations preserves DjangoJSONEncoder to prevent unnecessary migrations."""
    field = fields.PydanticSchemaField(schema=InnerSchema)
    serialized, imports = MigrationWriter.serialize(field)
    assert "encoder=django.core.serializers.json.DjangoJSONEncoder" in serialized
    assert "import django.core.serializers.json" in imports
