from django.core.management import call_command

MIGRATIONS_DIR = "tests/sample_app/migrations/"


def test_makemigrations_not_failing_not_creating_new_ones():
    call_command("makemigrations", "sample_app", "--noinput")
