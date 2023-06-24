import os
from contextlib import contextmanager

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db(databases="__all__")

MIGRATIONS_DIR = "tests/sample_app/migrations/"


def test_makemigrations_not_failing():
    call_command("makemigrations", "sample_app", "--noinput", "--dry-run")


def test_makemigrations_no_duplicates(capfd):
    with clean_dir(MIGRATIONS_DIR):
        call_command("makemigrations", "sample_app", "--noinput")
        capfd.readouterr()

        call_command("makemigrations", "sample_app", "--noinput", "--dry-run")
        out, _ = capfd.readouterr()

    assert "No changes detected in app 'sample_app'" in out, out


@contextmanager
def clean_dir(path):
    initial_files = dir_files(path)

    try:
        yield
    finally:
        new_files = dir_files(path) - initial_files
        for f_path in new_files:
            os.remove(f_path)


def dir_files(path):
    return {f.path for f in os.scandir(path) if f.is_file()}
