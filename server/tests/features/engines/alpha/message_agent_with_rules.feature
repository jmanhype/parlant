    Scenario: The agent greets the user
        Given the alpha engine
        And an agent
        And an empty session
        And a guide to greet with 'Howdy'
        When processing is triggered
        Then a single message event is produced
        And the message contains a 'Howdy' greeting

    Scenario: The agent offers a thirsty user a drink
        Given the alpha engine
        And an agent
        And a session with a thirsty user
        And a guide to offer thirsty users a Pepsi
        When processing is triggered
        Then a single message event is produced
        And the message contains an offering of a Pepsi
