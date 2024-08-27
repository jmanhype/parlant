import asyncio
from datetime import datetime, timezone
from typing import Iterable, Optional, OrderedDict, Sequence

from emcie.server.coherence_checker import CoherenceChecker, ContradictionTest
from emcie.server.core.common import generate_id
from emcie.server.core.evaluations import (
    CoherenceCheckResult,
    Evaluation,
    EvaluationGuidelinePayload,
    EvaluationId,
    EvaluationInvoice,
    EvaluationInvoiceGuidelineData,
    EvaluationPayload,
    EvaluationStore,
    GuidelineCoherenceCheckResult,
    GuidelineConnectionPropositions,
)
from emcie.server.core.guidelines import Guideline, GuidelineId, GuidelineStore
from emcie.server.guideline_connection_proposer import GuidelineConnectionProposer
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
        guideline_set: str,
        payloads: Sequence[EvaluationPayload],
    ) -> Sequence[EvaluationInvoiceGuidelineData]:
        proposed_guidelines = [
            Guideline(
                id=GuidelineId(generate_id()),
                creation_utc=datetime.now(timezone.utc),
                predicate=p.predicate,
                content=p.content,
            )
            for p in payloads
        ]

        existing_guidelines = await self._guideline_store.list_guidelines(
            guideline_set=guideline_set
        )

        coherence_results = await self._check_for_coherence(
            proposed_guidelines, existing_guidelines
        )

        if coherence_results:
            return [
                EvaluationInvoiceGuidelineData(type="guideline", detail=c)
                for c in coherence_results
            ]

        connection_propositions = await self._propose_guideline_connections(
            proposed_guidelines, existing_guidelines
        )

        return [
            EvaluationInvoiceGuidelineData(type="guideline", detail=c) for c in connection_propositions
        ]

    async def _propose_guideline_connections(
            self,
        proposed_guidelines: Sequence[Guideline],
        existing_guidelines: Sequence[Guideline],
    ) -> Sequence[GuidelineConnectionPropositions]:
        connection_propositions = await self._guideline_connection_proposer.propose_connections(
            introduced_guidelines=proposed_guidelines,
            existing_guidelines=existing_guidelines,
        )

        

    )
    async def _check_for_coherence(
        self,
        proposed_guidelines: Sequence[Guideline],
        existing_guidelines: Sequence[Guideline],
    ) -> Sequence[GuidelineCoherenceCheckResult]:
        checker = CoherenceChecker(self.logger)

        coherence_check_results = await checker.evaluate_coherence(
            proposed_guidelines=proposed_guidelines,
            existing_guidelines=existing_guidelines,
        )

        contradictions: dict[str, ContradictionTest] = {}

        for c in coherence_check_results:
            key = (
                f"{c.guideline_a_id}_{c.guideline_b_id}"
                if c.guideline_a_id > c.guideline_b_id
                else f"{c.guideline_b_id}_{c.guideline_a_id}"
            )
            if (
                c.severity >= 6
                and key in contradictions
                and c.severity > contradictions[key].severity
            ):
                contradictions[key] = c

        if not contradictions:
            return []

        guideline_coherence_results: OrderedDict[
            GuidelineId, tuple[Guideline, GuidelineCoherenceCheckResult]
        ] = OrderedDict(
            {
                g.id: (g, GuidelineCoherenceCheckResult(coherence_checks=[]))
                for g in proposed_guidelines
            }
        )

        for c in contradictions.values():
            if guideline := next(
                iter(g for g in existing_guidelines if g.id == c.guideline_a_id), None
            ):
                guideline_b = guideline
            else:
                guideline_b = next(iter(g for g in proposed_guidelines if g.id == c.guideline_a_id))

            guideline_coherence_results[c.guideline_a_id][1]["coherence_checks"].append(
                CoherenceCheckResult(
                    guideline_a=str(guideline_coherence_results[c.guideline_a_id][0]),
                    guideline_b=str(guideline_b),
                    issue=c.rationale,
                    severity=c.severity,
                )
            )

            if c.guideline_b_id in guideline_coherence_results:
                guideline_coherence_results[c.guideline_b_id][1]["coherence_checks"].append(
                    CoherenceCheckResult(
                        guideline_a=str(guideline_coherence_results[c.guideline_a_id][0]),
                        guideline_b=str(guideline_b),
                        issue=c.rationale,
                        severity=c.severity,
                    )
                )

        return [
            guideline_cohrence_check_result
            for g, guideline_cohrence_check_result in guideline_coherence_results.values()
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
        guideline_set: str,
        payloads: Sequence[EvaluationGuidelinePayload],
    ) -> None:
        if not payloads:
            raise EvaluationValidationError("No payloads provided for the evaluation task.")

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
        guideline_set = payloads[0].guideline_set

        await self.validate_payloads(guideline_set, payloads)

        evaluation = await self._evaluation_store.create_evaluation(payloads)

        asyncio.create_task(self.run_evaluation(evaluation, guideline_set))

        return evaluation.id

    async def run_evaluation(
        self,
        evaluation: Evaluation,
        guideline_set: str,
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

            self.logger.info(f"DorZo B: {evaluation.invoices}")
            guideline_results = await self._guideline_evaluator.evaluate(
                guideline_set=guideline_set,
                payloads=[
                    invoice.payload
                    for invoice in evaluation.invoices
                    if invoice.payload.type == "guideline"
                ],
            )
            self.logger.info("DorZo C")

            for i, result in enumerate(guideline_results):
                invoice_checksum = md5_checksum(str(evaluation.invoices[i].payload))
                state_version = str(hash("Temporarily"))

                invoice = EvaluationInvoice(
                    payload=evaluation.invoices[i].payload,
                    checksum=invoice_checksum,
                    state_version=state_version,
                    approved=True if len(result.detail["coherence_checks"]) == 0 else False,
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
