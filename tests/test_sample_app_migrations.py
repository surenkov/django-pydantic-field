import os
from django.core.management import call_command


def test_makemigrations_not_failing_not_creating_new_ones():
    files = {e.path for e in os.scandir("./tests/sample_app/migrations") if e.is_file()}

    call_command("makemigrations", "sample_app")
    new_files = {e.path for e in os.scandir("./tests/sample_app/migrations") if e.is_file()}

    assert files == new_files
