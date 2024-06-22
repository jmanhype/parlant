    Scenario: The agent does not start a conversation if no proactive guidelines exist
        Given the alpha engine
        And an agent
        And an empty session
        When processing is triggered
        Then no events are produced
