    Scenario: No events are generated for an empty session
        Given the alpha engine
        And an agent
        And an empty session
        When processing is triggered
        Then no events are generated
