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
    config = {
        "agents": [{"name": "Default Agent"}],
        "guidelines": {
            "Default Agent": [
                {
                    "when": "Ask for multiply two numbers",
                    "then": "use the multiply tool to give him result",
                    "enabled_tools": ["multiply"],
                }
            ]
        },
        "tools": {
            "multiply": {
                "description": "Multiply two number",
                "function_name": "multiply",
                "module_path": "",
                "parameters": {
                    "a": {"description": "first number", "type": "number"},
                    "b": {"description": "second number", "type": "number"},
                },
                "required": ["a", "b"],
                "type": "python",
            }
        },
    }
    config["tools"]["multiply"]["module_path"] = (
        str(new_file.relative_to(Path.cwd())).replace("/", ".").replace(".py", "")
    )
    with open(new_file, "w") as f:
        f.write("""def multiply(a,b): return a*b""")
    return config


async def test_valid_config(
    valid_config: JSONSerializable,
) -> None:
    validator = ConfigFileValidator(valid_config)
    assert validator.validate() is True


async def test_invalid_tool(
    valid_config: JSONSerializable,
    new_file,
) -> None:
    config = copy.deepcopy(valid_config)
    config["tools"]["multiply"]["module_path"] = "invalid.path.to.multiply"

    validator = ConfigFileValidator(config)
    assert validator.validate() is False

    config = copy.deepcopy(valid_config)
    with open(new_file, "w") as f:
        f.write("""def not_multiply(): return""")

    validator = ConfigFileValidator(config)
    assert validator.validate() is False


async def test_guideline_missing_mandatory_keys(
    valid_config: JSONSerializable,
) -> None:
    config = copy.deepcopy(valid_config)
    del config["guidelines"]["Default Agent"][0]["when"]

    validator = ConfigFileValidator(config)
    assert validator.validate() is False

    config = copy.deepcopy(valid_config)
    del config["guidelines"]["Default Agent"][0]["then"]

    validator = ConfigFileValidator(config)
    assert validator.validate() is False


async def test_guideline_with_nonexistent_tool(
    valid_config: JSONSerializable,
) -> None:
    config = copy.deepcopy(valid_config)
    config["guidelines"]["Default Agent"][0]["enabled_tools"] = ["nonexistent_tool"]

    validator = ConfigFileValidator(config)
    assert validator.validate() is False


def test_guideline_agent_existence(valid_config: JSONSerializable):
    config = copy.deepcopy(valid_config)
    config["guidelines"]["Nonexistent Agent"] = [
        {"when": "Example condition", "then": "Example action"}
    ]

    validator = ConfigFileValidator(config)
    assert validator.validate() is False
