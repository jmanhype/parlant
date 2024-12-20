from datetime import datetime, timezone
from lagom import Container

from parlant.core.agents import Agent
from parlant.core.customers import Customer
from parlant.core.engines.alpha.guideline_proposer import (
    GuidelineProposer,
    GuidelinePropositionSchema,
    GuidelinePropositionShot,
    GuidelinePropositionsSchema,
)
from parlant.core.guidelines import GuidelineContent
from parlant.core.sessions import Event, EventId
from parlant.core.shots import ShotCollection


async def test_that_appended_shot_is_displayed_in_guideline_proposer_prompt(
    container: Container,
    agent: Agent,
    customer: Customer,
) -> None:
    guideline_proposer = container[GuidelineProposer]
    shot_collection = container[ShotCollection[GuidelinePropositionShot]]

    guideline_content = GuidelineContent(
        condition="A user compliments the product",
        action="Tell him to stop being a bitch",
    )

    guideline_proposition_shot = GuidelinePropositionShot(
        description="Test Shot Description",
        interaction_events=[
            Event(
                id=EventId("test_id"),
                source="customer",
                kind="message",
                creation_utc=datetime.now(timezone.utc),
                offset=0,
                correlation_id="",
                data={"message": "This is a very cool feature, man!"},
                deleted=False,
            )
        ],
        guidelines=[guideline_content],
        expected_result=GuidelinePropositionsSchema(
            checks=[
                GuidelinePropositionSchema(
                    guideline_number=1,
                    condition=guideline_content.condition,
                    condition_application_rationale="Rationale: The user said that the feature is cool",
                    condition_applies=True,
                    action=guideline_content.action,
                    guideline_previously_applied="fully",
                    applies_score=8,
                )
            ]
        ),
    )

    await shot_collection.append(guideline_proposition_shot)

    shots = await shot_collection.list()
    prompt = guideline_proposer._format_prompt(
        agents=[agent],
        customer=customer,
        context_variables=[],
        interaction_history=[],
        staged_events=[],
        terms=[],
        guidelines={},
        shots=shots,
    )

    assert "Rationale: The user said that the feature is cool" in prompt
    assert "This is a very cool feature, man!" in prompt
    assert "Tell him to stop being a bitch" in prompt
