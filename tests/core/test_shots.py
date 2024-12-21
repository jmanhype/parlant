from datetime import datetime, timezone
from lagom import Container

from parlant.core.engines.alpha.guideline_proposer import (
    GuidelineProposer,
    GuidelinePropositionSchema,
    GuidelinePropositionShot,
    GuidelinePropositionsSchema,
)
from parlant.core.engines.alpha.tool_caller import ToolCallInferenceSchema, ToolCallerInferenceShot
from parlant.core.engines.alpha.tool_event_generator import ToolEventGenerator
from parlant.core.guidelines import GuidelineContent
from parlant.core.sessions import Event, EventId
from parlant.core.shots import ShotCollection


async def test_that_appended_shot_is_displayed_in_guideline_proposer_prompt(
    container: Container,
) -> None:
    guideline_proposer = container[GuidelineProposer]
    shot_collection = container[ShotCollection[GuidelinePropositionShot]]

    guideline_content = GuidelineContent(
        condition="A user compliments the product",
        action="Thank him with in Portuguese",
    )

    new_shot = GuidelinePropositionShot(
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

    await shot_collection.append(new_shot)

    shots = await guideline_proposer.shots()

    assert new_shot in shots


async def test_that_appended_shot_is_displayed_in_tool_caller_shots(
    container: Container,
) -> None:
    tool_caller = container[ToolEventGenerator].tool_caller
    shot_collection = container[ShotCollection[ToolCallerInferenceShot]]

    new_shot = ToolCallerInferenceShot(
        description="Test Shot Description",
        context="Test shot - checking if appended shot is reflected by tool_caller.shots()",
        expected_result=ToolCallInferenceSchema(
            last_customer_message="Testing shot append",
            most_recent_customer_inquiry_or_need="Verifying tool caller logic",
            most_recent_customer_inquiry_or_need_was_already_resolved=False,
            name="test_tool",
            subtleties_to_be_aware_of="",
            tool_calls_for_candidate_tool=[],
        ),
    )

    await shot_collection.append(new_shot)

    shots = await tool_caller.shots()
    assert new_shot in shots
