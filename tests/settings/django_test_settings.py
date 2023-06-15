import os
import django

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
    "tests.sample_app",
    "tests.test_app",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "settings", "db.sqlite3"),
    },
    # "default": {
    #     "ENGINE": "django.db.backends.postgresql",
    #     "NAME": "test_db",
    #     "USER": "postgres",
    #     "PASSWORD": "pass",
    #     "HOST": "127.0.0.1",
    #     "PORT": 5432,
    # }
}

REST_FRAMEWORK = {
    "COMPACT_JSON": True,
}
