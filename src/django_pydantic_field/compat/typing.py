try:
    from typing import get_args as get_args
    from typing import get_origin as get_origin
except ImportError:
    from typing_extensions import get_args as get_args
    from typing_extensions import get_origin as get_origin
