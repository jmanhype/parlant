import asyncio
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable, OrderedDict, Sequence

from emcie.server.coherence_checker import CoherenceChecker
from emcie.server.core.common import generate_id
from emcie.server.core.evaluations import (
    CoherenceCheckResult,
    Evaluation,
    EvaluationGuidelinePayload,
    EvaluationId,
    EvaluationInvoice,
    EvaluationInvoiceGuidelineData,
    EvaluationInvoiceId,
    EvaluationItem,
    EvaluationPayload,
    EvaluationStore,
    GuidelineCoherenceCheckResult,
)
from emcie.server.core.guidelines import Guideline, GuidelineId, GuidelineStore
from emcie.server.logger import Logger


class EvaluationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class GuidelineEvaluator:
    def __init__(self, logger: Logger, guideline_store: GuidelineStore) -> None:
        self.logger = logger
        self._guideline_store = guideline_store

    async def evaluate(
        self,
        payloads: Sequence[EvaluationPayload],
    ) -> Sequence[EvaluationInvoiceGuidelineData]:
        if len({p["guideline_set"] for p in payloads}) > 1:
            raise EvaluationError("Evaluation task must be processed for a single guideline_set.")

        await self._check_for_duplications(payloads)

        coherence_results = await self._check_for_coherence(payloads)

        return [
            EvaluationInvoiceGuidelineData(type="guideline", detail=c) for c in coherence_results
        ]

    async def _check_for_duplications(
        self,
        payloads: Sequence[EvaluationPayload],
    ) -> None:
        seen_guidelines = set(
            (payload["guideline_set"], payload["predicate"], payload["content"])
            for payload in payloads
        )
        if len(seen_guidelines) < len(payloads):
            raise EvaluationError("Duplicate guideline found among the provided guidelines.")

        guideline_set = payloads[0]["guideline_set"]
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
            raise EvaluationError(
                f"Duplicate guideline found against existing guidelines: {self._render_guideline(guideline)} in {guideline_set} guideline_set"
            )

    async def _check_for_coherence(
        self,
        payloads: Sequence[EvaluationPayload],
    ) -> Iterable[GuidelineCoherenceCheckResult]:
        checker = CoherenceChecker(self.logger)

        proposed_guidelines = OrderedDict()

        for p in payloads:
            id = GuidelineId(generate_id())
            proposed_guidelines[id] = Guideline(
                id=id,
                creation_utc=datetime.now(timezone.utc),
                predicate=p["predicate"],
                content=p["content"],
            )

        existing_guidelines = {
            g.id: g
            for g in await self._guideline_store.list_guidelines(
                guideline_set=payloads[0]["guideline_set"]
            )
        }

        contradictions = [
            contradiction
            for contradiction in await checker.evaluate_coherence(
                proposed_guidelines=list(proposed_guidelines.values()),
                existing_guidelines=list(existing_guidelines.values()),
            )
            if contradiction.severity > 6
        ]

        guideline_coherence_results: OrderedDict[GuidelineId, GuidelineCoherenceCheckResult] = (
            OrderedDict(
                {
                    g_id: GuidelineCoherenceCheckResult(type="coherence_check", data=[])
                    for g_id in proposed_guidelines
                }
            )
        )

        for contradiction in contradictions:
            existing_guideline = (
                existing_guidelines[contradiction.existing_guideline_id]
                if contradiction.existing_guideline_id in existing_guidelines
                else proposed_guidelines[contradiction.existing_guideline_id]
            )

            guideline_coherence_results[contradiction.proposed_guideline_id]["data"].append(
                CoherenceCheckResult(
                    proposed=self._render_guideline(
                        proposed_guidelines[contradiction.proposed_guideline_id]
                    ),
                    existing=self._render_guideline(existing_guideline),
                    issue=contradiction.rationale,
                    severity=contradiction.severity,
                )
            )

        return guideline_coherence_results.values()

    def _render_guideline(self, guideline: Guideline) -> str:
        return f"When {guideline.predicate}, then {guideline.content}"


class BehavioralChangeEvaluator:
    def __init__(
        self, logger: Logger, evaluation_store: EvaluationStore, guideline_store: GuidelineStore
    ) -> None:
        self.logger = logger
        self._evaluation_store = evaluation_store
        self._guideline_evaluator = GuidelineEvaluator(
            logger=logger, guideline_store=guideline_store
        )

    async def create_evaluation_task(
        self,
        payloads: Sequence[EvaluationGuidelinePayload],
    ) -> EvaluationId:
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
                    for e in await self._evaluation_store.list_active_evaluations()
                    if e.status == "running" and e.id != evaluation.id
                ),
                None,
            ):
                raise EvaluationError(f"An evaluation task '{running_task.id}' is already running.")

            await self._evaluation_store.update_evaluation(
                evaluation_id=evaluation.id,
                status="running",
            )

            results = await self._guideline_evaluator.evaluate(
                [item["payload"] for item in evaluation.items]
            )

            for i, result in enumerate(results):
                invoice_id = EvaluationInvoiceId(generate_id())

                invoice = EvaluationInvoice(
                    id=invoice_id,
                    state_version=str(hash(invoice_id)),
                    checksum=self._generate_checksum(evaluation.items[i]["payload"]),
                    approved=True if len(result["detail"]["data"]) == 0 else False,
                    data=result,
                )

                await self._evaluation_store.update_evaluation(
                    evaluation.id,
                    status=evaluation.status,
                    item=EvaluationItem(
                        id=evaluation.items[i]["id"],
                        payload=evaluation.items[i]["payload"],
                        invoice=invoice,
                        error=None,
                    ),
                )

            self.logger.info(f"evaluation task '{evaluation.id}' completed")

            await self._evaluation_store.update_evaluation(
                evaluation_id=evaluation.id,
                status="completed",
            )

        except Exception as exc:
            logger_level = "info" if isinstance(exc, EvaluationError) else "error"
            getattr(self.logger, logger_level)(
                f"Evaluation task '{evaluation.id}' failed due to the following error: '{str(exc)}'"
            )
            await self._evaluation_store.update_evaluation(
                evaluation_id=evaluation.id,
                status="failed",
                error=str(exc),
            )

    @staticmethod
    def _generate_checksum(payload: EvaluationGuidelinePayload) -> str:
        md5_hash = hashlib.md5()
        md5_hash.update(f"{json.dumps(payload)}".encode("utf-8"))
        return md5_hash.hexdigest()
