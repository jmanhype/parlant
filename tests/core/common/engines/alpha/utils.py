import importlib
import inspect
from sys import _getframe
from pytest_bdd import parsers
from typing import Any, Callable


class Step:
    def __init__(
        self,
        installer: Any,
        parser: str | parsers.StepParser,
        kwargs: Any,
        func: Callable[..., None],
    ):
        self._installer = installer
        self._parser = parser
        self._kwargs = kwargs
        self._func = func

    def install(self) -> None:
        self._installer(self._parser, stacklevel=3, **self._kwargs)(self._func)


def load_steps(*module_names: str) -> None:
    this_module = inspect.getmodule(_getframe(0))
    assert this_module

    for module_name in module_names:
        module = importlib.import_module(
            f"tests.core.common.engines.alpha.steps.{module_name}", this_module.__name__
        )
        steps = [a for a in module.__dict__.values() if isinstance(a, Step)]

        for s in steps:
            s.install()


def step(
    installer: Any,
    parser: str | parsers.StepParser,
    **kwargs: Any,
) -> Callable[..., Step]:
    def wrapper(func: Callable[..., None]) -> Step:
        return Step(installer, parser, kwargs, func)

    return wrapper
