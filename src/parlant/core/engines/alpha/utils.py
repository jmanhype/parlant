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

import json
from typing import Any, Sequence, cast

from parlant.core.context_variables import ContextVariable, ContextVariableValue
from parlant.core.sessions import ToolEventData
from parlant.core.emissions import EmittedEvent


def context_variables_to_json(
    context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
) -> str:
    context_values = {
        variable.name: {
            "value": value.data,
            **({"description": variable.description} if variable.description else {}),
        }
        for variable, value in context_variables
    }

    return json.dumps(context_values)


def emitted_tool_events_to_dicts(
    events: Sequence[EmittedEvent],
) -> list[dict[str, Any]]:
    return [emitted_tool_event_to_dict(e) for e in events]


def emitted_tool_event_to_dict(event: EmittedEvent) -> dict[str, Any]:
    assert event.kind == "tool"

    return {
        "kind": event.kind,
        "data": cast(ToolEventData, event.data)["tool_calls"],
    }
