import asyncio
from lagom import Container
from pytest import raises

from emcie.server.behavioral_change_evaluation import (
    BehavioralChangeEvaluator,
    EvaluationValidationError,
)
from emcie.server.core.evaluations import EvaluationGuidelinePayload, EvaluationStore
from emcie.server.core.guidelines import GuidelineStore
from tests.test_mc import REASONABLE_AMOUNT_OF_TIME


async def test_that_a_new_evaluation_starts_with_a_pending_status(
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]
    evaluation_store = container[EvaluationStore]

    payloads = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="the user greets you",
            content="greet them back with 'Hello'",
        )
    ]

    evaluation_id = await evaluation_service.create_evaluation_task(payloads=payloads)

    evaluation = await evaluation_store.read_evaluation(evaluation_id)

    assert evaluation.status == "pending"


async def test_that_an_evaluation_completes_when_all_invoices_have_data(
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]
    evaluation_store = container[EvaluationStore]

    payloads = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="the user greets you",
            content="greet them back with 'Hello'",
        )
    ]
    evaluation_id = await evaluation_service.create_evaluation_task(payloads)

    await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    evaluation = await evaluation_store.read_evaluation(evaluation_id)

    assert evaluation.status == "completed"

    assert len(evaluation.invoices) == 1

    assert evaluation.invoices[0].approved
    assert evaluation.invoices[0].data is not None


async def test_that_an_evaluation_of_a_coherent_guideline_completes_with_an_approved_invoice(
    container: Container,
) -> None:
    guideline_store = container[GuidelineStore]
    evaluation_service = container[BehavioralChangeEvaluator]
    evaluation_store = container[EvaluationStore]

    await guideline_store.create_guideline(
        guideline_set="test-set",
        predicate="a customer inquires about upgrading their service package",
        content="provide information on available upgrade options and benefits",
    )

    payloads = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="a customer needs assistance with understanding their billing statements",
            content="guide them through the billing details and explain any charges",
        )
    ]

    evaluation_id = await evaluation_service.create_evaluation_task(payloads=payloads)

    await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    evaluation = await evaluation_store.read_evaluation(evaluation_id)

    assert evaluation.status == "completed"

    assert len(evaluation.invoices) == 1

    assert evaluation.invoices[0].approved

    assert evaluation.invoices[0].data
    assert evaluation.invoices[0].data.type == "guideline"

    assert len(evaluation.invoices[0].data.detail["coherence_checks"]) == 0


async def test_that_an_evaluation_of_an_incoherent_guideline_completes_with_an_unapproved_invoice(
    container: Container,
) -> None:
    guideline_store = container[GuidelineStore]
    evaluation_service = container[BehavioralChangeEvaluator]
    evaluation_store = container[EvaluationStore]

    await guideline_store.create_guideline(
        guideline_set="test-agent",
        predicate="a VIP customer requests a specific feature that aligns with their business needs but is not on the current product roadmap",
        content="escalate the request to product management for special consideration",
    )

    payloads = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="any customer requests a feature not available in the current version",
            content="inform them about the product roadmap and upcoming features",
        )
    ]

    evaluation_id = await evaluation_service.create_evaluation_task(payloads=payloads)

    await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    evaluation = await evaluation_store.read_evaluation(evaluation_id)

    assert evaluation.status == "completed"

    assert len(evaluation.invoices) == 1

    assert evaluation.invoices[0]
    assert not evaluation.invoices[0].approved

    assert evaluation.invoices[0].data
    assert evaluation.invoices[0].data.type == "guideline"

    assert len(evaluation.invoices[0].data.detail["coherence_checks"]) == 1


async def test_that_an_evaluation_of_an_incoherent_proposed_guidelines_completes_with_an_unapproved_invoice(
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]
    evaluation_store = container[EvaluationStore]

    payloads = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="any customer requests a feature not available in the current version",
            content="inform them about the product roadmap and upcoming features",
        ),
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="a VIP customer requests a specific feature that aligns with their business needs but is not on the current product roadmap",
            content="escalate the request to product management for special consideration",
        ),
    ]

    evaluation_id = await evaluation_service.create_evaluation_task(payloads=payloads)

    await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    evaluation = await evaluation_store.read_evaluation(evaluation_id)

    assert evaluation.status == "completed"

    assert len(evaluation.invoices) == 1

    assert evaluation.invoices[0]
    assert not evaluation.invoices[0].approved

    assert evaluation.invoices[0].data
    assert evaluation.invoices[0].data.type == "guideline"

    assert len(evaluation.invoices[0].data.detail["coherence_checks"]) == 1

    assert len(evaluation.invoices[1].data.detail["coherence_checks"]) == 1


async def test_that_an_evaluation_of_multiple_payloads_completes_with_an_invoice_containing_data_for_each(
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]
    evaluation_store = container[EvaluationStore]

    payloads = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="the user greets you",
            content="greet them back with 'Hello'",
        ),
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="the user asks about the weather",
            content="provide a weather update",
        ),
    ]
    evaluation_id = await evaluation_service.create_evaluation_task(payloads)

    await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    evaluation = await evaluation_store.read_evaluation(evaluation_id)

    assert evaluation.status == "completed"
    assert len(evaluation.invoices) == len(payloads)

    for invoice in evaluation.invoices:
        assert invoice.approved
        assert invoice.data


async def test_that_an_evaluation_that_failed_due_to_already_running_evaluation_task_contains_its_error_details(
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]
    evaluation_store = container[EvaluationStore]

    payload_with_contradictions = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="the user greets you",
            content="greet them back with 'Hello'",
        ),
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="the user greets you",
            content="greet them back with 'Hola'",
        ),
    ]
    first_evaluation_id = await evaluation_service.create_evaluation_task(
        payloads=payload_with_contradictions
    )

    second_payloads = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="test-agent",
            predicate="the user asks about the weather",
            content="provide a weather update",
        )
    ]

    reasonable_amount_of_time_until_task_starts = 1
    await asyncio.sleep(reasonable_amount_of_time_until_task_starts)

    second_evaluation_id = await evaluation_service.create_evaluation_task(payloads=second_payloads)

    await asyncio.sleep(reasonable_amount_of_time_until_task_starts)

    evaluation = await evaluation_store.read_evaluation(second_evaluation_id)

    assert evaluation.status == "failed"
    assert evaluation.error == f"An evaluation task '{first_evaluation_id}' is already running."


async def test_that_an_evaluation_validation_failed_due_multiple_guideline_sets_contains_relevant_error_details(
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]

    payloads = [
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="set-1",
            predicate="the user greets you",
            content="greet them back with 'Hello'",
        ),
        EvaluationGuidelinePayload(
            type="guideline",
            guideline_set="set-2",
            predicate="the user asks about the weather",
            content="provide a weather update",
        ),
    ]

    with raises(EvaluationValidationError) as exc:
        await evaluation_service.create_evaluation_task(payloads=payloads)
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    assert str(exc.value) == "Evaluation task must be processed for a single guideline_set."


async def test_that_an_evaluation_validation_failed_due_to_guidelines_duplication_in_the_payloads_contains_relevant_error_details(
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]

    duplicate_payload = EvaluationGuidelinePayload(
        type="guideline",
        guideline_set="test-agent",
        predicate="the user greets you",
        content="greet them back with 'Hello'",
    )

    with raises(EvaluationValidationError) as exc:
        await evaluation_service.create_evaluation_task(
            payloads=[
                duplicate_payload,
                duplicate_payload,
            ]
        )
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    assert str(exc.value) == "Duplicate guideline found among the provided guidelines."


async def test_that_an_evaluation_validation_failed_due_to_duplicate_guidelines_with_existing_contains_relevant_error_details(
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]
    guideline_store = container[GuidelineStore]

    await guideline_store.create_guideline(
        guideline_set="test-agent",
        predicate="the user greets you",
        content="greet them back with 'Hello'",
    )

    duplicate_payload = EvaluationGuidelinePayload(
        type="guideline",
        guideline_set="test-agent",
        predicate="the user greets you",
        content="greet them back with 'Hello'",
    )
    with raises(EvaluationValidationError) as exc:
        await evaluation_service.create_evaluation_task(
            payloads=[
                duplicate_payload,
            ]
        )
        await asyncio.sleep(REASONABLE_AMOUNT_OF_TIME)

    assert (
        str(exc.value)
        == "Duplicate guideline found against existing guidelines: When the user greets you, then greet them back with 'Hello' in test-agent guideline_set"
    )
