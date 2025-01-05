import functools
import inspect
import os
import time

import loguru

logger = loguru.logger


def timer(func):
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()
        value = func(*args, **kwargs)
        duration = time.perf_counter() - start_time
        filename = os.path.basename(inspect.getsourcefile(func))
        logger.info(f"Time cost: {filename}:{func.__name__!r}: {duration:.2f} secs")
        return value

    return wrapper_timer
