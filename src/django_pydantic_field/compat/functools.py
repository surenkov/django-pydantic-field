try:
    from functools import cached_property as cached_property
except ImportError:
    from django.utils.functional import cached_property as cached_property  # type: ignore
