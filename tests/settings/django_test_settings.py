import os
import dj_database_url

SECRET_KEY = "1"
SITE_ID = 1
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sites",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "tests.sample_app",
    "tests.test_app",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "settings", "db.sqlite3"),
    },
}

if os.getenv("POSTGRES_DSN"):
    DATABASES["postgres"] = dj_database_url.config("POSTGRES_DSN")  # type: ignore

if os.getenv("MYSQL_DSN"):
    DATABASES["mysql"] = dj_database_url.config("MYSQL_DSN")  # type: ignore

DATABASE_ROUTERS = ["tests.sample_app.dbrouters.TestDBRouter"]
CURRENT_TEST_DB = "default"

REST_FRAMEWORK = {"COMPACT_JSON": True}
