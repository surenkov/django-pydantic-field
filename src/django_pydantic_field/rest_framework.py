from .compat.imports import compat_dir, compat_getattr

__getattr__ = compat_getattr(__name__)
__dir__ = compat_dir(__name__)
