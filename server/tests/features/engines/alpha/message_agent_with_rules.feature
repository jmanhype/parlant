    Scenario: The agent greets the user
        Given the alpha engine
        And an agent
        And a guide to greet with 'Howdy'
        And an empty session
        When processing is triggered
        Then a single message event is produced
        And the message contains a 'Howdy' greeting
