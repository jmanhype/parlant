from abc import ABC
from pathlib import Path
from loguru import logger


class Logger(ABC):
    def __init__(self) -> None:
        self.logger = logger

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def critical(self, message: str) -> None:
        self.logger.critical(message)


class StdoutLogger(Logger):
    def __init__(self) -> None:
        super().__init__()
        # self.logger.remove()
        # self.logger.add(lambda msg: print(msg, end=""))


class FileLogger(Logger):
    def __init__(self, log_file_path: Path) -> None:
        super().__init__()
        logger.remove()
        logger.add(lambda msg: print(msg, end=""))
        self.logger.add(
            log_file_path,
            rotation="500 MB",
            retention="10 days",
            compression="zip",
            level="DEBUG",
        )
