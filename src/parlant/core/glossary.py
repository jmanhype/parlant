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

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import NewType, Optional, Sequence, TypedDict


TermId = NewType("TermId", str)


@dataclass(frozen=True)
class Term:
    id: TermId
    creation_utc: datetime
    name: str
    description: str
    synonyms: list[str]

    def __repr__(self) -> str:
        term_string = f"Name: '{self.name}', Description: {self.description}"
        if self.synonyms:
            term_string += f", Synonyms: {', '.join(self.synonyms)}"
        return term_string

    def __hash__(self) -> int:
        return hash(self.id)


class TermUpdateParams(TypedDict, total=False):
    name: str
    description: str
    synonyms: Sequence[str]


class GlossaryStore:
    @abstractmethod
    async def create_term(
        self,
        term_set: str,
        name: str,
        description: str,
        creation_utc: Optional[datetime] = None,
        synonyms: Optional[Sequence[str]] = None,
    ) -> Term: ...

    @abstractmethod
    async def update_term(
        self,
        term_set: str,
        term_id: TermId,
        params: TermUpdateParams,
    ) -> Term: ...

    @abstractmethod
    async def read_term(
        self,
        term_set: str,
        term_id: TermId,
    ) -> Term: ...

    @abstractmethod
    async def list_terms(
        self,
        term_set: str,
    ) -> Sequence[Term]: ...

    @abstractmethod
    async def delete_term(
        self,
        term_set: str,
        term_id: TermId,
    ) -> None: ...

    @abstractmethod
    async def find_relevant_terms(
        self,
        term_set: str,
        query: str,
    ) -> Sequence[Term]: ...
