import os
import dj_database_url

SECRET_KEY = "1"
SITE_ID = 1
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_URL = "/static/"
DEBUG = True

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

try:
    import django_jsonform  # type: ignore[import-untyped]
except ImportError:
    pass
else:
    INSTALLED_APPS.append("django_jsonform")


MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
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
ROOT_URLCONF = "tests.settings.urls"
