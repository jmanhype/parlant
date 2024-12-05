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

from contextlib import contextmanager
import contextvars
from typing import Iterator

from parlant.core.common import generate_id

_UNINITIALIZED = 0xC0FFEE


class ContextualCorrelator:
    def __init__(self) -> None:
        self._instance_id = generate_id()

        self._scopes = contextvars.ContextVar[str](
            f"correlator_{self._instance_id}_scopes",
            default="",
        )

    @contextmanager
    def correlation_scope(self, scope_id: str) -> Iterator[None]:
        current_scopes = self._scopes.get()

        if current_scopes:
            new_scopes = current_scopes + f".{scope_id}"
        else:
            new_scopes = scope_id

        reset_token = self._scopes.set(new_scopes)

        yield

        self._scopes.reset(reset_token)

    @property
    def correlation_id(self) -> str:
        if scopes := self._scopes.get():
            return scopes
        return "<main>"
