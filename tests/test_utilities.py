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

import asyncio
import hashlib
import json
import logging
from contextlib import AsyncExitStack, contextmanager
import os
from pathlib import Path
from time import sleep
from typing import (
    Any,
    Awaitable,
    Callable,
    Generator,
    Iterator,
    Mapping,
    Optional,
    TypeVar,
    TypedDict,
    cast,
)

from lagom import Container
from parlant.adapters.db.json_file import JSONFileDocumentDatabase
from parlant.adapters.nlp.openai import GPT_4o
from parlant.bin.server import PARLANT_HOME_DIR
from parlant.core.agents import Agent, AgentId, AgentStore
from parlant.core.application import Application
from parlant.core.async_utils import Timeout
from parlant.core.common import DefaultBaseModel, JSONSerializable, Version
from parlant.core.context_variables import (
    ContextVariable,
    ContextVariableId,
    ContextVariableStore,
    ContextVariableValue,
)
from parlant.core.customers import Customer, CustomerId, CustomerStore
from parlant.core.glossary import GlossaryStore, Term
from parlant.core.guideline_tool_associations import GuidelineToolAssociationStore
from parlant.core.guidelines import Guideline, GuidelineStore
from parlant.core.logging import LogLevel, Logger
from parlant.core.nlp.generation import (
    FallbackSchematicGenerator,
    GenerationInfo,
    SchematicGenerationResult,
    SchematicGenerator,
    UsageInfo,
)
from parlant.core.nlp.tokenization import EstimatingTokenizer
from parlant.core.sessions import (
    _GenerationInfoDocument,
    _UsageInfoDocument,
    Event,
    MessageEventData,
    Session,
    SessionId,
    SessionStore,
)
from parlant.core.tools import LocalToolService, ToolId, ToolResult
from parlant.core.persistence.common import ObjectId
from parlant.core.persistence.document_database import DocumentCollection

T = TypeVar("T")
GLOBAL_CACHE_FILE = Path("_schematic_cache.json")
CACHE_SCHEMATIC_GENERATION_RESULTS = (
    True
    if os.environ.get("CACHE_SCHEMATIC_GENERATION_RESULTS", "True").lower() == "true"
    else False
)


class NLPTestSchema(DefaultBaseModel):
    answer: bool


class SyncAwaiter:
    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self.event_loop = event_loop

    def __call__(self, awaitable: Generator[Any, None, T] | Awaitable[T]) -> T:
        return self.event_loop.run_until_complete(awaitable)  # type: ignore


class _TestLogger(Logger):
    def __init__(self) -> None:
        self.logger = logging.getLogger("TestLogger")

    def set_level(self, log_level: LogLevel) -> None:
        self.logger.setLevel(
            {
                LogLevel.DEBUG: logging.DEBUG,
                LogLevel.INFO: logging.INFO,
                LogLevel.WARNING: logging.WARNING,
                LogLevel.ERROR: logging.ERROR,
                LogLevel.CRITICAL: logging.CRITICAL,
            }[log_level]
        )

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def critical(self, message: str) -> None:
        self.logger.critical(message)

    @contextmanager
    def operation(self, name: str, props: dict[str, Any] = {}) -> Iterator[None]:
        yield


async def nlp_test(context: str, condition: str) -> bool:
    schematic_generator = GPT_4o[NLPTestSchema](logger=_TestLogger())

    inference = await schematic_generator.generate(
        prompt=f"""\
Given a context and a condition, determine whether the
condition applies with respect to the given context.
If the condition applies, the answer is true;
otherwise, the answer is false.

Context: ###
{context}
###

Condition: ###
{condition}
###

Output JSON structure: ###
{{
    answer: <BOOL>
}}
###

Example #1: ###
{{
    answer: true
}}
###

Example #2: ###
{{
    answer: false
}}
###
""",
        hints={"temperature": 0.0, "strict": True},
    )
    return inference.content.answer


async def create_agent(container: Container, name: str) -> Agent:
    return await container[AgentStore].create_agent(name="test-agent")


async def create_customer(container: Container, name: str) -> Customer:
    return await container[CustomerStore].create_customer(
        name=name,
        extra={"email": "test@customer.com"},
    )


async def create_session(
    container: Container,
    agent_id: AgentId,
    customer_id: Optional[CustomerId] = None,
    title: Optional[str] = None,
) -> Session:
    return await container[SessionStore].create_session(
        customer_id or (await create_customer(container, "Auto-Created Customer")).id,
        agent_id=agent_id,
        title=title,
    )


async def create_term(
    container: Container,
    agent_id: AgentId,
    name: str,
    description: str,
    synonyms: list[str],
) -> Term:
    return await container[GlossaryStore].create_term(
        term_set=agent_id,
        name=name,
        description=description,
        synonyms=synonyms,
    )


async def create_context_variable(
    container: Container,
    agent_id: AgentId,
    name: str,
    description: str = "",
) -> ContextVariable:
    return await container[ContextVariableStore].create_variable(
        variable_set=agent_id,
        name=name,
        description=description,
        tool_id=None,
        freshness_rules=None,
    )


async def set_context_variable_value(
    container: Container,
    agent_id: AgentId,
    variable_id: ContextVariableId,
    key: str,
    data: JSONSerializable,
) -> ContextVariableValue:
    return await container[ContextVariableStore].update_value(
        variable_set=agent_id,
        key=key,
        variable_id=variable_id,
        data=data,
    )


async def create_guideline(
    container: Container,
    agent_id: AgentId,
    condition: str,
    action: str,
    tool_function: Optional[Callable[[], ToolResult]] = None,
) -> Guideline:
    guideline = await container[GuidelineStore].create_guideline(
        guideline_set=agent_id,
        condition=condition,
        action=action,
    )

    if tool_function:
        local_tool_service = container[LocalToolService]

        existing_tools = await local_tool_service.list_tools()

        tool = next((t for t in existing_tools if t.name == tool_function.__name__), None)

        if not tool:
            tool = await local_tool_service.create_tool(
                name=tool_function.__name__,
                module_path=tool_function.__module__,
                description="",
                parameters={},
                required=[],
            )

        await container[GuidelineToolAssociationStore].create_association(
            guideline_id=guideline.id,
            tool_id=ToolId("local", tool_function.__name__),
        )

    return guideline


async def read_reply(
    container: Container,
    session_id: SessionId,
    customer_event_offset: int,
) -> Event:
    return next(
        iter(
            await container[SessionStore].list_events(
                session_id=session_id,
                source="ai_agent",
                min_offset=customer_event_offset,
                kinds=["message"],
            )
        )
    )


async def post_message(
    container: Container,
    session_id: SessionId,
    message: str,
    response_timeout: Timeout = Timeout.none(),
) -> Event:
    customer_id = (await container[SessionStore].read_session(session_id)).customer_id
    customer = await container[CustomerStore].read_customer(customer_id)

    data: MessageEventData = {
        "message": message,
        "participant": {
            "id": customer_id,
            "display_name": customer.name,
        },
    }

    event = await container[Application].post_event(
        session_id=session_id,
        kind="message",
        data=data,
    )

    if response_timeout:
        await container[Application].wait_for_update(
            session_id=session_id,
            min_offset=event.offset + 1,
            kinds=["message"],
            timeout=response_timeout,
        )

    return event


async def get_when_async_done_or_timeout(
    result_getter: Callable[[], Awaitable[T]],
    done_condition: Callable[[T], bool],
    timeout: int,
) -> T:
    for _ in range(timeout):
        result = await result_getter()
        if done_condition(result):
            return result
        await asyncio.sleep(1)

    raise TimeoutError()


def get_when_done_or_timeout(
    result_getter: Callable[[], T],
    done_condition: Callable[[T], bool],
    timeout: int,
) -> T:
    for _ in range(timeout):
        result = result_getter()
        if done_condition(result):
            return result
        sleep(1)

    raise TimeoutError()


TBaseModel = TypeVar("TBaseModel", bound=DefaultBaseModel)


class _SchematicGenerationResultDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    content: JSONSerializable
    info: _GenerationInfoDocument


class CachedSchematicGenerator(SchematicGenerator[TBaseModel]):
    VERSION = Version.from_string("0.1.0")

    def __init__(
        self,
        base_generator: SchematicGenerator[TBaseModel],
        collection: DocumentCollection[_SchematicGenerationResultDocument],
    ):
        self._base_generator = base_generator
        self._collection = collection
        self._ensure_cache_file_exists()

    def _ensure_cache_file_exists(self) -> None:
        if not GLOBAL_CACHE_FILE.exists():
            GLOBAL_CACHE_FILE.write_text("{}")

    def _generate_id(
        self,
        prompt: str,
        hints: Mapping[str, Any],
    ) -> str:
        sorted_hints = json.dumps(dict(sorted(hints.items())), sort_keys=True)
        key_content = f"{self.id}:{prompt}:{sorted_hints}"
        return hashlib.sha256(key_content.encode()).hexdigest()

    def _serialize_result(
        self,
        id: str,
        result: SchematicGenerationResult[TBaseModel],
    ) -> _SchematicGenerationResultDocument:
        def serialize_generation_info(generation: GenerationInfo) -> _GenerationInfoDocument:
            return _GenerationInfoDocument(
                schema_name=generation.schema_name,
                model=generation.model,
                duration=generation.duration,
                usage=_UsageInfoDocument(
                    input_tokens=generation.usage.input_tokens,
                    output_tokens=generation.usage.output_tokens,
                    extra=generation.usage.extra,
                ),
            )

        return _SchematicGenerationResultDocument(
            id=ObjectId(id),
            version=self.VERSION.to_string(),
            content=result.content.model_dump(mode="json"),
            info=serialize_generation_info(result.info),
        )

    def _deserialize_result(
        self,
        doc: _SchematicGenerationResultDocument,
        schema_type: type[TBaseModel],
    ) -> SchematicGenerationResult[TBaseModel]:
        def deserialize_generation_info(
            generation_document: _GenerationInfoDocument,
        ) -> GenerationInfo:
            return GenerationInfo(
                schema_name=generation_document["schema_name"],
                model=generation_document["model"],
                duration=generation_document["duration"],
                usage=UsageInfo(
                    input_tokens=generation_document["usage"]["input_tokens"],
                    output_tokens=generation_document["usage"]["output_tokens"],
                    extra=generation_document["usage"]["extra"],
                ),
            )

        content = schema_type.model_validate(doc["content"])
        info = deserialize_generation_info(doc["info"])

        return SchematicGenerationResult[TBaseModel](content=content, info=info)

    async def generate(
        self,
        prompt: str,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[TBaseModel]:
        id = self._generate_id(prompt, hints)

        result_document = await self._collection.find_one(filters={"id": {"$eq": id}})
        if result_document:
            schema_type = (
                self._base_generator.schema
                if type(self._base_generator) is not FallbackSchematicGenerator
                else cast(FallbackSchematicGenerator[TBaseModel], self._base_generator)
                ._generators[0]
                .schema
            )

            return self._deserialize_result(doc=result_document, schema_type=schema_type)

        result = await self._base_generator.generate(prompt, hints)
        await self._collection.insert_one(document=self._serialize_result(id=id, result=result))

        return result

    @property
    def id(self) -> str:
        return self._base_generator.id

    @property
    def max_tokens(self) -> int:
        return self._base_generator.max_tokens

    @property
    def tokenizer(self) -> EstimatingTokenizer:
        return self._base_generator.tokenizer


async def create_schematic_generation_result_collection(
    stack: AsyncExitStack,
    logger: Logger,
) -> DocumentCollection[_SchematicGenerationResultDocument]:
    _db = await stack.enter_async_context(
        JSONFileDocumentDatabase(
            logger,
            PARLANT_HOME_DIR / GLOBAL_CACHE_FILE,
        )
    )

    return await _db.get_or_create_collection(
        name="cache_schematic_generation_results", schema=_SchematicGenerationResultDocument
    )


async def create_schematic_generator(
    base_generator: SchematicGenerator[TBaseModel],
    collection: DocumentCollection[_SchematicGenerationResultDocument],
    cache: Optional[bool] = None,
) -> SchematicGenerator[TBaseModel]:
    if cache is False or (cache is None and CACHE_SCHEMATIC_GENERATION_RESULTS is False):
        return base_generator

    return CachedSchematicGenerator(base_generator, collection)
