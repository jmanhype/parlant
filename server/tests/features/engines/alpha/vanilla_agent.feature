    Scenario: No events are generated for an empty session
        Given the alpha engine
        And a vanilla agent
        And an empty session
        When processing is triggered
        Then no events are generated

    Scenario: A single message event is generated for a session with a user message
        Given the alpha engine
        And a vanilla agent
        And a session with a single user message
        When processing is triggered
        Then one message event is generated
