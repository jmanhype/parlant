from typing import (
    Any,
    Coroutine,
    ParamSpec,
    Type,
    TypeVar,
    Callable,
    Union,
    Optional,
)
import asyncio
from dataclasses import dataclass

from parlant.core.nlp.generation import T, SchematicGenerationResult

ExceptionType = TypeVar("ExceptionType", bound=Exception)
P = ParamSpec("P")


@dataclass
class RetryConfig:
    max_attempts: int = 5
    wait_times: tuple[float, ...] = (1.0, 2.0, 10.0, 30.0)

    def get_wait_time(self, attempt: int) -> float:
        if attempt <= 0:
            return 0
        if attempt > len(self.wait_times):
            return self.wait_times[-1]
        return self.wait_times[attempt - 1]


def retry(
    exceptions: Union[Type[Exception], tuple[Type[Exception], ...]],
    max_attempts: Optional[int] = None,
    wait_times: Optional[tuple[float, ...]] = None,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, SchematicGenerationResult[T]]]],
    Callable[P, Coroutine[Any, Any, SchematicGenerationResult[T]]],
]:
    if not isinstance(exceptions, tuple):
        exceptions = (exceptions,)

    config = RetryConfig()
    if max_attempts is not None:
        config.max_attempts = max_attempts
    if wait_times is not None:
        config.wait_times = wait_times

    def decorator(
        func: Callable[P, Coroutine[Any, Any, SchematicGenerationResult[T]]],
    ) -> Callable[P, Coroutine[Any, Any, SchematicGenerationResult[T]]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> SchematicGenerationResult[T]:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        raise last_exception

                    wait_time = config.get_wait_time(attempt)
                    await asyncio.sleep(wait_time)

            raise (
                last_exception
                if last_exception
                else RuntimeError("Unexpected error in retry logic")
            )

        return wrapper

    return decorator
