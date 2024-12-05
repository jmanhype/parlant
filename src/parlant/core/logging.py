# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from abc import ABC, abstractmethod
import asyncio
from contextlib import contextmanager
from enum import Enum, auto
from pathlib import Path
import time
import traceback
from typing import Any, Iterator
from typing_extensions import override
import coloredlogs  # type: ignore
import logging
import logging.handlers

from parlant.core.contextual_correlator import ContextualCorrelator


class LogLevel(Enum):
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class CustomFormatter(logging.Formatter, ABC):
    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s %(name)s[P=%(process)d; T=%(thread)d] %(levelname)s %(message)s"
        )


class Logger(ABC):
    @abstractmethod
    def set_level(self, log_level: LogLevel) -> None: ...

    @abstractmethod
    def debug(self, message: str) -> None: ...

    @abstractmethod
    def info(self, message: str) -> None: ...

    @abstractmethod
    def warning(self, message: str) -> None: ...

    @abstractmethod
    def error(self, message: str) -> None: ...

    @abstractmethod
    def critical(self, message: str) -> None: ...

    @abstractmethod
    @contextmanager
    def operation(self, name: str, props: dict[str, Any] = {}) -> Iterator[None]: ...


class CorrelationalLogger(Logger):
    def __init__(
        self,
        correlator: ContextualCorrelator,
        log_level: LogLevel = LogLevel.DEBUG,
    ) -> None:
        self._correlator = correlator
        self.logger = logging.getLogger("parlant")
        self._formatter = CustomFormatter()
        self.set_level(log_level)

    @override
    def set_level(self, log_level: LogLevel) -> None:
        self.logger.setLevel(
            {
                LogLevel.DEBUG: logging.DEBUG,
                LogLevel.INFO: logging.INFO,
                LogLevel.WARNING: logging.WARNING,
                LogLevel.ERROR: logging.ERROR,
                LogLevel.CRITICAL: logging.CRITICAL,
            }[log_level]
        )

    @override
    def debug(self, message: str) -> None:
        self.logger.debug(self._add_correlation_id(message))

    @override
    def info(self, message: str) -> None:
        self.logger.info(self._add_correlation_id(message))

    @override
    def warning(self, message: str) -> None:
        self.logger.warning(self._add_correlation_id(message))

    @override
    def error(self, message: str) -> None:
        self.logger.error(self._add_correlation_id(message))

    @override
    def critical(self, message: str) -> None:
        self.logger.critical(self._add_correlation_id(message))

    @override
    @contextmanager
    def operation(self, name: str, props: dict[str, Any] = {}) -> Iterator[None]:
        t_start = time.time()
        try:
            if props:
                self.info(f"{name} [{props}] started")
            else:
                self.info(f"{name} started")

            yield

            t_end = time.time()

            if props:
                self.info(f"{name} [{props}] finished in {t_end - t_start}s")
            else:
                self.info(f"{name} finished in {round(t_end - t_start, 3)} seconds")
        except asyncio.CancelledError:
            self.error(f"{name} cancelled after {round(time.time() - t_start, 3)} seconds")
            raise
        except Exception as exc:
            self.error(f"{name} failed")
            self.error(" ".join(traceback.format_exception(exc)))
            raise
        except BaseException as exc:
            self.error(f"{name} failed with critical error")
            self.critical(" ".join(traceback.format_exception(exc)))
            raise

    def _add_correlation_id(self, message: str) -> str:
        return f"[{self._correlator.correlation_id}] {message}"


class StdoutLogger(CorrelationalLogger):
    def __init__(
        self,
        correlator: ContextualCorrelator,
        log_level: LogLevel = LogLevel.DEBUG,
    ) -> None:
        super().__init__(correlator, log_level)
        coloredlogs.install(level="DEBUG", logger=self.logger)


class FileLogger(CorrelationalLogger):
    def __init__(
        self,
        log_file_path: Path,
        correlator: ContextualCorrelator,
        log_level: LogLevel = LogLevel.DEBUG,
    ) -> None:
        super().__init__(correlator, log_level)

        handlers: list[logging.Handler] = [
            logging.FileHandler(log_file_path),
            logging.StreamHandler(),
        ]

        for handler in handlers:
            handler.setFormatter(self._formatter)
            self.logger.addHandler(handler)

        coloredlogs.install(level=log_level.name, logger=self.logger)
