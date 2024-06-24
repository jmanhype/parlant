from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal, NewType, Optional

from emcie.server.core.common import JSONSerializable, generate_id
from emcie.server.core.tools import ToolId

ContextVariableId = NewType("ContextVariableId", str)
ContextVariableValueId = NewType("ContextVariableValueId", str)


@dataclass(frozen=True)
class FreshnessRules:
    """
    A data class representing the times at which the context variable should be considered fresh.
    """

    months: Optional[list[int]]
    days_of_month: Optional[list[int]]
    days_of_week: Optional[
        list[
            Literal[
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ]
        ]
    ]
    hours: Optional[list[int]]
    minutes: Optional[list[int]]
    seconds: Optional[list[int]]


@dataclass(frozen=True)
class ContextVariable:
    id: ContextVariableId
    name: str
    description: Optional[str]
    tool_id: ToolId
    freshness_rules: Optional[FreshnessRules]
    """If None, the variable will only be updated on session creation"""


@dataclass(frozen=True)
class ContextVariableValue:
    id: ContextVariableValueId
    variable_id: ContextVariableId
    last_modified: datetime
    data: JSONSerializable


class ContextVariableStore:
    def __init__(
        self,
    ) -> None:
        self._variable_sets: dict[str, dict[ContextVariableId, ContextVariable]] = defaultdict(dict)
        self._variable_values: dict[
            str, dict[str, dict[ContextVariableId, ContextVariableValue]]
        ] = defaultdict(lambda: defaultdict(dict))

    async def create_variable(
        self,
        variable_set: str,
        name: str,
        description: Optional[str],
        tool_id: ToolId,
        freshness_rules: Optional[FreshnessRules],
    ) -> ContextVariable:
        variable = ContextVariable(
            id=ContextVariableId(generate_id()),
            name=name,
            description=description,
            tool_id=tool_id,
            freshness_rules=freshness_rules,
        )

        self._variable_sets[variable_set][variable.id] = variable

        return variable

    async def update_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
        data: JSONSerializable,
    ) -> ContextVariableValue:
        existing_value = self._variable_values[variable_set][key].get(variable_id, None)

        updated_value = ContextVariableValue(
            id=existing_value and existing_value.id or ContextVariableValueId(generate_id()),
            variable_id=variable_id,
            last_modified=datetime.now(timezone.utc),
            data=data,
        )

        self._variable_values[variable_set][key][variable_id] = updated_value

        return updated_value

    async def delete_variable(
        self,
        variable_set: str,
        id: ContextVariableId,
    ) -> None:
        self._variable_sets[variable_set].pop(id)

    async def list_variables(
        self,
        variable_set: str,
    ) -> Iterable[ContextVariable]:
        return self._variable_sets[variable_set].values()

    async def read_variable(
        self,
        variable_set: str,
        id: ContextVariableId,
    ) -> ContextVariable:
        return self._variable_sets[variable_set][id]

    async def read_value(
        self,
        variable_set: str,
        key: str,
        variable_id: ContextVariableId,
    ) -> ContextVariableValue:
        return self._variable_values[variable_set][key][variable_id]
