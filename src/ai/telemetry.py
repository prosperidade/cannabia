import time
from contextlib import contextmanager


@contextmanager
def time_block():
    """
    Context manager para medir tempo em ms.
    Uso:
        with time_block() as elapsed:
            ...
        print(elapsed())
    """
    start = time.perf_counter()
    elapsed_ms = {"value": 0}

    def get_elapsed():
        return elapsed_ms["value"]

    try:
        yield get_elapsed
    finally:
        end = time.perf_counter()
        elapsed_ms["value"] = int((end - start) * 1000)
