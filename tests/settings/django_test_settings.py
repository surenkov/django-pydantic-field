import os
import django

SECRET_KEY = "1"
SITE_ID = 1

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sites",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tests.sample_app",
]


REST_FRAMEWORK = {
    'COMPACT_JSON': True,
}
