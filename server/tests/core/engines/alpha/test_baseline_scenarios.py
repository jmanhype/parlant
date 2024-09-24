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
            "conversation",
            "errors",
            "guideline_connections",
            "proactivity",
            "supervision",
            "terminology",
            "tools",
        )
    )
)
