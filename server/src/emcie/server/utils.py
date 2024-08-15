from contextlib import contextmanager
import hashlib
import time
from typing import Any

from emcie.server.logger import Logger


@contextmanager
def duration_logger(
    logger: Logger,
    operation_name: str,
) -> Any:
    t_start = time.time()

    try:
        yield
    finally:
        t_end = time.time()
        logger.debug(f"{operation_name} took {round(t_end - t_start, 3)}s")


def md5_checksum(input: str) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(input.encode("utf-8"))

    return md5_hash.hexdigest()
