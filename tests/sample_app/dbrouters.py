from django.conf import settings


class TestDBRouter:
    def db_for_read(self, model, **hints):
        return settings.CURRENT_TEST_DB

    def db_for_write(self, model, **hints):
        return settings.CURRENT_TEST_DB

    def allow_relation(self, obj1, obj2, **hints):
        return True
