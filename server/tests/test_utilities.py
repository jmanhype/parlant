import asyncio
from contextlib import contextmanager
import logging
from typing import Any, Awaitable, Generator, Iterator, TypeVar

from emcie.server.adapters.nlp.openai import GPT_4o
from emcie.server.core.logging import Logger
from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.services.indexing.coherence_checker import (
    ActionsContradictionChecker,
    PredicatesEntailmentChecker,
    IncoherencyTest,
)

T = TypeVar("T")


class NLPTestSchema(DefaultBaseModel):
    answer: bool


class SyncAwaiter:
    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self.event_loop = event_loop

    def __call__(self, awaitable: Generator[Any, None, T] | Awaitable[T]) -> T:
        return self.event_loop.run_until_complete(awaitable)  # type: ignore


class TestLogger(Logger):
    def __init__(self) -> None:
        self.logger = logging.getLogger("TestLogger")

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


async def nlp_test(context: str, predicate: str) -> bool:
    schematic_generator = GPT_4o[NLPTestSchema](logger=TestLogger())

    inference = await schematic_generator.generate(
        prompt=f"""\
Given a context and a predicate, determine whether the
predicate applies with respect to the given context.
If the predicate applies, the answer is true;
otherwise, the answer is false.

Context: ###
{context}
###

Predicate: ###
{predicate}
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


async def action_contradiction_nlp_test(incoherency: IncoherencyTest) -> bool:
    prompt = f"""Here is an explanation of what an 'actions contradiction' is:
{ActionsContradictionChecker.get_task_description()}
Such a contradiction was found between these two guidelines:
{{when: "{incoherency.guideline_a.predicate}", then: {incoherency.guideline_a.action}"}}
{{when: "{incoherency.guideline_b.predicate}", then: {incoherency.guideline_b.action}"}}
The rationale for marking these guidelines as contradicting is: 
{incoherency.actions_contradiction_rationale}

Given these two guidelines and the rationale behind marking their 'then' statements as contradictory, determine whether this rationale correctly applies.
If the rationale applies, return true. Otherwise return false.

Output JSON structure: ###
{{
    answer: <BOOL>
}}
###
"""

    schematic_generator = GPT_4o[NLPTestSchema](logger=TestLogger())
    inference = await schematic_generator.generate(
        prompt,
        hints={"temperature": 0.0, "strict": True},
    )
    return inference.content.answer


async def predicate_entailment_nlp_test(incoherency: IncoherencyTest) -> bool:
    prompt = f"""Here is an explanation of what a 'actions contradiction' is:
{PredicatesEntailmentChecker.get_task_description()}
Such a contradiction was found between these two guidelines:
{{when: "{incoherency.guideline_a.predicate}", then: {incoherency.guideline_a.action}"}}
{{when: "{incoherency.guideline_b.predicate}", then: {incoherency.guideline_b.action}"}}
The rationale for marking these guidelines as contradicting is: 
{incoherency.predicates_entailment_rationale}

Given these two guidelines and the rationale behind marking their 'when' statements as entailing, determine whether this rationale correctly applies.
If the rationale applies, return true. Otherwise return false.

Output JSON structure: ###
{{
    answer: <BOOL>
}}
###

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
"""

    schematic_generator = GPT_4o[NLPTestSchema](logger=TestLogger())
    inference = await schematic_generator.generate(
        prompt,
        hints={"temperature": 0.0, "strict": True},
    )
    return inference.content.answer
