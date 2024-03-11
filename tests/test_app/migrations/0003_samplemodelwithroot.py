# Generated by Django 5.0.1 on 2024-03-11 22:29

import django.core.serializers.json
import django_pydantic_field.fields
import tests.test_app.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("test_app", "0002_examplemodel"),
    ]

    operations = [
        migrations.CreateModel(
            name="SampleModelWithRoot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "root_field",
                    django_pydantic_field.fields.PydanticSchemaField(
                        config=None,
                        default=list,
                        encoder=django.core.serializers.json.DjangoJSONEncoder,
                        schema=tests.test_app.models.RootSchema,
                    ),
                ),
            ],
        ),
    ]
