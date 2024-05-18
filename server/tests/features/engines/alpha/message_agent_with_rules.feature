    Scenario: The agent greets the user
        Given the alpha engine
        And an agent
        And an empty session
        And a guideline to greet with 'Howdy'
        When processing is triggered
        Then a single message event is produced
        And the message contains a 'Howdy' greeting

    Scenario: The agent offers a thirsty user a drink
        Given the alpha engine
        And an agent
        And a session with a thirsty user
        And a guideline to offer thirsty users a Pepsi
        When processing is triggered
        Then a single message event is produced
        And the message contains an offering of a Pepsi

    Scenario: The agent finds and follows relevant guidelines like a needle in a haystack
        Given the alpha engine
        And an agent
        And a session with a thirsty user
        And a guideline to offer thirsty users a Pepsi
        And 50 other random guidelines
        When processing is triggered
        Then a single message event is produced
        And the message contains an offering of a Pepsi
