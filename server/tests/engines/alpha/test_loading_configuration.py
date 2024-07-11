import copy
from pathlib import Path
from typing import AsyncIterator
import pytest

from emcie.server.core.common import JSONSerializable
from emcie.server.engines.alpha.configuration_validator import ConfigFileValidator


@pytest.fixture
async def new_file() -> AsyncIterator[Path]:
    path = Path(__file__).parent / "new_file.py"
    path.touch()
    try:
        yield path
    finally:
        path.unlink()


@pytest.fixture
async def valid_config(new_file: Path) -> JSONSerializable:
    config: JSONSerializable = {
        "agents": [{"name": "Default Agent"}],
        "guidelines": {
            "Default Agent": [
                {
                    "when": "Ask to multiply two numbers",
                    "then": "use the multiply tool to provide the result",
                    "enabled_tools": ["multiply"],
                }
            ]
        },
        "tools": {
            "multiply": {
                "description": "Multiply two numbers",
                "function_name": "multiply",
                "module_path": str(new_file.relative_to(Path.cwd()))
                .replace("/", ".")
                .replace(".py", ""),
                "parameters": {
                    "a": {"description": "first number", "type": "number"},
                    "b": {"description": "second number", "type": "number"},
                },
                "required": ["a", "b"],
                "type": "python",
            }
        },
    }
    with open(new_file, "w") as f:
        f.write("""def multiply(a, b): return a * b""")
    return config


@pytest.fixture
async def empty_config() -> JSONSerializable:
    config: JSONSerializable = {
        "agents": [{"name": "Default Agent"}],
        "guidelines": {"Default Agent": []},
        "tools": {},
    }
    return config


async def test_that_empty_config_is_valid(
    empty_config: JSONSerializable,
) -> None:
    validator = ConfigFileValidator(empty_config)
    assert validator.validate() is True


async def test_valid_config(
    valid_config: JSONSerializable,
) -> None:
    validator = ConfigFileValidator(valid_config)
    assert validator.validate() is True


async def test_invalid_tool(
    valid_config: JSONSerializable,
    new_file: Path,
) -> None:
    invalid_config: JSONSerializable = copy.deepcopy(valid_config)
    invalid_config["tools"]["multiply"]["module_path"] = "invalid.path.to.multiply"  # type: ignore

    validator = ConfigFileValidator(invalid_config)
    assert validator.validate() is False

    invalid_config = copy.deepcopy(valid_config)
    with open(new_file, "w") as f:
        f.write("""def not_multiply(): return""")

    validator = ConfigFileValidator(invalid_config)
    assert validator.validate() is False


async def test_guideline_missing_mandatory_keys(
    valid_config: JSONSerializable,
) -> None:
    invalid_config = copy.deepcopy(valid_config)
    del invalid_config["guidelines"]["Default Agent"][0]["when"]  # type: ignore

    validator = ConfigFileValidator(invalid_config)
    assert validator.validate() is False

    invalid_config = copy.deepcopy(valid_config)
    del invalid_config["guidelines"]["Default Agent"][0]["then"]  # type: ignore

    validator = ConfigFileValidator(invalid_config)
    assert validator.validate() is False


async def test_guideline_with_nonexistent_tool(
    valid_config: JSONSerializable,
) -> None:
    invalid_config = copy.deepcopy(valid_config)
    invalid_config["guidelines"]["Default Agent"][0]["enabled_tools"] = [  # type: ignore
        "nonexistent_tool"
    ]

    validator = ConfigFileValidator(invalid_config)
    assert validator.validate() is False


def test_guideline_agent_existence(
    valid_config: JSONSerializable,
) -> None:
    invalid_config = copy.deepcopy(valid_config)
    invalid_config["guidelines"]["Nonexistent Agent"] = [  # type: ignore
        {"when": "Example condition", "then": "Example action"}
    ]

    validator = ConfigFileValidator(invalid_config)
    assert validator.validate() is False
