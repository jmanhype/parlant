import copy
import importlib
import json
from pathlib import Path
from pydoc import importfile
import tempfile
from typing import Callable

from pytest import fixture

from emcie.server.engines.alpha.configuration_validator import config_validator
from emcie.server.core.common import JSONSerializable


@fixture(scope="function")
def new_file() -> Callable[[], Path]:
    def create_temp_file() -> Path:
        with tempfile.NamedTemporaryFile() as file:
            return Path(file.name)

    return create_temp_file


@fixture
def valid_config(
    new_file: Callable[[], Path],
) -> JSONSerializable:
    tool_file = new_file()

    def create_valid_config() -> JSONSerializable:
        return {
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
                    "module_path": importfile(str(tool_file)).__name__,
                    "parameters": {
                        "a": {"description": "first number", "type": "number"},
                        "b": {"description": "second number", "type": "number"},
                    },
                    "required": ["a", "b"],
                    "type": "python",
                }
            },
        }

    with open(tool_file, "w") as f:
        f.write("""def multiply(a, b): return a * b""")
    return create_valid_config()


async def test_that_empty_config_is_valid(
    new_file: Callable[[], Path],
) -> None:
    config_file = new_file()
    with open(config_file, "w") as f:
        f.write(
            json.dumps(
                {
                    "agents": [{"name": "Default Agent"}],
                    "guidelines": {"Default Agent": []},
                    "tools": {},
                }
            )
        )
    assert config_validator.validate(config_file) is True


async def test_valid_config(
    valid_config: JSONSerializable,
    new_file: Callable[[], Path],
) -> None:
    config_file = new_file()
    with open(config_file, "w") as f:
        f.write(json.dumps(valid_config))

    assert config_validator.validate(config_file) is True


async def test_invalid_tool(
    valid_config: JSONSerializable,
    new_file: Callable[[], Path],
) -> None:
    config_file = new_file()
    tool_file = new_file()

    invalid_config: JSONSerializable = copy.deepcopy(valid_config)
    invalid_config["tools"]["multiply"]["module_path"] = "invalid.path.to.multiply"  # type: ignore

    with open(config_file, "w") as f:
        f.write(json.dumps(invalid_config))

    assert config_validator.validate(config_file) is False

    with open(tool_file, "w") as f:
        f.write("""def not_multiply(): return""")

    assert config_validator.validate(config_file) is False


async def test_guideline_missing_mandatory_keys(
    valid_config: JSONSerializable,
    new_file: Callable[[], Path],
) -> None:
    config_file = new_file()

    invalid_config = copy.deepcopy(valid_config)
    del invalid_config["guidelines"]["Default Agent"][0]["when"]  # type: ignore

    with open(config_file, "w") as f:
        f.write(json.dumps(invalid_config))

    assert config_validator.validate(config_file) is False

    invalid_config = copy.deepcopy(valid_config)
    del invalid_config["guidelines"]["Default Agent"][0]["then"]  # type: ignore

    with open(config_file, "w") as f:
        f.write(json.dumps(invalid_config))

    assert config_validator.validate(config_file) is False


async def test_guideline_with_nonexistent_tool(
    valid_config: JSONSerializable,
    new_file: Callable[[], Path],
) -> None:
    config_file = new_file()

    invalid_config = copy.deepcopy(valid_config)
    invalid_config["guidelines"]["Default Agent"][0]["enabled_tools"] = [  # type: ignore
        "nonexistent_tool"
    ]

    with open(config_file, "w") as f:
        f.write(json.dumps(invalid_config))

    assert config_validator.validate(config_file) is False


def test_guideline_agent_existence(
    valid_config: JSONSerializable,
    new_file: Callable[[], Path],
) -> None:
    config_file = new_file()

    invalid_config = copy.deepcopy(valid_config)
    invalid_config["guidelines"]["Nonexistent Agent"] = [  # type: ignore
        {"when": "Example condition", "then": "Example action"}
    ]

    with open(config_file, "w") as f:
        f.write(json.dumps(invalid_config))

    assert config_validator.validate(config_file) is False


def test_invalid_json(
    new_file: Callable[[], Path],
) -> None:
    config_file = new_file()

    with open(config_file, "w") as f:
        f.write("{invalid_json: true,}")

    assert config_validator.validate(config_file) is False
