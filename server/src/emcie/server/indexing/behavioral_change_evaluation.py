import asyncio
from typing import Optional, OrderedDict, Sequence

from emcie.server.core.evaluations import (
    CoherenceCheckResult,
    ConnectionPropositionResult,
    EvaluationGuidelineCoherenceCheckResult,
    Evaluation,
    EvaluationGuidelinePayload,
    EvaluationId,
    EvaluationInvoice,
    EvaluationInvoiceGuidelineData,
    EvaluationPayload,
    EvaluationStore,
    EvaluationGuidelineConnectionPropositionsResult,
)
from emcie.server.core.guidelines import Guideline, GuidelineData, GuidelineStore
from emcie.server.indexing.coherence_checker import CoherenceChecker, ContradictionTest
from emcie.server.indexing.guideline_connection_proposer import GuidelineConnectionProposer
from emcie.server.logger import Logger
from emcie.server.utils import md5_checksum


class EvaluationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class EvaluationValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class GuidelineEvaluator:
    def __init__(
        self,
        logger: Logger,
        guideline_store: GuidelineStore,
        guideline_connection_proposer: GuidelineConnectionProposer,
    ) -> None:
        self.logger = logger
        self._guideline_store = guideline_store
        self._guideline_connection_proposer = guideline_connection_proposer

    async def evaluate(
        self,
        payloads: Sequence[EvaluationPayload],
    ) -> Sequence[EvaluationInvoiceGuidelineData]:
        guideline_set = payloads[0].guideline_set

        guideline_to_evaluate = [
            GuidelineData(
                predicate=p.predicate,
                content=p.content,
            )
            for p in payloads
        ]

        existing_guidelines = await self._guideline_store.list_guidelines(
            guideline_set=guideline_set
        )

        coherence_results = await self._check_for_coherence(
            guideline_to_evaluate, existing_guidelines
        )

        if coherence_results:
            return [
                EvaluationInvoiceGuidelineData(
                    type="guideline",
                    coherence_check_detail=coherence_result,
                    connections_detail=None,
                )
                for coherence_result in coherence_results
            ]

        connections_results = await self._propose_guideline_connections(
            guideline_to_evaluate, existing_guidelines
        )

        if connections_results:
            return [
                EvaluationInvoiceGuidelineData(
                    type="guideline",
                    coherence_check_detail=None,
                    connections_detail=connections_result,
                )
                for connections_result in connections_results
            ]

        else:
            return [
                EvaluationInvoiceGuidelineData(
                    type="guideline",
                    coherence_check_detail=None,
                    connections_detail=None,
                )
                for _ in range(len(payloads))
            ]

    async def _check_for_coherence(
        self,
        guidelines_to_evaluate: Sequence[GuidelineData],
        existing_guidelines: Sequence[Guideline],
    ) -> Optional[Sequence[EvaluationGuidelineCoherenceCheckResult]]:
        checker = CoherenceChecker(self.logger)

        coherence_check_results = await checker.evaluate_coherence(
            guidelines_to_evaluate=guidelines_to_evaluate,
            comparison_guidelines=[
                GuidelineData(predicate=g.predicate, content=g.content) for g in existing_guidelines
            ],
        )

        contradictions: dict[str, ContradictionTest] = {}

        for c in coherence_check_results:
            key = f"{c.guideline_a.predicate}{c.guideline_a.content}"
            if (c.severity >= 6) and (
                key not in contradictions or c.severity > contradictions[key].severity
            ):
                contradictions[key] = c

        if not contradictions:
            return None

        guideline_coherence_results: OrderedDict[str, list[CoherenceCheckResult]] = OrderedDict(
            {f"{g.predicate}{g.content}": [] for g in guidelines_to_evaluate}
        )

        for c in contradictions.values():
            guideline_coherence_results[f"{c.guideline_a.predicate}{c.guideline_a.content}"].append(
                CoherenceCheckResult(
                    type="Contradiction With Other Proposed Guideline"
                    if f"{c.guideline_b.predicate}{c.guideline_b.content}"
                    in guideline_coherence_results
                    else "Contradiction With Existing Guideline",
                    first=c.guideline_a,
                    second=c.guideline_b,
                    issue=c.rationale,
                    severity=c.severity,
                )
            )

            if f"{c.guideline_b.predicate}{c.guideline_b.content}" in guideline_coherence_results:
                guideline_coherence_results[
                    f"{c.guideline_b.predicate}{c.guideline_b.content}"
                ].append(
                    CoherenceCheckResult(
                        type="Contradiction With Other Proposed Guideline",
                        first=c.guideline_a,
                        second=c.guideline_b,
                        issue=c.rationale,
                        severity=c.severity,
                    )
                )

        return [
            EvaluationGuidelineCoherenceCheckResult(coherence_checks=v)
            for v in guideline_coherence_results.values()
        ]

    async def _propose_guideline_connections(
        self,
        proposed_guidelines: Sequence[GuidelineData],
        existing_guidelines: Sequence[Guideline],
    ) -> Optional[Sequence[EvaluationGuidelineConnectionPropositionsResult]]:
        connection_propositions = [
            p
            for p in await self._guideline_connection_proposer.propose_connections(
                introduced_guidelines=proposed_guidelines,
                existing_guidelines=[
                    GuidelineData(predicate=g.predicate, content=g.content)
                    for g in existing_guidelines
                ],
            )
            if p.score >= 6
        ]

        if not connection_propositions:
            return None

        connection_results: OrderedDict[str, list[ConnectionPropositionResult]] = OrderedDict(
            {f"{g.predicate}{g.content}": [] for g in proposed_guidelines}
        )

        for c in connection_propositions:
            if f"{c.source.predicate}{c.source.content}" in connection_results:
                connection_results[f"{c.source.predicate}{c.source.content}"].append(
                    ConnectionPropositionResult(
                        type="Connection With Other Proposed Guideline"
                        if f"{c.target.predicate}{c.target.content}" in connection_results
                        else "Connection With Existing Guideline",
                        source=c.source,
                        target=c.target,
                        kind=c.kind,
                    )
                )

            if f"{c.target.predicate}{c.target.content}" in connection_results:
                connection_results[f"{c.target.predicate}{c.target.content}"].append(
                    ConnectionPropositionResult(
                        type="Connection With Other Proposed Guideline"
                        if f"{c.source.predicate}{c.source.content}" in connection_results
                        else "Connection With Existing Guideline",
                        source=c.source,
                        target=c.target,
                        kind=c.kind,
                    )
                )

        return [
            EvaluationGuidelineConnectionPropositionsResult(connection_propositions=v)
            for v in connection_results.values()
        ]


class BehavioralChangeEvaluator:
    def __init__(
        self,
        logger: Logger,
        evaluation_store: EvaluationStore,
        guideline_store: GuidelineStore,
        guideline_connection_proposer: GuidelineConnectionProposer,
    ) -> None:
        self.logger = logger
        self._evaluation_store = evaluation_store
        self._guideline_store = guideline_store
        self._guideline_evaluator = GuidelineEvaluator(
            logger=logger,
            guideline_store=guideline_store,
            guideline_connection_proposer=guideline_connection_proposer,
        )

    async def validate_payloads(
        self,
        payloads: Sequence[EvaluationGuidelinePayload],
    ) -> None:
        if not payloads:
            raise EvaluationValidationError("No payloads provided for the evaluation task.")

        guideline_set = payloads[0].guideline_set

        if len({p.guideline_set for p in payloads}) > 1:
            raise EvaluationValidationError(
                "Evaluation task must be processed for a single guideline_set."
            )

        async def _check_for_duplications() -> None:
            seen_guidelines = set(
                (payload.guideline_set, payload.predicate, payload.content) for payload in payloads
            )
            if len(seen_guidelines) < len(payloads):
                raise EvaluationValidationError(
                    "Duplicate guideline found among the provided guidelines."
                )

            existing_guidelines = await self._guideline_store.list_guidelines(
                guideline_set=guideline_set
            )

            if guideline := next(
                iter(
                    g
                    for g in existing_guidelines
                    if (
                        guideline_set,
                        g.predicate,
                        g.content,
                    )
                    in seen_guidelines
                ),
                None,
            ):
                raise EvaluationValidationError(
                    f"Duplicate guideline found against existing guidelines: {str(guideline)} in {guideline_set} guideline_set"
                )

        await _check_for_duplications()

    async def create_evaluation_task(
        self,
        payloads: Sequence[EvaluationGuidelinePayload],
    ) -> EvaluationId:
        await self.validate_payloads(payloads)

        evaluation = await self._evaluation_store.create_evaluation(payloads)

        asyncio.create_task(self.run_evaluation(evaluation))

        return evaluation.id

    async def run_evaluation(
        self,
        evaluation: Evaluation,
    ) -> None:
        self.logger.info(f"Starting evaluation task '{evaluation.id}'")

        try:
            if running_task := next(
                iter(
                    e
                    for e in await self._evaluation_store.list_evaluations()
                    if e.status == "running" and e.id != evaluation.id
                ),
                None,
            ):
                raise EvaluationError(f"An evaluation task '{running_task.id}' is already running.")

            await self._evaluation_store.update_evaluation_status(
                evaluation_id=evaluation.id,
                status="running",
            )

            guideline_results = await self._guideline_evaluator.evaluate(
                payloads=[
                    invoice.payload
                    for invoice in evaluation.invoices
                    if invoice.payload.type == "guideline"
                ],
            )

            for i, result in enumerate(guideline_results):
                invoice_checksum = md5_checksum(str(evaluation.invoices[i].payload))
                state_version = str(hash("Temporarily"))

                invoice = EvaluationInvoice(
                    payload=evaluation.invoices[i].payload,
                    checksum=invoice_checksum,
                    state_version=state_version,
                    approved=True if not result.coherence_check_detail else False,
                    data=result,
                    error=None,
                )

                await self._evaluation_store.update_evaluation_invoice(
                    evaluation.id,
                    invoice_index=i,
                    updated_invoice=invoice,
                )

            self.logger.info(f"evaluation task '{evaluation.id}' completed")

            await self._evaluation_store.update_evaluation_status(
                evaluation_id=evaluation.id,
                status="completed",
            )

        except Exception as exc:
            logger_level = "info" if isinstance(exc, EvaluationError) else "error"
            getattr(self.logger, logger_level)(
                f"Evaluation task '{evaluation.id}' failed due to the following error: '{str(exc)}'"
            )
            await self._evaluation_store.update_evaluation_status(
                evaluation_id=evaluation.id,
                status="failed",
                error=str(exc),
            )
