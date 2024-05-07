    Scenario: A single message is produced for an empty session
        Given the alpha engine
        And a vanilla agent
        And an empty session
        When processing is triggered
        # the "How can I assist?" greeting...
        Then a single message event is produced

    Scenario: A single message event is produced for a session with a user message
        Given the alpha engine
        And a vanilla agent
        And a session with a single user message
        When processing is triggered
        Then a single message event is produced

    Scenario: A single message event is produced for a session with a few messages
        Given the alpha engine
        And a vanilla agent
        And a session with a few messages
        When processing is triggered
        Then a single message event is produced
