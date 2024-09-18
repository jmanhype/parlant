from pytest_bdd import scenarios
from tests.core.engines.alpha.utils import load_steps


load_steps(
    "agents",
    "context_variables",
    "engines",
    "events",
    "guidelines",
    "sessions",
    "terms",
    "tools",
)

scenarios(
    *(
        f"core/engines/alpha/features/{feature}.feature"
        for feature in (
            "guideline_connections",
            "message_agent_with_rules",
            "proactive_agent",
            "single_tool_event",
            "supervision",
            "terminology",
            "vanilla_agent",
        )
    )
)
