import importlib
from typing import Any
from jsonschema import ValidationError, validate
from loguru import logger


class ConfigFileValidator:
    def __init__(
        self,
        config: Any,
    ) -> None:
        self.config = config
        self.schema = {
            "type": "object",
            "properties": {
                "agents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
                "guidelines": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "when": {"type": "string"},
                                "then": {"type": "string"},
                                "enabled_tools": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["when", "then"],
                        },
                    },
                },
                "tools": {
                    "type": "object",
                    "patternProperties": {
                        "^[a-zA-Z0-9_]+$": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "description": {"type": "string"},
                                "function_name": {"type": "string"},
                                "module_path": {"type": "string"},
                                "parameters": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "object",
                                        "properties": {
                                            "description": {"type": "string"},
                                            "type": {
                                                "enum": [
                                                    "number",
                                                    "string",
                                                    "integer",
                                                    "boolean",
                                                    "array",
                                                    "object",
                                                ]
                                            },
                                        },
                                        "required": ["description", "type"],
                                    },
                                },
                                "required": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "description",
                                "function_name",
                                "module_path",
                                "parameters",
                                "type",
                            ],
                        }
                    },
                },
            },
            "required": ["agents", "guidelines", "tools"],
        }

    def validate_json_schema(self) -> None:
        validate(instance=self.config, schema=self.schema)

    def validate_tools(self) -> None:
        for tool_name, tool_info in self.config["tools"].items():
            module_path = tool_info["module_path"]
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError:
                raise ValidationError(
                    f'Module path "{module_path}" for tool "{tool_name}" does not exist.'
                )
            function_name = tool_info["function_name"]
            try:
                getattr(module, function_name)
            except Exception:
                raise ValidationError(
                    f'The function "{function_name}" for tool "{tool_name}" '
                    f'does not exist in the "{module_path}" module.'
                )

    def validate_guidelines(self) -> None:
        tools = set(self.config["tools"].keys())
        agents = set(agent["name"] for agent in self.config["agents"])
        for agent, guidelines in self.config["guidelines"].items():
            if agent not in agents:
                raise ValidationError(f'Agent "{agent}" does not exist.')

            for guideline in guidelines:
                if "enabled_tools" in guideline:
                    for tool_name in guideline["enabled_tools"]:
                        if tool_name not in tools:
                            raise ValidationError(
                                f'Tool "{tool_name}" listed in "enabled_tools"'
                                ' does not exist in "tools".'
                            )

    def validate(self) -> bool:
        try:
            self.validate_json_schema()
            self.validate_tools()
            self.validate_guidelines()
            logger.info("Configuration file is valid.")
            return True
        except ValidationError as e:
            logger.error(f"Configuration file invalid: {str(e)}")
            return False
