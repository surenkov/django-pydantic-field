from .compat.imports import compat_getattr, compat_dir

__getattr__ = compat_getattr(__name__)
__dir__ = compat_dir(__name__)
